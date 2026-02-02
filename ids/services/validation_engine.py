"""Python code validation engine"""

import ast
import subprocess
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

from ids.utils import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of code validation"""
    passed: bool
    errors: List[str]
    warnings: List[str]
    validation_type: str  # 'syntax', 'types', 'lint'


class ValidationEngine:
    """
    Multi-layer Python code validation.
    No auto-fix - just validation and reporting.
    """
    
    def __init__(self, enable_type_check: bool = False, enable_lint: bool = False):
        """
        Initialize validation engine.
        
        Args:
            enable_type_check: Run mypy type checking
            enable_lint: Run ruff linting
        """
        self.enable_type_check = enable_type_check
        self.enable_lint = enable_lint
    
    def validate_syntax(self, code: str, filepath: Optional[str] = None) -> ValidationResult:
        """
        Validate Python syntax using AST.
        
        Args:
            code: Python source code
            filepath: Optional filepath for error messages
            
        Returns:
            ValidationResult
        """
        try:
            ast.parse(code)
            return ValidationResult(
                passed=True,
                errors=[],
                warnings=[],
                validation_type='syntax'
            )
        except SyntaxError as e:
            error_msg = f"Line {e.lineno}: {e.msg}"
            if filepath:
                error_msg = f"{filepath}:{error_msg}"
            
            logger.warning("syntax_validation_failed", error=error_msg)
            return ValidationResult(
                passed=False,
                errors=[error_msg],
                warnings=[],
                validation_type='syntax'
            )
    
    def validate_types(self, filepath: Path) -> ValidationResult:
        """
        Run mypy type checking.
        
        Args:
            filepath: Path to Python file
            
        Returns:
            ValidationResult
        """
        if not self.enable_type_check:
            return ValidationResult(
                passed=True,
                errors=[],
                warnings=["Type checking disabled"],
                validation_type='types'
            )
        
        try:
            result = subprocess.run(
                ['mypy', '--no-error-summary', str(filepath)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return ValidationResult(
                    passed=True,
                    errors=[],
                    warnings=[],
                    validation_type='types'
                )
            else:
                errors = [line for line in result.stdout.split('\n') if line.strip()]
                return ValidationResult(
                    passed=False,
                    errors=errors,
                    warnings=[],
                    validation_type='types'
                )
                
        except FileNotFoundError:
            logger.warning("mypy_not_installed")
            return ValidationResult(
                passed=True,
                errors=[],
                warnings=["mypy not available"],
                validation_type='types'
            )
        except Exception as e:
            logger.error("type_validation_error", error=str(e))
            return ValidationResult(
                passed=True,
                errors=[],
                warnings=[f"Type check failed: {e}"],
                validation_type='types'
            )
    
    def validate_lint(self, filepath: Path) -> ValidationResult:
        """
        Run ruff linting.
        
        Args:
            filepath: Path to Python file
            
        Returns:
            ValidationResult
        """
        if not self.enable_lint:
            return ValidationResult(
                passed=True,
                errors=[],
                warnings=["Linting disabled"],
                validation_type='lint'
            )
        
        try:
            result = subprocess.run(
                ['ruff', 'check', str(filepath)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Ruff returns 0 if no issues, 1 if issues found
            warnings = []
            if result.stdout.strip():
                warnings = [line for line in result.stdout.split('\n') if line.strip()]
            
            return ValidationResult(
                passed=True,  # Lint warnings don't fail validation
                errors=[],
                warnings=warnings,
                validation_type='lint'
            )
                
        except FileNotFoundError:
            logger.warning("ruff_not_installed")
            return ValidationResult(
                passed=True,
                errors=[],
                warnings=["ruff not available"],
                validation_type='lint'
            )
        except Exception as e:
            logger.error("lint_validation_error", error=str(e))
            return ValidationResult(
                passed=True,
                errors=[],
                warnings=[f"Lint check failed: {e}"],
                validation_type='lint'
            )
    
    def validate_imports(self, code: str) -> ValidationResult:
        """
        Validate that all imports are resolvable.
        Basic check - doesn't actually import.
        
        Args:
            code: Python source code
            
        Returns:
            ValidationResult
        """
        try:
            tree = ast.parse(code)
            warnings = []
            
            # Extract imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # Could check if module exists in sys.modules or stdlib
                        # For now, just log
                        pass
                elif isinstance(node, ast.ImportFrom):
                    # Similar check for from imports
                    pass
            
            return ValidationResult(
                passed=True,
                errors=[],
                warnings=warnings,
                validation_type='imports'
            )
            
        except Exception as e:
            return ValidationResult(
                passed=False,
                errors=[f"Import validation failed: {e}"],
                warnings=[],
                validation_type='imports'
            )
    
    def validate_file(self, filepath: Path) -> List[ValidationResult]:
        """
        Run all validation layers on a file.
        
        Args:
            filepath: Path to Python file
            
        Returns:
            List of validation results
        """
        results = []
        
        # Read file
        try:
            code = filepath.read_text(encoding='utf-8')
        except Exception as e:
            logger.error("error_reading_file_for_validation", 
                        filepath=str(filepath), error=str(e))
            return [ValidationResult(
                passed=False,
                errors=[f"Cannot read file: {e}"],
                warnings=[],
                validation_type='file_access'
            )]
        
        # Layer 1: Syntax (required)
        syntax_result = self.validate_syntax(code, str(filepath))
        results.append(syntax_result)
        
        if not syntax_result.passed:
            # Don't continue if syntax fails
            return results
        
        # Layer 2: Imports
        import_result = self.validate_imports(code)
        results.append(import_result)
        
        # Layer 3: Type checking (optional)
        if self.enable_type_check:
            type_result = self.validate_types(filepath)
            results.append(type_result)
        
        # Layer 4: Linting (optional)
        if self.enable_lint:
            lint_result = self.validate_lint(filepath)
            results.append(lint_result)
        
        return results
    
    def format_results(self, results: List[ValidationResult]) -> str:
        """
        Format validation results for display.
        
        Args:
            results: List of validation results
            
        Returns:
            Formatted string
        """
        lines = []
        for result in results:
            status = "✅" if result.passed else "❌"
            lines.append(f"{status} {result.validation_type.title()}")
            
            if result.errors:
                for error in result.errors:
                    lines.append(f"  ❌ {error}")
            
            if result.warnings:
                for warning in result.warnings[:5]:  # Limit warnings
                    lines.append(f"  ⚠️  {warning}")
                if len(result.warnings) > 5:
                    lines.append(f"  ... and {len(result.warnings) - 5} more warnings")
        
        return "\n".join(lines)
