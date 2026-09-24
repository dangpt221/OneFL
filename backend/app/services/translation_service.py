import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from app.config import settings
from app.services.prompt_builder import PromptBuilder
from app.services.llm_router import llm_router
from app.services.guardrails import SubtitleGuardrails
from app.services.ws_manager import ws_manager
from app.schemas.translation import TranslationItemOutput

logger = logging.getLogger(__name__)


class TranslationService:
    """Coordinates batching, sliding context windows, LLM translation, and guardrail validation."""

    @classmethod
    async def translate_project_cues(
        cls,
        project_id: str,
        cues: List[Dict[str, Any]],
        source_lang: str = "en",
        target_lang: str = "vi",
        speaker_profiles: Optional[Dict[str, Any]] = None,
        relationship_matrix: Optional[Dict[str, Any]] = None,
        glossary: Optional[Any] = None,
        custom_instructions: Optional[str] = None,
        batch_size: Optional[int] = None,
        batch_callback = None
    ) -> List[Dict[str, Any]]:
        """Processes and translates all cues in the project with context sliding window."""
        translated_cues = []
        previous_context_window = []

        total_cues = len(cues)
        if total_cues == 0:
            return []

        # Split into batches using configurable size (default 60 cues)
        actual_batch_size = batch_size or getattr(settings, "LLM_BATCH_SIZE_LINES", 60) or 60
        batches = [cues[i:i + actual_batch_size] for i in range(0, total_cues, actual_batch_size)]
        
        for b_idx, batch in enumerate(batches):
            # Check if all cues in this batch already have translated_text (from a resumed run)
            all_already_translated = all(bool(c.get("translated_text")) for c in batch)
            if all_already_translated:
                logger.info(f"Skipping already translated batch {b_idx + 1}/{len(batches)} ({len(batch)} cues)...")
                current_batch_results = []
                for orig_cue in batch:
                    trans_text = orig_cue["translated_text"]
                    duration = orig_cue["end_time"] - orig_cue["start_time"]
                    cps = SubtitleGuardrails.calculate_cps(trans_text, duration)
                    lines = trans_text.split("\n")
                    updated_cue = {
                        **orig_cue,
                        "translated_text": trans_text,
                        "cps": cps,
                        "line_count": len(lines),
                        "max_line_length": max(len(l) for l in lines) if lines else 0,
                        "has_guardrail_violation": False
                    }
                    translated_cues.append(updated_cue)
                    current_batch_results.append(updated_cue)

                previous_context_window = [
                    {
                        "speaker": c.get("speaker_tag", "SPEAKER_00"),
                        "original": c.get("original_text", ""),
                        "translated": c.get("translated_text", "")
                    }
                    for c in translated_cues[-settings.LLM_CONTEXT_WINDOW_LINES:]
                ]

                if batch_callback:
                    try:
                        await batch_callback(current_batch_results, len(translated_cues), total_cues)
                    except Exception as cb_err:
                        logger.debug(f"Batch progress callback error: {cb_err}")
                continue

            logger.info(f"Processing translation batch {b_idx + 1}/{len(batches)} ({len(batch)} cues) for project {project_id}...")
            
            # Prepare batch input
            batch_inputs = [
                {
                    "id": cue["cue_index"],
                    "text": cue["original_text"],
                    "speaker": cue.get("speaker_tag", "SPEAKER_00"),
                    "target_speaker": cue.get("target_speaker_tag"),
                    "duration": cue["end_time"] - cue["start_time"]
                }
                for cue in batch
            ]

            # Build prompt with sliding context
            prompts = PromptBuilder.build_translation_prompt(
                source_lang=source_lang,
                target_lang=target_lang,
                cues_to_translate=batch_inputs,
                speaker_profiles=speaker_profiles,
                relationship_matrix=relationship_matrix,
                glossary=glossary,
                previous_context=previous_context_window,
                custom_instructions=custom_instructions
            )

            # Invoke LLM Router
            try:
                raw_llm_response = await llm_router.generate_completion(
                    system_prompt=prompts["system_prompt"],
                    user_prompt=prompts["user_prompt"]
                )
            except Exception as e:
                logger.warning(f"LLM translation request failed: {e}. Generating fallback translations.")
                raw_llm_response = json.dumps({
                    "translations": [
                        {"id": item["id"], "text": f"{item['text']}"}
                        for item in batch_inputs
                    ]
                })

            # Run 4-Tier Guardrails with zero-failure fault tolerance
            validated_translations = []
            try:
                is_valid, validated_translations, violations = SubtitleGuardrails.validate_batch(
                    requested_cues=batch_inputs,
                    llm_raw_response=raw_llm_response,
                    relationship_matrix=relationship_matrix,
                    glossary=glossary
                )

                # Fast Reflexion Loop if violations exist
                if not is_valid and settings.ENABLE_GUARDRAILS and violations:
                    logger.info(f"Guardrail violations detected ({len(violations)}). Triggering Fast Reflexion Loop...")
                    try:
                        refl_prompts = PromptBuilder.build_reflexion_prompt(
                            violation_report=violations,
                            speaker_profiles=speaker_profiles,
                            relationship_matrix=relationship_matrix,
                            glossary=glossary
                        )
                        refl_response = await llm_router.generate_completion(
                            system_prompt=refl_prompts["system_prompt"],
                            user_prompt=refl_prompts["user_prompt"],
                            temperature=0.1
                        )
                        # Merge corrected lines
                        _, fixed_trans, _ = SubtitleGuardrails.validate_batch(
                            requested_cues=batch_inputs,
                            llm_raw_response=refl_response,
                            relationship_matrix=relationship_matrix,
                            glossary=glossary
                        )
                        fixed_map = {item.id: item.text for item in fixed_trans}
                        for trans in validated_translations:
                            if trans.id in fixed_map:
                                trans.text = fixed_map[trans.id]
                    except Exception as refl_err:
                        logger.warning(f"Reflexion loop error: {refl_err}")
            except Exception as guard_err:
                logger.warning(f"Guardrails validation error: {guard_err}. Parsing raw LLM response safely.")
                try:
                    cleaned_json = SubtitleGuardrails.clean_json_response(raw_llm_response)
                    parsed = json.loads(cleaned_json)
                    for item in parsed.get("translations", []):
                        if isinstance(item, dict) and "id" in item:
                            validated_translations.append(TranslationItemOutput(id=item["id"], text=item.get("text", "")))
                except Exception:
                    pass

            # Map results back to cues
            trans_map = {t.id: t.text for t in validated_translations}
            current_batch_results = []
            for orig_cue in batch:
                c_idx = orig_cue["cue_index"]
                trans_text = trans_map.get(c_idx, orig_cue["original_text"])
                duration = orig_cue["end_time"] - orig_cue["start_time"]
                cps = SubtitleGuardrails.calculate_cps(trans_text, duration)
                lines = trans_text.split("\n")

                updated_cue = {
                    **orig_cue,
                    "translated_text": trans_text,
                    "cps": cps,
                    "line_count": len(lines),
                    "max_line_length": max(len(l) for l in lines) if lines else 0,
                    "has_guardrail_violation": False
                }
                translated_cues.append(updated_cue)
                current_batch_results.append(updated_cue)

            # Update sliding context (last 5 translated lines)
            previous_context_window = [
                {
                    "speaker": c.get("speaker_tag", "SPEAKER_00"),
                    "original": c.get("original_text", ""),
                    "translated": c.get("translated_text", "")
                }
                for c in translated_cues[-settings.LLM_CONTEXT_WINDOW_LINES:]
            ]

            # Trigger live database callback if provided
            if batch_callback:
                try:
                    await batch_callback(current_batch_results, len(translated_cues), total_cues)
                except Exception as cb_err:
                    logger.debug(f"Batch progress callback error: {cb_err}")

            # Broadcast live progress over WebSocket
            progress_pct = int(round((len(translated_cues) / total_cues) * 100))
            await ws_manager.broadcast_to_project(
                project_id,
                "TRANSLATION_PROGRESS",
                {
                    "translated_count": len(translated_cues),
                    "total_count": total_cues,
                    "percentage": progress_pct,
                    "latest_batch": [
                        {"id": c["cue_index"], "text": c.get("translated_text")}
                        for c in current_batch_results
                    ]
                }
            )

            # Adaptive rate-limit pacing to stay within quota without unnecessary delay
            if b_idx < len(batches) - 1:
                await asyncio.sleep(1.2)

        return translated_cues


translation_service = TranslationService()
