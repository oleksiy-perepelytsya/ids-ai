"""Project/context models"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DataSourceConfig(BaseModel):
    """Inline copy of DataSource for Mongo serialisation (avoids circular import)."""
    name: str
    kind: str
    backend: str = "qdrant"
    namespace: str
    embedding_model: str | None = None
    priority: int = 0
    filters: dict = Field(default_factory=dict)


class Project(BaseModel):
    """
    Project represents a context domain for deliberation.
    Can be a software project, business domain, or any decision context.
    """
    project_id: str = Field(description="Unique project identifier")
    name: str = Field(description="Project name")
    description: Optional[str] = Field(default=None, description="Project description")
    path: Optional[str] = Field(default=None, description="Filesystem path (if applicable)")

    user_id: int = Field(description="Owner's user ID (interface-agnostic)")

    # Parliament prompt URLs (fetched at runtime; fallback to local persona files)
    generalist_prompt_url: Optional[str] = Field(default=None, description="URL to generalist system prompt")
    sourcer_prompt_url: Optional[str] = Field(default=None, description="URL to sourcer system prompt")
    genprompt_prompt_url: Optional[str] = Field(default=None, description="URL to prompt-generator system prompt")
    specialist_prompt_urls: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of specialist key ('1', '2', ...) to prompt URL"
    )
    # Inline prompt text per specialist key — takes precedence over URL when set
    # Populated by /genprompt or /set_prompts specialist1 <role_name>
    specialist_prompts: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of specialist key to stored prompt text (overrides URL)"
    )
    specialist_role_names: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of specialist key to role name label (e.g. '1' -> 'marine_biologist')"
    )

    # Model overrides per agent role (None = use global default from settings)
    generalist_model: Optional[str] = Field(default=None, description="LLM model for generalist agent")

    # Embedding model — registry key (e.g. "minilm", "ada", "bge-large")
    # Governs the learning_{project_id} collection.  Legacy values "default"
    # and "ada-002" are resolved via embeddings.resolve_embedding_key().
    embedding_model: str = Field(default="minilm", description="Embedding model registry key")

    # Searchable data sources bound to this project.
    # When empty, SearchOrchestrator falls back to a single learning_ collection.
    data_sources: List[DataSourceConfig] = Field(
        default_factory=list,
        description="Declared search sources (learning, corpus, graph, …)",
    )

    # MCP context server for the Sourcer agent (optional).
    # When set, sourcer also queries this MCP SSE endpoint and merges results.
    mcp_context_url: Optional[str] = Field(default=None, description="MCP SSE endpoint URL for Sourcer context")
    mcp_tool_name: Optional[str] = Field(default=None, description="MCP tool name to call (None = auto-discover)")

    # Deliberation limits (None = use global default from settings)
    max_rounds: Optional[int] = Field(default=None, description="Max deliberation rounds before dead-end")

    # Response size limits in tokens
    specialist_max_tokens: int = Field(default=1000, description="Max tokens for specialist responses")
    generalist_max_tokens: int = Field(default=2000, description="Max tokens for generalist responses")
    sourcer_max_tokens: int = Field(default=3000, description="Max tokens for sourcer responses")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
