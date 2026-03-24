"""Project/context models"""

from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel, Field


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

    # Embedding model for ChromaDB knowledge base
    # "default" = ChromaDB built-in all-MiniLM-L6-v2 (384 dims, no API key needed)
    # "ada-002"  = OpenAI text-embedding-ada-002 (1536 dims, requires OPENAI_API_KEY)
    embedding_model: str = Field(default="default", description="Embedding model for ChromaDB collections")

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
