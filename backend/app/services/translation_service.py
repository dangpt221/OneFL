"""Batch translation with durable callbacks and fail-closed validation."""
import json
from typing import Any, Callable, Optional
from app.config import settings
from app.services.guardrails import SubtitleGuardrails
from app.services.llm_router import llm_router
from app.services.prompt_builder import PromptBuilder
from app.services.ws_manager import ws_manager


class TranslationService:
    @classmethod
    async def translate_project_cues(
        cls, project_id: str, cues: list[dict[str, Any]], source_lang: str = "en",
        target_lang: str = "vi", speaker_profiles: Optional[dict] = None,
        relationship_matrix: Optional[Any] = None, glossary: Optional[Any] = None,
        custom_instructions: Optional[str] = None, batch_size: Optional[int] = None,
        batch_callback: Optional[Callable] = None, force_reprocess: bool = False,
        model_override: Optional[str] = None, temperature: Optional[float] = None,
        preserve_edited: bool = True, video_context: Optional[str] = None,
        video_path: Optional[Any] = None,
    ) -> list[dict[str, Any]]:
        size = batch_size or settings.LLM_BATCH_SIZE_LINES
        if size <= 0:
            raise ValueError("batch_size must be positive")
        if len({c['cue_index'] for c in cues}) != len(cues):
            raise ValueError("Cue indices must be unique")
        translated = []
        context = []
        for offset in range(0, len(cues), size):
            batch = cues[offset:offset + size]
            def as_input(c):
                return {'id': c['cue_index'], 'text': c['original_text'],
                        'speaker': c.get('speaker_tag', 'SPEAKER_00'), 'target_speaker': c.get('target_speaker_tag'),
                        'duration': c['end_time'] - c['start_time']}
            reusable = set()
            for c in batch:
                if c.get('translated_text'):
                    valid, _, _ = SubtitleGuardrails.validate_batch([as_input(c)], json.dumps({'translations': [{'id': c['cue_index'], 'text': c['translated_text']}]}), relationship_matrix, glossary)
                    if valid:
                        reusable.add(c['cue_index'])
            pending = [c for c in batch if not (
                (preserve_edited and c.get('is_edited') and c.get('translated_text'))
                or (not force_reprocess and c['cue_index'] in reusable)
            )]
            pending_ids = {c['cue_index'] for c in pending}
            inputs = [as_input(c) for c in pending]
            result_map = {}
            if inputs:
                context_for_batch = video_context
                if settings.ENABLE_VISUAL_CONTEXT:
                    if not video_path:
                        raise ValueError('Visual translation requires a source video path')
                    from pathlib import Path
                    from app.services.visual_context import visual_context_service
                    times = [pending[0]['start_time'], pending[len(pending) // 2]['start_time'], pending[-1]['start_time']]
                    observed = await visual_context_service.describe_video(Path(video_path), times)
                    context_for_batch = '\n'.join(filter(None, [video_context, observed]))
                prompts = PromptBuilder.build_translation_prompt(
                    source_lang=source_lang, target_lang=target_lang,
                    cues_to_translate=inputs, speaker_profiles=speaker_profiles,
                    relationship_matrix=relationship_matrix, glossary=glossary,
                    previous_context=context, custom_instructions=custom_instructions,
                    video_context=context_for_batch,
                )
                raw = await llm_router.generate_completion(
                    **prompts, model_override=model_override, temperature=temperature,
                )
                valid, items, violations = SubtitleGuardrails.validate_batch(inputs, raw, relationship_matrix, glossary)
                result_map = {t.id: t.text for t in items}
                for _ in range(settings.GUARDRAIL_MAX_REFLEXION_RETRIES):
                    if valid:
                        break
                    repair = PromptBuilder.build_reflexion_prompt(
                        [{**v, 'requested_cues': inputs} if 'cue_id' not in v else v for v in violations],
                        speaker_profiles, relationship_matrix, glossary,
                    )
                    repaired_raw = await llm_router.generate_completion(
                        **repair, model_override=model_override, temperature=0.1,
                    )
                    # Merge repairs even when the initial response had no valid IDs.
                    _, repaired, repair_violations = SubtitleGuardrails.validate_batch(inputs, repaired_raw, relationship_matrix, glossary)
                    structural_errors = [v for v in repair_violations if v['type'] in ('INVALID_TRANSLATION_SCHEMA', 'UNEXPECTED_OR_DUPLICATE_ID', 'JSON_SYNTAX_ERROR')]
                    if structural_errors:
                        violations = repair_violations
                        continue
                    result_map.update({t.id: t.text for t in repaired})
                    merged = json.dumps({"translations": [{"id": i, "text": text} for i, text in result_map.items()]})
                    valid, items, violations = SubtitleGuardrails.validate_batch(inputs, merged, relationship_matrix, glossary)
                    result_map = {t.id: t.text for t in items}
                if not valid:
                    raise RuntimeError(f"Guardrail validation failed at cue {batch[0]['cue_index']}: {json.dumps(violations, ensure_ascii=False)}")
            completed = []
            for c in batch:
                text = result_map[c['cue_index']] if c['cue_index'] in pending_ids else c['translated_text']
                _, _, row_violations = SubtitleGuardrails.validate_batch([as_input(c)], json.dumps({'translations': [{'id': c['cue_index'], 'text': text}]}), relationship_matrix, glossary)
                lines = text.splitlines() or ['']
                completed.append({**c, 'translated_text': text,
                                  'cps': SubtitleGuardrails.calculate_cps(text, c['end_time'] - c['start_time']),
                                  'line_count': len(lines), 'max_line_length': max(map(len, lines)),
                                  'has_guardrail_violation': bool(row_violations),
                                  'violation_notes': json.dumps(row_violations, ensure_ascii=False) if row_violations else None})
            translated.extend(completed)
            if batch_callback:
                await batch_callback(completed, len(translated), len(cues))
            context = [{"speaker": c.get('speaker_tag'), "original": c['original_text'], "translated": c['translated_text']}
                       for c in translated[-max(1, settings.LLM_CONTEXT_WINDOW_LINES):]]
            await ws_manager.broadcast_to_project(project_id, 'TRANSLATION_PROGRESS', {
                'translated_count': len(translated), 'total_count': len(cues),
                'progress': 60 + int(len(translated) / len(cues) * 20),
                'latest_batch': [{'id': c['cue_index'], 'text': c['translated_text']} for c in completed],
            })
        return translated


translation_service = TranslationService()
