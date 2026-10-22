import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
import httpx
from app.config import settings
from app.services.resource_limits import bounded_resource

logger = logging.getLogger(__name__)


class LLMRouter:
    """Multi-Provider Router for Google Gemini and OpenAI with auto-fallback and structured output."""

    def __init__(self):
        self.gemini_key = settings.GEMINI_API_KEY
        self.openai_key = settings.OPENAI_API_KEY
        self.primary_provider = settings.TRANSLATION_PRIMARY_PROVIDER.lower()
        self.fallback_provider = settings.TRANSLATION_FALLBACK_PROVIDER.lower()

    async def generate_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        provider_override: Optional[str] = None,
        model_override: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Dispatches request to active provider with auto-fallback."""
        target_provider = (provider_override or self.primary_provider).lower()
        temp = temperature if temperature is not None else settings.LLM_TEMPERATURE
        if target_provider not in {'gemini', 'openai'}:
            raise ValueError(f'Unsupported translation provider: {target_provider}')

        try:
            if target_provider == "gemini":
                return await self._call_gemini(system_prompt, user_prompt, model_override, temp)
            elif target_provider == "openai":
                return await self._call_openai(system_prompt, user_prompt, model_override, temp)
            else:
                return await self._call_gemini(system_prompt, user_prompt, model_override, temp)
        except Exception as primary_error:
            logger.warning(f"Primary provider [{target_provider}] failed: {primary_error}")
            
            if not settings.ENABLE_AUTO_FALLBACK_ON_ERROR or model_override:
                raise primary_error

            backup_provider = self.fallback_provider if target_provider != self.fallback_provider else "openai"
            if backup_provider == target_provider:
                backup_provider = "gemini" if target_provider == "openai" else "openai"

            logger.info(f"Triggering Auto-Fallback to backup provider [{backup_provider}]...")
            try:
                if backup_provider == "gemini":
                    return await self._call_gemini(system_prompt, user_prompt, None, temp)
                else:
                    return await self._call_openai(system_prompt, user_prompt, None, temp)
            except Exception as fallback_error:
                logger.error(f"Fallback provider [{backup_provider}] also failed: {fallback_error}")
                raise RuntimeError(f"All LLM providers failed. Primary: {primary_error} | Fallback: {fallback_error}")

    @bounded_resource('llm-gemini', lambda: settings.GEMINI_MAX_CONCURRENCY)
    async def _call_gemini(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.3
    ) -> str:
        """Call Google Gemini API via official endpoint with JSON structured output and automatic model fallback."""
        api_key = self.gemini_key or settings.GEMINI_API_KEY
        if not api_key or "DIEN_API_KEY" in api_key:
            raise ValueError("GEMINI_API_KEY is not configured or placeholder detected.")

        target_model = model or settings.GEMINI_MODEL
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent'
        headers = {'Content-Type': 'application/json', 'x-goog-api-key': api_key}
        payload = {
            'contents': [{'role': 'user', 'parts': [{'text': system_prompt + '\n\n' + user_prompt}]}],
            'generationConfig': {'temperature': temperature, 'responseMimeType': 'application/json'},
        }
        # Let the configured model choose its supported thinking defaults.
        # A blanket thinkingBudget=0 is not a portable contract across models.
        for attempt in range(4):
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                candidates = response.json().get('candidates', [])
                parts = candidates[0].get('content', {}).get('parts', []) if candidates else []
                content = ''.join(part.get('text', '') for part in parts if not part.get('thought'))
                if not content.strip():
                    raise RuntimeError('Gemini returned no usable translation content')
                return content
            if response.status_code not in (429, 503) or attempt == 3:
                raise RuntimeError(f'Gemini API error {response.status_code}: {response.text[:300]}')
            wait = 4.0 * (attempt + 1)
            try:
                for detail in response.json().get('error', {}).get('details', []):
                    if str(detail.get('retryDelay', '')).endswith('s'):
                        wait = max(wait, float(detail['retryDelay'][:-1]) + 1)
            except (ValueError, TypeError, AttributeError):
                logger.debug('Provider supplied no usable retry delay; using bounded backoff')
            logger.warning('Gemini request returned %s; retry %s/3', response.status_code, attempt + 1)
            await asyncio.sleep(min(wait, 15.0))
        raise RuntimeError('Gemini retry budget exhausted')

    @bounded_resource('llm-openai', lambda: settings.OPENAI_MAX_CONCURRENCY)
    async def _call_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.3
    ) -> str:
        """Call OpenAI API with json_object format."""
        api_key = self.openai_key or settings.OPENAI_API_KEY
        if not api_key or "DIEN_API_KEY" in api_key:
            raise ValueError("OPENAI_API_KEY is not configured or placeholder detected.")

        target_model = model or settings.OPENAI_MODEL
        url = f"{settings.OPENAI_API_BASE}/chat/completions"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": target_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI API error {resp.status_code}: {resp.text}")
            
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError(f"No choices returned by OpenAI: {data}")
            
            content = choices[0].get("message", {}).get("content", "")
            return content

    async def test_connection(self, provider: str, api_key: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
        """Test API key and model connectivity."""
        test_sys = "You are a translator. Return JSON: {\"status\": \"ok\", \"model\": \"name\"}"
        test_usr = "Hello world"
        
        # Per-request router prevents concurrent key tests or translations from
        # observing another request's credentials.
        isolated = LLMRouter()
        try:
            if provider == 'gemini':
                isolated.gemini_key = api_key or self.gemini_key
                res = await isolated._call_gemini(test_sys, test_usr, model=model, temperature=0.1)
            elif provider == 'openai':
                isolated.openai_key = api_key or self.openai_key
                res = await isolated._call_openai(test_sys, test_usr, model=model, temperature=0.1)
            else:
                raise ValueError('Unsupported provider')
            return {'success': True, 'provider': provider, 'raw_response': res}
        except Exception as error:
            return {'success': False, 'provider': provider, 'error': type(error).__name__ + ': connection test failed'}


llm_router = LLMRouter()
