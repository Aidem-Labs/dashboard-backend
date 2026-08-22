import logging
import httpx
from typing import AsyncIterator
from app.config import HUGGINGFACE_API_KEY, HUGGINGFACE_MODEL

# Setup logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class HuggingFaceLLM:
    """Calls Hugging Face Inference API for chat completions."""

    # Reliable models that work on Hugging Face Inference API
    MODELS = [
        "Qwen/Qwen2.5-72B-Instruct",
        "mistralai/Mistral-7B-Instruct-v0.3",
        "meta-llama/Llama-3.2-3B-Instruct",
        "microsoft/Phi-3-mini-4k-instruct",
    ]

    def __init__(self, model: str = None):
        self.model = model or HUGGINGFACE_MODEL
        self.api_key = HUGGINGFACE_API_KEY
        # Use the router endpoint which is more reliable for chat completions
        self.api_url = f"https://router.huggingface.co/v1/chat/completions"
        self.fallback_models = [m for m in self.MODELS if m != self.model]

    async def generate(self, messages: list[dict]) -> str:
        """Generate a response from the LLM given a conversation history."""
        if not self.api_key:
            return "[Hugging Face API key not set. Please add it to .env]"

        print("\n" + "="*80)
        print(" AI LANGUAGE MODEL - GENERATING RESPONSE")
        print("="*80)
        print(f" Model: {self.model}")
        print(f" API URL: {self.api_url}")
        print(f" Messages in conversation: {len(messages)}")
        print("-"*80)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 300,
            "temperature": 0.7,
        }

        async with httpx.AsyncClient() as client:
            try:
                print(f" Sending request to HuggingFace Router...")
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=60,
                )

                if response.status_code != 200:
                    print(f"\n API Error ({response.status_code}): {response.text}")
                    return f"Error: {response.text}"

                result = response.json()
                return self._parse_chat_response(result)

            except Exception as e:
                print(f"\n Error: {str(e)}")
                return f"Error: {str(e)}"

    async def _try_chat_api(self, headers: dict, messages: list[dict]) -> str:
        """Try alternative chat completions endpoint."""
        print(f"\n Trying alternative Chat API endpoint...")
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 300,
            "temperature": 0.7,
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.chat_api_url,
                    headers=headers,
                    json=payload,
                    timeout=60,
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return self._parse_chat_response(result)
                else:
                    print(f" Chat API also failed: {response.status_code}")
                    return "Error: Could not generate response (no compatible endpoint)"
            except Exception as e:
                print(f" Chat API error: {str(e)}")
                return "Error: Could not generate response"

    def _parse_chat_response(self, result) -> str:
        """Parse response from Chat Completions API (OpenAI-compatible format)."""
        if "choices" in result and len(result["choices"]) > 0:
            message = result["choices"][0].get("message", {})
            content = message.get("content", "")
            return content.strip()
        return "Sorry, I couldn't generate a response right now."

    def _parse_response(self, result) -> str:
        """Parse response from Inference API."""
        if isinstance(result, list) and len(result) > 0:
            generated_text = result[0].get("generated_text", "")
            return generated_text.strip()
        return "Sorry, I couldn't generate a response right now."

    def _build_prompt_text(self, system_prompt: str, messages: list[dict]) -> str:
        """Build a text prompt from messages for the text generation API."""
        prompt = ""
        if system_prompt:
            prompt += f"{system_prompt}\n\n"
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                prompt += f"User: {content}\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n"
            elif role == "system":
                prompt += f"System: {content}\n"
        
        prompt += "Assistant:"
        return prompt

    def _build_prompt(self, system_prompt: str, messages: list[dict]) -> str:
        """Build a text prompt from messages for the inference API."""
        prompt = ""
        if system_prompt:
            prompt += f"<|system|>\n{system_prompt}\n"
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                prompt += f"<|user|>\n{content}\n"
            elif role == "assistant":
                prompt += f"<|assistant|>\n{content}\n"
        
        prompt += "<|assistant|>\n"
        return prompt
