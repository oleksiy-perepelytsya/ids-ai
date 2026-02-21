"""Code generation workflow orchestration"""

from pathlib import Path
from typing import Optional

from ids.models import DevSession
from ids.models.code_task import (
    CodeResult, CodeContext, CodeChange, CodeOperation, ClaudeCodeResult
)
from ids.services.python_analyzer import PythonAnalyzer
from ids.services.file_manager import FileManager
from ids.services.validation_engine import ValidationEngine
from ids.services.claude_code import ClaudeCodeExecutor
from ids.utils import get_logger

logger = get_logger(__name__)


class CodeWorkflow:
    """
    Orchestrate code generation and modification workflow.
    Uses Claude Code CLI as the implementation engine.
    """

    def __init__(
        self,
        claude_executor: ClaudeCodeExecutor,
        file_manager: Optional[FileManager] = None,
        analyzer: Optional[PythonAnalyzer] = None,
        validator: Optional[ValidationEngine] = None,
    ):
        self.claude_executor = claude_executor
        self.file_manager = file_manager
        self.analyzer = analyzer
        self.validator = validator

    async def implement_from_consensus(
        self,
        session: DevSession,
        project_path: Path,
    ) -> ClaudeCodeResult:
        """
        Implement code changes based on deliberation consensus.

        Extracts the agreed approach from the session's rounds and
        invokes Claude Code to execute it against the target project.

        Args:
            session: Completed deliberation session with CONSENSUS status
            project_path: Root path of the target project

        Returns:
            ClaudeCodeResult with implementation outcome
        """
        logger.info(
            "implementing_from_consensus",
            session_id=session.session_id,
            project=str(project_path),
        )

        prompt = self._build_consensus_prompt(session)

        return await self.claude_executor.execute(
            prompt=prompt,
            working_dir=project_path,
            system_prompt=(
                "You are implementing a solution that was agreed upon by a team of "
                "specialist agents through deliberation. Follow the agreed approach "
                "closely. Read existing code before making changes."
            ),
        )

    async def implement_direct(
        self,
        task_description: str,
        project_path: Path,
    ) -> ClaudeCodeResult:
        """
        Implement code changes directly without prior deliberation.

        Used by the /code command for straightforward tasks.

        Args:
            task_description: What to implement
            project_path: Root path of the target project

        Returns:
            ClaudeCodeResult with implementation outcome
        """
        logger.info(
            "implementing_direct",
            project=str(project_path),
            task_length=len(task_description),
        )

        return await self.claude_executor.execute(
            prompt=task_description,
            working_dir=project_path,
        )

    def _build_consensus_prompt(self, session: DevSession) -> str:
        """
        Build an implementation prompt from the deliberation consensus.

        Extracts the task, generalist framing, agent proposals, and
        consensus reasoning into a structured prompt for Claude Code.
        """
        parts = [f"# Task\n{session.task}\n"]

        if session.context:
            parts.append(f"# Additional Context\n{session.context}\n")

        if not session.rounds:
            return "\n".join(parts)

        last_round = session.rounds[-1]

        # Generalist synthesis
        if last_round.generalist_response:
            parts.append(
                f"# Agreed Approach ({last_round.generalist_response.role_name} Synthesis)\n"
                f"{last_round.generalist_response.response}\n"
            )

        # Specialist perspectives
        proposals = []
        for resp in last_round.agent_responses:
            if resp.response:
                proposals.append(
                    f"**{resp.role_name}**: {resp.response}"
                )
        if proposals:
            parts.append("# Specialist Perspectives\n" + "\n\n".join(proposals) + "\n")

        # Decision reasoning
        if last_round.decision_reasoning:
            parts.append(
                f"# Consensus Reasoning\n{last_round.decision_reasoning}\n"
            )

        parts.append(
            "# Instructions\n"
            "Implement the agreed solution. Read existing project files first "
            "to understand the codebase, then make the necessary changes."
        )

        return "\n".join(parts)

    # --- Legacy methods (kept for standalone use) ---

    async def execute_code_task(
        self,
        session: DevSession,
        code_context: CodeContext,
        generated_code: str,
        target_file: Path,
    ) -> CodeResult:
        """
        Execute a code task with validation (legacy path).
        Validates syntax, writes file, runs validation, rolls back on failure.
        """
        if not self.file_manager or not self.validator:
            return CodeResult(
                success=False,
                changes=[],
                validation_summary="FileManager/Validator not configured",
                error_message="Legacy code path requires file_manager and validator",
                iterations=1,
            )

        logger.info(
            "executing_code_task",
            session_id=session.session_id,
            target=str(target_file),
        )

        syntax_result = self.validator.validate_syntax(generated_code, str(target_file))
        if not syntax_result.passed:
            return CodeResult(
                success=False,
                changes=[],
                validation_summary=self.validator.format_results([syntax_result]),
                error_message=f"Syntax errors: {', '.join(syntax_result.errors)}",
                iterations=1,
            )

        write_success = self.file_manager.write_file(
            filepath=target_file,
            content=generated_code,
            session_id=session.session_id,
            create_backup=True,
        )
        if not write_success:
            return CodeResult(
                success=False,
                changes=[],
                validation_summary="Failed to write file",
                error_message="File write operation failed",
                iterations=1,
            )

        validation_results = self.validator.validate_file(target_file)
        all_passed = all(r.passed for r in validation_results)
        validation_summary = self.validator.format_results(validation_results)

        if not all_passed:
            self.file_manager.rollback_file(target_file)
            return CodeResult(
                success=False,
                changes=[],
                validation_summary=validation_summary,
                error_message="Validation failed, changes rolled back",
                iterations=1,
            )

        operation = CodeOperation.CREATE if not target_file.exists() else CodeOperation.MODIFY
        return CodeResult(
            success=True,
            changes=[CodeChange(
                filepath=str(target_file),
                operation=operation,
                content=generated_code,
                backup_path=str(self.file_manager.backups.get(str(target_file)).backup_path)
                if str(target_file) in self.file_manager.backups else None,
            )],
            validation_summary=validation_summary,
            error_message=None,
            iterations=1,
        )

    async def analyze_project(self, project_path: Path) -> dict:
        """Analyze a Python project structure."""
        if not self.analyzer:
            return {"error": "PythonAnalyzer not configured"}

        logger.info("analyzing_project", path=str(project_path))

        analysis = {
            "path": str(project_path),
            "files": [],
            "total_functions": 0,
            "total_classes": 0,
            "imports": set(),
        }

        python_files = list(project_path.rglob("*.py"))
        for py_file in python_files:
            file_info = self.analyzer.analyze_file(py_file)
            if file_info:
                analysis["files"].append({
                    "path": str(py_file.relative_to(project_path)),
                    "functions": len(file_info.functions),
                    "classes": len(file_info.classes),
                })
                analysis["total_functions"] += len(file_info.functions)
                analysis["total_classes"] += len(file_info.classes)
                analysis["imports"].update(file_info.imports)

        analysis["imports"] = sorted(list(analysis["imports"]))
        return analysis

    def build_code_context(
        self,
        project_path: Path,
        target_files: list[str],
        task_description: str,
    ) -> str:
        """Build context string for LLM code generation."""
        if not self.analyzer:
            return f"Task: {task_description}\nProject: {project_path.name}"

        lines = [
            f"Task: {task_description}",
            "",
            f"Project: {project_path.name}",
            "",
        ]

        for target_file in target_files:
            file_path = project_path / target_file
            if file_path.exists():
                file_info = self.analyzer.analyze_file(file_path)
                if file_info:
                    lines.append(self.analyzer.build_context_summary(file_info))
                    lines.append("")

        return "\n".join(lines)
