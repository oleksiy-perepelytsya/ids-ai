"""Python code analysis using AST"""

import ast
from pathlib import Path
from typing import List, Dict, Set, Optional
from dataclasses import dataclass

from ids.utils import get_logger

logger = get_logger(__name__)


@dataclass
class FunctionInfo:
    """Information about a function"""
    name: str
    args: List[str]
    returns: Optional[str]
    docstring: Optional[str]
    line_number: int
    is_async: bool


@dataclass
class ClassInfo:
    """Information about a class"""
    name: str
    bases: List[str]
    methods: List[str]
    docstring: Optional[str]
    line_number: int


@dataclass
class PythonFileInfo:
    """Complete analysis of a Python file"""
    filepath: str
    imports: List[str]
    functions: List[FunctionInfo]
    classes: List[ClassInfo]
    global_variables: List[str]
    has_main: bool


class PythonAnalyzer:
    """Analyze Python source code using AST"""
    
    def analyze_file(self, filepath: Path) -> Optional[PythonFileInfo]:
        """
        Analyze a Python file and extract structure.
        
        Args:
            filepath: Path to Python file
            
        Returns:
            PythonFileInfo with complete analysis, or None if parse fails
        """
        try:
            source = filepath.read_text(encoding='utf-8')
            tree = ast.parse(source, filename=str(filepath))
            
            return PythonFileInfo(
                filepath=str(filepath),
                imports=self._extract_imports(tree),
                functions=self._extract_functions(tree),
                classes=self._extract_classes(tree),
                global_variables=self._extract_globals(tree),
                has_main=self._has_main_block(tree)
            )
        except SyntaxError as e:
            logger.error("syntax_error_parsing_file", filepath=str(filepath), error=str(e))
            return None
        except Exception as e:
            logger.error("error_analyzing_file", filepath=str(filepath), error=str(e))
            return None
    
    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract all imports from the file"""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
        return imports
    
    def _extract_functions(self, tree: ast.AST) -> List[FunctionInfo]:
        """Extract all top-level functions"""
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Only top-level functions (not methods)
                if not any(isinstance(parent, ast.ClassDef) 
                          for parent in ast.walk(tree) 
                          if hasattr(parent, 'body') and node in parent.body):
                    functions.append(FunctionInfo(
                        name=node.name,
                        args=[arg.arg for arg in node.args.args],
                        returns=ast.unparse(node.returns) if node.returns else None,
                        docstring=ast.get_docstring(node),
                        line_number=node.lineno,
                        is_async=isinstance(node, ast.AsyncFunctionDef)
                    ))
        return functions
    
    def _extract_classes(self, tree: ast.AST) -> List[ClassInfo]:
        """Extract all classes"""
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [
                    item.name for item in node.body 
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                classes.append(ClassInfo(
                    name=node.name,
                    bases=[ast.unparse(base) for base in node.bases],
                    methods=methods,
                    docstring=ast.get_docstring(node),
                    line_number=node.lineno
                ))
        return classes
    
    def _extract_globals(self, tree: ast.AST) -> List[str]:
        """Extract global variable names"""
        globals_vars = []
        if isinstance(tree, ast.Module):
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            globals_vars.append(target.id)
        return globals_vars
    
    def _has_main_block(self, tree: ast.AST) -> bool:
        """Check if file has if __name__ == '__main__' block"""
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Compare):
                    left = node.test.left
                    if isinstance(left, ast.Name) and left.id == '__name__':
                        return True
        return False
    
    def validate_syntax(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Validate Python syntax.
        
        Args:
            code: Python source code
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            error_msg = f"Line {e.lineno}: {e.msg}"
            return False, error_msg
    
    def build_context_summary(self, file_info: PythonFileInfo) -> str:
        """
        Build a concise summary for LLM context.
        
        Args:
            file_info: Analyzed file information
            
        Returns:
            Human-readable summary
        """
        lines = [
            f"File: {file_info.filepath}",
            f"",
            f"Imports: {len(file_info.imports)}",
        ]
        
        if file_info.imports:
            lines.append("  " + ", ".join(file_info.imports[:10]))
            if len(file_info.imports) > 10:
                lines.append(f"  ... and {len(file_info.imports) - 10} more")
        
        lines.append(f"")
        lines.append(f"Functions: {len(file_info.functions)}")
        for func in file_info.functions[:5]:
            args_str = ", ".join(func.args)
            lines.append(f"  {'async ' if func.is_async else ''}def {func.name}({args_str})")
        
        lines.append(f"")
        lines.append(f"Classes: {len(file_info.classes)}")
        for cls in file_info.classes[:5]:
            lines.append(f"  class {cls.name}:")
            for method in cls.methods[:3]:
                lines.append(f"    - {method}()")
        
        return "\n".join(lines)
