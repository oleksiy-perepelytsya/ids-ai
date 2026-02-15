"""Unified agent implementation - all agents use this class with different personas"""

import re
from pathlib import Path
from typing import Dict, List, Optional
from ids.models import AgentRole, AgentResponse, CrossScore
from ids.services import LLMClient
from ids.utils import get_logger

logger = get_logger(__name__)


class Agent:
    """
    Unified agent class. All agents (Generalist + specialized) use this.
    Differentiation comes from persona YAML files.
    """
    
    def __init__(self, role: AgentRole, llm_client: LLMClient):
        self.role = role
        self.llm_client = llm_client
        self.persona = self._load_persona()
        logger.info("agent_initialized", role=role)
    
    def _load_persona(self) -> Dict:
        """Load persona configuration from Markdown"""
        persona_file = self._get_persona_file()
        
        with open(persona_file, 'r') as f:
            content = f.read()
        
        # Simple Markdown parsing
        persona = {
            "role": "",
            "system_prompt": "",
            "personality_traits": [],
            "focus_areas": []
        }
        
        # Extract role (from # Role: line or role: line)
        role_match = re.search(r'(?:^# Role:|^role:)\s*(.*)', content, re.MULTILINE | re.IGNORECASE)
        if role_match:
            persona["role"] = role_match.group(1).strip().strip('"').strip("'")
            
        # Extract system prompt (everything after # System Prompt header)
        # Search for # System Prompt header (case insensitive, flexible spacing)
        prompt_marker = re.search(r'^#+\s*System\s+Prompt', content, re.MULTILINE | re.IGNORECASE)
        if prompt_marker:
            persona["system_prompt"] = content[prompt_marker.end():].strip()
        else:
            # Fallback to system_prompt: block if exists
            prompt_match = re.search(r'system_prompt:\s*(.*)', content, re.DOTALL | re.IGNORECASE)
            if prompt_match:
                persona["system_prompt"] = prompt_match.group(1).strip()
            else:
                # Last resort: use the whole file as the prompt if no role was found
                if not persona["role"]:
                    persona["system_prompt"] = content.strip()
        
        logger.info("persona_loaded", role=self.role, file=str(persona_file))
        return persona
    
    def _get_persona_file(self) -> Path:
        """Get path to persona Markdown file"""
        personas_dir = Path(__file__).parent / "personas"
        
        # Map role to filename
        role_to_file = {
            AgentRole.GENERALIST: "generalist.md",
            AgentRole.DEVELOPER_PROGRESSIVE: "developer_progressive.md",
            AgentRole.DEVELOPER_CRITIC: "developer_critic.md",
            AgentRole.ARCHITECT_PROGRESSIVE: "architect_progressive.md",
            AgentRole.ARCHITECT_CRITIC: "architect_critic.md",
            AgentRole.SRE_PROGRESSIVE: "sre_progressive.md",
            AgentRole.SRE_CRITIC: "sre_critic.md",
            AgentRole.SOURCER: "sourcer.md",
        }
        
        filename = role_to_file.get(self.role)
        if not filename:
            raise ValueError(f"Unknown role: {self.role}")
        
        return personas_dir / filename
    
    async def analyze(
        self,
        task: str,
        context: str = "",
        previous_rounds: Optional[List[Dict]] = None,
        generalist_cross: Optional[CrossScore] = None,
        learning_patterns: Optional[List[Dict]] = None,
        model_override: Optional[str] = None
    ) -> AgentResponse:
        """
        Analyze task and provide CROSS scoring + recommendation.
        
        Args:
            task: The question/task to analyze
            context: Additional context about the task
            previous_rounds: History of previous deliberation rounds
            generalist_cross: Generalist's CROSS score (for specialized agents)
            learning_patterns: Relevant context found in vector DB
            model_override: Specific model to use (for Sourcer mode)
            
        Returns:
            AgentResponse with CROSS scores and analysis
        """
        # Build prompt
        prompt = self._build_prompt(task, context, previous_rounds, generalist_cross, learning_patterns)
        
        # Call appropriate LLM
        if model_override:
            # Use specific model if requested
            response_text = await self.llm_client.call_model(
                model=model_override,
                prompt=prompt,
                system_prompt=self.persona["system_prompt"],
                temperature=0.7
            )
        elif self.role == AgentRole.GENERALIST:
            response_text = await self.llm_client.call_claude(
                prompt=prompt,
                system_prompt=self.persona["system_prompt"],
                temperature=0.7
            )
        else:
            response_text = await self.llm_client.call_gemini(
                prompt=prompt,
                system_prompt=self.persona["system_prompt"],
                temperature=0.7
            )
        
        # Parse response
        cross_score = self._parse_cross_scores(response_text)
        proposed_approach = self._extract_section(response_text, "PROPOSED APPROACH")
        concerns = self._extract_concerns(response_text)
        
        agent_response = AgentResponse(
            agent_id=self.role,
            raw_response=response_text,  # Store complete LLM response
            cross_score=cross_score,
            proposed_approach=proposed_approach,
            concerns=concerns
        )
        
        logger.info(
            "agent_analysis_complete",
            role=self.role,
            confidence=cross_score.confidence,
            risk=cross_score.risk,
            outcome=cross_score.outcome
        )
        
        return agent_response
    
    def _build_prompt(
        self,
        task: str,
        context: str,
        previous_rounds: Optional[List[Dict]],
        generalist_cross: Optional[CrossScore],
        learning_patterns: Optional[List[Dict]] = None
    ) -> str:
        """Build the prompt for LLM"""
        prompt_parts = []
        
        # Task
        prompt_parts.append(f"TASK:\n{task}\n")
        
        # Context (if any)
        if context:
            prompt_parts.append(f"ADDITIONAL CONTEXT:\n{context}\n")
        
        # Learning Patterns (RAG)
        if learning_patterns:
            prompt_parts.append("\nRELEVANT LEARNING PATTERNS & HISTORICAL DATA:\n")
            for i, pattern in enumerate(learning_patterns, 1):
                prompt_parts.append(f"Pattern {i}: {pattern.get('content')}\n")
        
        # Generalist's initial analysis (for specialized agents)
        if generalist_cross:
            prompt_parts.append(
                f"\nGENERALIST'S INITIAL ANALYSIS:\n"
                f"Confidence: {generalist_cross.confidence}\n"
                f"Risk: {generalist_cross.risk}\n"
                f"Outcome: {generalist_cross.outcome}\n"
                f"Reasoning: {generalist_cross.explanation}\n"
            )
        
        # Previous rounds (if any)
        if previous_rounds:
            prompt_parts.append("\nPREVIOUS DELIBERATION ROUNDS:\n")
            for i, round_data in enumerate(previous_rounds, 1):
                prompt_parts.append(f"\nRound {i}:\n{self._format_round(round_data)}\n")
        
        # Instruction
        prompt_parts.append(
            "\nPlease analyze this task from your perspective and provide your response "
            "in the following format:\n\n"
            "CROSS SCORES:\n"
            "Confidence: [0-100]\n"
            "Risk: [0-100]\n"
            "Outcome: [0-100]\n\n"
            "ANALYSIS:\n"
            "[Your detailed analysis]\n\n"
            "PROPOSED APPROACH:\n"
            "[Your specific recommendation]\n\n"
            "CONCERNS:\n"
            "- [Concern 1]\n"
            "- [Concern 2]\n"
        )
        
        return "\n".join(prompt_parts)
    
    def _format_round(self, round_data: Dict) -> str:
        """Format previous round data for prompt"""
        parts = []
        
        if "merged_cross" in round_data:
            merged = round_data["merged_cross"]
            parts.append(
                f"Average Confidence: {merged.get('avg_confidence', 0):.1f}\n"
                f"Max Risk: {merged.get('max_risk', 0):.1f}\n"
                f"Average Outcome: {merged.get('avg_outcome', 0):.1f}\n"
            )
        
        if "agent_responses" in round_data:
            parts.append("\nAgent Perspectives:")
            for resp in round_data["agent_responses"]:
                parts.append(f"- {resp.get('agent_id', 'Unknown')}: {resp.get('proposed_approach', '')[:100]}...")
        
        return "\n".join(parts)
    
    def _parse_cross_scores(self, response_text: str) -> CrossScore:
        """Parse CROSS scores from LLM response"""
        try:
            # Extract scores using regex
            confidence_match = re.search(r"Confidence:\s*(\d+(?:\.\d+)?)", response_text, re.IGNORECASE)
            risk_match = re.search(r"Risk:\s*(\d+(?:\.\d+)?)", response_text, re.IGNORECASE)
            outcome_match = re.search(r"Outcome:\s*(\d+(?:\.\d+)?)", response_text, re.IGNORECASE)
            
            if not all([confidence_match, risk_match, outcome_match]):
                logger.error("failed_to_parse_cross_scores", response=response_text[:200])
                raise ValueError("Could not parse CROSS scores from response")
            
            confidence = float(confidence_match.group(1))
            risk = float(risk_match.group(1))
            outcome = float(outcome_match.group(1))
            
            # Extract explanation (everything after ANALYSIS: and before PROPOSED APPROACH:)
            explanation = self._extract_section(response_text, "ANALYSIS")
            if not explanation:
                explanation = "No detailed explanation provided"
            
            return CrossScore(
                confidence=confidence,
                risk=risk,
                outcome=outcome,
                explanation=explanation
            )
            
        except Exception as e:
            logger.error("cross_parsing_error", error=str(e), response=response_text[:200])
            # Return default scores if parsing fails
            return CrossScore(
                confidence=50.0,
                risk=50.0,
                outcome=50.0,
                explanation=f"Error parsing response: {str(e)}"
            )
    
    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract a section from the response"""
        pattern = rf"{section_name}:\s*(.*?)(?=\n[A-Z\s]+:|$)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        
        if match:
            return match.group(1).strip()
        
        return ""
    
    def _extract_concerns(self, response_text: str) -> List[str]:
        """Extract concerns list from response"""
        concerns = []
        
        # Find CONCERNS section
        concerns_section = self._extract_section(response_text, "CONCERNS")
        if not concerns_section:
            return concerns
        
        # Extract bullet points
        lines = concerns_section.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("-") or line.startswith("•"):
                concern = line[1:].strip()
                if concern:
                    concerns.append(concern)
        
        return concerns
