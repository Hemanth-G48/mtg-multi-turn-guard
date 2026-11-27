import os
from dotenv import load_dotenv, find_dotenv

import json
from typing import Dict, Any, Tuple
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

# import replicate
from prompts.prompt_templates import PromptManager
from config.mtg_config import MTGConfig
from prompts.prompt_response import Response

# Command Code Provider API: OpenAI-compatible endpoint serving deepseek/deepseek-v4.1-flash
COMMAND_CODE_BASE_URL = "https://api.commandcode.ai/provider/v1"
COMMAND_CODE_MODEL = "deepseek/deepseek-v4.1-flash"


class LLMManager:
    def __init__(self, prompt_manager: PromptManager):
        """
        Initializes the LLMManager with the necessary API clients and keys.

        Args:
            prompt_manager (PromptManager): The PromptManager instance for managing prompts.
        """
        self.prompt_manager = prompt_manager
        self.config = MTGConfig("config/config.yaml")
        # Load environment variables from .env file
        load_dotenv(find_dotenv())

        # Access environment variables. Clients are created lazily so a run only
        # needs the key for the provider it actually uses.
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_GENAI_API_KEY")
        self.commandcode_api_key = os.getenv("COMMAND_CODE_API_KEY")

        self.openai_client = None
        self.anthropic_client = None
        self.commandcode_client = None

    def _get_openai_client(self) -> AsyncOpenAI:
        if not self.openai_api_key:
            raise ValueError("Missing OPENAI_API_KEY environment variable")
        if self.openai_client is None:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
        return self.openai_client

    def _get_anthropic_client(self) -> AsyncAnthropic:
        if not self.anthropic_api_key:
            raise ValueError("Missing ANTHROPIC_API_KEY environment variable")
        if self.anthropic_client is None:
            self.anthropic_client = AsyncAnthropic(api_key=self.anthropic_api_key)
        return self.anthropic_client

    def _get_commandcode_client(self) -> AsyncOpenAI:
        if not self.commandcode_api_key:
            raise ValueError(
                "Missing COMMAND_CODE_API_KEY environment variable. Create a key at "
                "https://commandcode.ai/settings/keys (API access requires a GOAT plan or higher)."
            )
        if self.commandcode_client is None:
            self.commandcode_client = AsyncOpenAI(
                api_key=self.commandcode_api_key,
                base_url=COMMAND_CODE_BASE_URL,
            )
        return self.commandcode_client

    async def analyze_conversation(
        self, llm_type: str, prev_pair: Tuple[str, str], current_pair: Tuple[str, str]
    ) -> Dict[str, Any]:
        """
        Analyzes a conversation using the specified LLM type.

        Args:
            llm_type (str): The type of LLM (e.g., "gpt", "claude").
            prev_pair (Tuple[str, str]): The previous assistant-human conversation pair.
            current_pair (Tuple[str, str]): The current assistant-human conversation pair.

        Returns:
            Dict[str, Any]: The analysis result from the LLM.
        """
        template = self.prompt_manager.get_template(llm_type)
        print("*" * 50)
        print("Formatting prompt now")
        prompt = template.format(prev_pair=prev_pair, current_pair=current_pair)
        # print("Prompt formatted: " + prompt)

        handlers = {
            "commandcode": self._call_commandcode,
            "gpt": self._call_gpt,
            "claude": self._call_claude,
            "gemini": self._call_gemini,
           # "llama": self._call_llama,
        }

        handler = handlers.get(llm_type)
        if not handler:
            raise ValueError(f"Unsupported LLM type: {llm_type}")

        return await handler(prompt)

    async def _call_commandcode(self, prompt: str) -> Dict[str, Any]:
        """
        Calls Command Code Provider API with the provided prompt.

        Args:
            prompt (str): The input prompt for the model.

        Returns:
            Dict[str, Any]: The response as a JSON dictionary.
        """
        client = self._get_commandcode_client()
        response = await client.chat.completions.create(
            model=COMMAND_CODE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        response_content = response.choices[0].message.content
        parsed_data = self.clean_and_parse_json(response_content)

        response_out = Response(
            content=response_content,
            risk_level=parsed_data.get("risk_level"),
            recommendations=parsed_data.get("recommendations"),
            intent_shift=parsed_data.get("intent_shift"),
            prompt_attack=parsed_data.get("prompt_attack"),
            patterns=parsed_data.get("patterns"),
            overall_progression_summary=parsed_data.get("overall_progression_summary"),
        )

        return response_out.dict()

    @staticmethod
    def clean_and_parse_json(content: str) -> dict:
        """
        Strips Markdown code fences and parses the model's JSON response.
        """
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            if cleaned.rstrip().endswith("```"):
                cleaned = cleaned.rstrip()[:-3]
        return json.loads(cleaned.strip())

    async def _call_gpt(self, prompt: str) -> Dict[str, Any]:
        """
        Calls OpenAI GPT model with the provided prompt.

        Args:
            prompt (str): The input prompt for GPT.

        Returns:
            Dict[str, Any]: The response as a JSON dictionary.
        """
        response = await self._get_openai_client().chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        # Extract content from OpenAI response
        response_content = response.choices[0].message.content

        # Parse the content to extract structured information
        # You'll need to implement this based on your content structure
        parsed_data = self.parse_content(
            response_content
        )  # This function needs to be implemented

        # Create Response instance with all fields
        response_out = Response(
            content=response_content,
            risk_level=parsed_data.get("risk_level"),
            recommendations=parsed_data.get("recommendations"),
            intent_shift=parsed_data.get("intent_shift"),
            prompt_attack=parsed_data.get("prompt_attack"),
            patterns=parsed_data.get("patterns"),
            overall_progression_summary=parsed_data.get("overall_progression_summary"),
        )

        # Access and print the attributes
        # print("Risk Level:", response_out.risk_level)
        # print("Recommendations:", response_out.recommendations)
        # print("Intent Shift Details:", response_out.intent_shift)
        # print("Prompt Attack Details:", response_out.prompt_attack)
        # print("Patterns:", response_out.patterns)
        # print("Overall Progression Summary:", response_out.overall_progression_summary)

        return response_out.dict()

    def parse_content(self, content: str) -> dict:
        """
        Parse the OpenAI response content to extract structured information.
        This is a placeholder - implement based on your content structure.
        """
        # Example implementation - you'll need to modify this based on your actual content structure
        return {
            'risk_level': None,
            'recommendations': [],
            'intent_shift': {},
            'prompt_attack': {},
            'patterns': {},
            'overall_progression_summary': {}
        }

    async def _call_claude(self, prompt: str) -> Dict[str, Any]:
        """
        Calls Anthropic Claude model with the provided prompt.

        Args:
            prompt (str): The input prompt for Claude.

        Returns:
            Dict[str, Any]: The response as a JSON dictionary.
        """
        response = await self._get_anthropic_client().messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=2000,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(response.content[0].text)

    async def _call_gemini(self, prompt: str) -> Dict[str, Any]:
        """
        Calls Google Generative AI Gemini model with the provided prompt.

        Args:
            prompt (str): The input prompt for Gemini.

        Returns:
            Dict[str, Any]: The response as a JSON dictionary.
        """
        if not self.google_api_key:
            raise ValueError("Missing GOOGLE_GENAI_API_KEY environment variable")
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai is required for the gemini backend: "
                "pip install google-generativeai"
            )
        genai.configure(api_key=self.google_api_key)
        model = genai.GenerativeModel("gemini-pro")
        response = await model.generate_content_async(prompt)
        return json.loads(response.text)

    # async def _call_llama(self, prompt: str) -> Dict[str, Any]:
    #     """
    #     Calls LLaMA model hosted on Replicate with the provided prompt.

    #     Args:
    #         prompt (str): The input prompt for LLaMA.

    #     Returns:
    #         Dict[str, Any]: The response as a JSON dictionary.
    #     """
    #     output = await self.replicate_client.async_run(
    #         "meta/llama-2-70b-chat:02e509c789964a7ea8736978a43525956ef40397be9033abf9fd2badfe68c9e3",
    #         input={"prompt": prompt},
    #     )
    #     return json.loads(output)
