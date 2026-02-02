"""Models for code operations"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from pathlib import Path


class CodeOperation(str, Enum):
    """Type of code operation"""
    CREATE = "create"      # Create new file
    MODIFY = "modify"      # Modify existing file
    DELETE = "delete"      # Delete file
    ANALYZE = "analyze"    # Just analyze, don't change


class CodeTaskType(str, Enum):
    """Type of code task"""
    DELIBERATION_ONLY = "deliberation_only"  # Just discuss, no code
    CODE_GENERATION = "code_generation"       # Write new code
    CODE_MODIFICATION = "code_modification"   # Modify existing
    CODE_ANALYSIS = "code_analysis"           # Analyze/review


class CodeChange(BaseModel):
    """A single code change"""
    filepath: str = Field(description="Path to file")
    operation: CodeOperation = Field(description="Operation type")
    content: Optional[str] = Field(default=None, description="New file content")
    backup_path: Optional[str] = Field(default=None, description="Backup location")


class CodeResult(BaseModel):
    """Result of code generation/modification"""
    success: bool = Field(description="Whether operation succeeded")
    changes: List[CodeChange] = Field(default_factory=list, description="Code changes made")
    validation_summary: str = Field(default="", description="Validation results")
    error_message: Optional[str] = Field(default=None, description="Error if failed")
    iterations: int = Field(default=1, description="Number of attempts")


class CodeContext(BaseModel):
    """Context for code operations"""
    project_path: Path = Field(description="Root path of project")
    target_files: List[str] = Field(default_factory=list, description="Files to operate on")
    related_files: List[str] = Field(default_factory=list, description="Related files for context")
    task_description: str = Field(description="What to do")
