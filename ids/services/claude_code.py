"""Claude Code CLI executor service"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional, List

from ids.config import settings
from ids.models.code_task import ClaudeCodeResult
from ids.utils import get_logger

logger = get_logger(__name__)


class ClaudeCodeExecutor:
    """
    Async wrapper around the Claude Code CLI (claude -p).
    Invokes Claude Code as a subprocess to implement code changes.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        max_turns: Optional[int] = None,
    ):
        self.model = model or settings.claude_code_model
        self.max_turns = max_turns or settings.claude_code_max_turns
        logger.info(
            "claude_code_executor_initialized",
            model=self.model,
            max_turns=self.max_turns,
        )

    async def execute(
        self,
        prompt: str,
        working_dir: Path,
        system_prompt: Optional[str] = None,
        allowed_tools: Optional[List[str]] = None,
        max_turns: Optional[int] = None,
    ) -> ClaudeCodeResult:
        """
        Execute a task using Claude Code CLI.

        Args:
            prompt: The implementation prompt
            working_dir: Working directory (target project root)
            system_prompt: Optional system prompt to append
            allowed_tools: Optional list of allowed tools (e.g. ["Bash", "Edit", "Read"])
            max_turns: Override max turns for this execution

        Returns:
            ClaudeCodeResult with execution outcome
        """
        turns = max_turns or self.max_turns

        cmd = [
            "claude",
            "-p",
            "--output-format", "json",
            "--model", self.model,
            "--max-turns", str(turns),
            "--dangerously-skip-permissions",
        ]

        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])

        if allowed_tools:
            cmd.extend(["--allowedTools", ",".join(allowed_tools)])

        logger.info(
            "claude_code_executing",
            working_dir=str(working_dir),
            model=self.model,
            max_turns=turns,
            prompt_length=len(prompt),
        )

        # Unset CLAUDECODE env var to allow nested invocation
        env = {**os.environ, "CLAUDECODE": ""}

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(working_dir),
                env=env,
            )

            stdout, stderr = await process.communicate(input=prompt.encode())

            stdout_str = stdout.decode().strip()
            stderr_str = stderr.decode().strip()

            if stderr_str:
                logger.warning("claude_code_stderr", stderr=stderr_str[:500])

            if not stdout_str:
                return ClaudeCodeResult(
                    success=False,
                    error_message=f"No output from Claude Code. stderr: {stderr_str[:500]}",
                )

            # Parse JSON output
            result_data = json.loads(stdout_str)

            success = (
                result_data.get("type") == "result"
                and not result_data.get("is_error", True)
            )
            subtype = result_data.get("subtype", "")

            return ClaudeCodeResult(
                success=success,
                result_text=result_data.get("result", ""),
                cost_usd=result_data.get("total_cost_usd", 0.0),
                num_turns=result_data.get("num_turns", 0),
                session_id=result_data.get("session_id", ""),
                duration_ms=result_data.get("duration_ms", 0),
                error_message=None if success else f"Claude Code {subtype}",
            )

        except json.JSONDecodeError as e:
            logger.error("claude_code_json_error", error=str(e), output=stdout_str[:200])
            return ClaudeCodeResult(
                success=False,
                result_text=stdout_str,
                error_message=f"Failed to parse Claude Code output: {e}",
            )
        except FileNotFoundError:
            logger.error("claude_code_not_found")
            return ClaudeCodeResult(
                success=False,
                error_message="Claude Code CLI not found. Is 'claude' installed and in PATH?",
            )
        except Exception as e:
            logger.error("claude_code_error", error=str(e))
            return ClaudeCodeResult(
                success=False,
                error_message=f"Claude Code execution failed: {e}",
            )
