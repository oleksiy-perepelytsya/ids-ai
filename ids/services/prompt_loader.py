"""Prompt loader - fetches agent prompts from URLs or local fallback files"""

from pathlib import Path
from typing import Optional

import aiohttp

from ids.utils import get_logger

logger = get_logger(__name__)

_PERSONAS_DIR = Path(__file__).parent.parent / "agents" / "personas"


async def fetch_prompt_from_url(url: str) -> str:
    """Fetch a system prompt from a URL."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=30)) as response:
            response.raise_for_status()
            return await response.text()


def load_fallback_prompt(filename: str) -> str:
    """Load a system prompt from a local persona file."""
    filepath = _PERSONAS_DIR / filename
    if filepath.exists():
        return filepath.read_text()
    # Generic minimal prompt if file doesn't exist
    role_name = filename.replace(".md", "").replace("_", " ").title()
    return f"# Role: {role_name}\n\n# System Prompt\nYou are a specialist analyst. Provide clear, structured analysis."


async def fetch_or_fallback(url: Optional[str], fallback_filename: str) -> str:
    """
    Try to fetch prompt from URL; fall back to local file on any error.

    Args:
        url: Optional URL to fetch from
        fallback_filename: Local persona filename (e.g. 'generalist.md')

    Returns:
        Prompt text
    """
    if url:
        try:
            prompt = await fetch_prompt_from_url(url)
            logger.info("prompt_loaded_from_url", url=url, length=len(prompt))
            return prompt
        except Exception as e:
            logger.warning("prompt_url_fetch_failed", url=url, error=str(e), fallback=fallback_filename)

    prompt = load_fallback_prompt(fallback_filename)
    logger.info("prompt_loaded_from_file", filename=fallback_filename, length=len(prompt))
    return prompt
