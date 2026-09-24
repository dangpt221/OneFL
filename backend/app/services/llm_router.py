import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
import httpx
from app.config import settings

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

        try:
            if target_provider == "gemini":
                return await self._call_gemini(system_prompt, user_prompt, model_override, temp)
            elif target_provider == "openai":
                return await self._call_openai(system_prompt, user_prompt, model_override, temp)
            else:
                return await self._call_gemini(system_prompt, user_prompt, model_override, temp)
        except Exception as primary_error:
            logger.warning(f"Primary provider [{target_provider}] failed: {primary_error}")
            
            if not settings.ENABLE_AUTO_FALLBACK_ON_ERROR:
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

        primary_model = model or settings.GEMINI_MODEL
        # Models to try in order of priority (prioritizing models with fresh quota)
        candidate_models = [primary_model, "gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-flash-latest"]
        # De-duplicate while preserving order
        candidate_models = list(dict.fromkeys(candidate_models))

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

        last_error = None
        for m in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
            gen_config = {
                "temperature": temperature,
                "responseMimeType": "application/json"
            }
            if "2.5" in m or "3.6" in m:
                gen_config["thinkingConfig"] = {"thinkingBudget": 0}

            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": f"{system_prompt}\n\n---\n\n{user_prompt}"}]
                    }
                ],
                "generationConfig": gen_config
            }

            for attempt in range(4):
                try:
                    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                        resp = await client.post(url, json=payload, headers=headers)
                        
                        if resp.status_code == 200:
                            data = resp.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                text_content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                                if text_content:
                                    return text_content
                            raise RuntimeError(f"No valid candidates returned by Gemini ({m})")

                        if resp.status_code == 503:
                            if attempt < 3:
                                logger.warning(f"Gemini model [{m}] temporarily busy (503). Waiting 3s before retry (attempt {attempt+1}/4)...")
                                await asyncio.sleep(3.0)
                                continue
                            else:
                                logger.warning(f"Gemini model [{m}] repeated 503. Switching to next model...")
                                break

                        if resp.status_code == 429:
                            resp_text = resp.text
                            # Check if daily quota is exhausted - only if PerDay is explicitly mentioned
                            if "GenerateRequestsPerDay" in resp_text or "PerDay" in resp_text or "per_day" in resp_text:
                                logger.warning(f"Gemini model [{m}] daily quota exhausted. Switching to next model...")
                                break
                            
                            # Otherwise temporary RPM limit: wait and retry
                            wait_sec = 4.0 * (attempt + 1)
                            try:
                                err_json = resp.json()
                                for d in err_json.get("error", {}).get("details", []):
                                    if "retryDelay" in d:
                                        d_str = d["retryDelay"]
                                        if d_str.endswith("s"):
                                            wait_sec = max(wait_sec, float(d_str.rstrip("s")) + 1.0)
                            except Exception:
                                pass
                            if attempt < 3:
                                logger.warning(f"Gemini ({m}) 429 rate limit. Waiting {wait_sec:.1f}s (attempt {attempt + 1}/4)...")
                                await asyncio.sleep(min(wait_sec, 15.0))
                                continue
                            else:
                                break

                        if resp.status_code == 404:
                            logger.warning(f"Gemini model [{m}] returned 404. Trying next model...")
                            break

                        raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:300]}")
                except Exception as e:
                    last_error = e
                    if attempt >= 3 or "Switching to next model" in str(e):
                        break

        raise RuntimeError(f"All Gemini candidate models failed. Last error: {last_error}")

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
        
        old_gemini = self.gemini_key
        old_openai = self.openai_key
        try:
            if provider == "gemini":
                if api_key: self.gemini_key = api_key
                res = await self._call_gemini(test_sys, test_usr, model=model, temperature=0.1)
            else:
                if api_key: self.openai_key = api_key
                res = await self._call_openai(test_sys, test_usr, model=model, temperature=0.1)
            
            return {"success": True, "provider": provider, "raw_response": res}
        except Exception as e:
            return {"success": False, "provider": provider, "error": str(e)}
        finally:
            self.gemini_key = old_gemini
            self.openai_key = old_openai


llm_router = LLMRouter()
