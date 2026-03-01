"""Daily Update Service — calls LLM agent with daily_update persona, parses JSON, stores fingerprint."""

import json
import re
from datetime import date, datetime
from ids.services.prompt_loader import fetch_or_fallback
from ids.utils import get_logger

logger = get_logger(__name__)


class DailyUpdateService:
    """Orchestrates the daily planetary fingerprint update via LLM agent call."""

    def __init__(self, llm_client, fingerprint_store):
        self.llm_client = llm_client
        self.fingerprint_store = fingerprint_store

    async def run(self, target_date: date, model: str = "gemini") -> dict:
        """
        Run daily update for the given date:
        1. Load daily_update persona prompt
        2. Call LLM with date as input
        3. Parse JSON response
        4. Store in MongoDB + ChromaDB
        5. Return stored document

        Args:
            target_date: Date to collect fingerprint for
            model: "gemini" or "claude"
        """
        logger.info("daily_update_started", date=target_date.isoformat(), model=model)

        # Load agent persona
        system_prompt = await fetch_or_fallback(None, "daily_update.md")

        # Build user prompt
        user_prompt = (
            f"Generate the planetary daily fingerprint for: {target_date.isoformat()}\n"
            f"Julian day reference: days since J2000.0 = {(target_date - date(2000, 1, 1)).days}\n"
            f"Return only the JSON object."
        )

        # Call LLM
        if model == "claude":
            raw = await self.llm_client.call_claude(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=4000,
            )
        else:
            raw = await self.llm_client.call_gemini(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=4000,
            )

        logger.info("daily_update_llm_response_received", date=target_date.isoformat())

        # Parse JSON from response
        doc = self._parse_json(raw)

        # Ensure required fields
        doc["date"] = target_date.isoformat()
        doc.setdefault("source", "agent")
        doc["updated_at"] = datetime.utcnow().isoformat() + "Z"
        doc["version"] = "1.0"
        doc.setdefault("day_of_year", target_date.timetuple().tm_yday)

        # Store and vectorize
        stored = await self.fingerprint_store.upsert(doc)

        logger.info("daily_update_complete", date=target_date.isoformat())
        return stored

    def _parse_json(self, raw: str) -> dict:
        """Extract and parse JSON from LLM response."""
        # Strip markdown code blocks if present
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()

        # Try direct parse first
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Find first {...} block
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON from LLM response: {e}\nRaw: {raw[:500]}")

        raise ValueError(f"No JSON object found in LLM response. Raw: {raw[:500]}")
