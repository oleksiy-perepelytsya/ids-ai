"""Unified LLM client for Gemini and Claude APIs"""

import asyncio
import google.generativeai as genai
from anthropic import Anthropic
from typing import Dict, Any
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
        temperature: float = 0.7
    ) -> str:
        """
        Call Gemini API.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            temperature: Sampling temperature
            
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
                        temperature=temperature
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
