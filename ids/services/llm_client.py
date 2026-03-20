"""Unified LLM client for Gemini and Claude APIs"""

import asyncio
import aiohttp
import google.generativeai as genai
from anthropic import Anthropic
from ids.config import settings
from ids.utils import get_logger

logger = get_logger(__name__)


class LLMClient:
    """Unified client for both Gemini and Claude APIs"""

    def __init__(self):
        # Configure Gemini
        genai.configure(api_key=settings.gemini_api_key)
        # Use configurable model name from settings
        self.gemini_model = genai.GenerativeModel(settings.gemini_model)

        # Configure Claude (Anthropic client)
        self.anthropic = Anthropic(
            api_key=settings.anthropic_api_key
        )
        self.claude_model = settings.claude_model

        logger.info("llm_client_initialized")

    async def call_gemini(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """
        Call Gemini API.

        Args:
            prompt: User prompt
            system_prompt: System instructions
            temperature: Sampling temperature
            max_tokens: Maximum output tokens

        Returns:
            Model response text
        """
        try:
            # Build full prompt with system instructions
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            # Run blocking call in executor
            loop = asyncio.get_running_loop()

            def _call_gemini_sync():
                return self.gemini_model.generate_content(
                    full_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens
                    )
                )

            response = await loop.run_in_executor(None, _call_gemini_sync)

            logger.info("gemini_call_success")
            return response.text

        except Exception as e:
            logger.error("gemini_call_failed", error=str(e))
            raise

    async def call_claude(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """
        Call Claude API.

        Args:
            prompt: User prompt
            system_prompt: System instructions
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            Model response text
        """
        try:
            message_params = {
                "model": self.claude_model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }

            if system_prompt:
                message_params["system"] = system_prompt

            response = self.anthropic.messages.create(**message_params)

            logger.info("claude_call_success")
            return response.content[0].text

        except Exception as e:
            logger.error("claude_call_failed", error=str(e))
            raise

    async def call_local(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        base_url: str = None,
        timeout_seconds: int = 3600,  # 60 min — local inference is slow
    ) -> str:
        """
        Call a local llama-server (OpenAI-compatible /v1/chat/completions endpoint).

        Args:
            base_url: llama-server address, default http://localhost:8080
            timeout_seconds: total request timeout (default 15 min)
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        if base_url is None:
            base_url = settings.local_llm_url
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{base_url}/v1/chat/completions",
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    text = data["choices"][0]["message"]["content"]
                    logger.info("local_llm_call_success", base_url=base_url)
                    return text
        except asyncio.TimeoutError:
            msg = f"Local model timed out after {timeout_seconds // 60} min — try a shorter query or increase timeout"
            logger.error("local_llm_timeout", base_url=base_url, timeout=timeout_seconds)
            raise RuntimeError(msg)
        except Exception as e:
            logger.error("local_llm_call_failed", error=str(e), base_url=base_url)
            raise

    async def call_model(
        self,
        model: str,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """Call a specific model based on string"""
        if "claude" in model.lower():
            return await self.call_claude(prompt, system_prompt, temperature, max_tokens)
        elif "gemini" in model.lower():
            return await self.call_gemini(prompt, system_prompt, temperature, max_tokens)
        elif model.lower() in ("local", "llama"):
            return await self.call_local(prompt, system_prompt, temperature, max_tokens)
        else:
            # Fallback
            return await self.call_gemini(prompt, system_prompt, temperature, max_tokens)
