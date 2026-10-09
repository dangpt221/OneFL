import re
import json
from typing import List, Dict, Any, Tuple, Optional
from app.config import settings
from app.schemas.translation import TranslationItemOutput, GuardrailCheckResult


class SubtitleGuardrails:
    """4-Tier Guardrail Pipeline for Subtitle Quality Control."""

    @staticmethod
    def clean_json_response(raw_response: str) -> str:
        """Strip markdown codeblocks (```json ... ```) and leading/trailing whitespace."""
        text = raw_response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    @staticmethod
    def auto_wrap_text(text: str, max_chars_per_line: int = 40, max_lines: int = 2) -> str:
        """Intelligently wraps subtitle text into balanced lines without breaking mid-word."""
        text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        # If already <= max_lines and each line <= max_chars_per_line, return as is
        if len(lines) <= max_lines and all(len(l) <= max_chars_per_line for l in lines):
            return "\n".join(lines)
        
        # Merge everything into single sentence first
        unified = " ".join(" ".join(lines).split())
        if len(unified) <= max_chars_per_line:
            return unified

        words = unified.split()
        if not words:
            return ""

        wrapped_lines = []
        current_line = []
        current_len = 0

        for word in words:
            needed = len(word) + (1 if current_line else 0)
            if current_len + needed <= max_chars_per_line:
                current_line.append(word)
                current_len += needed
            else:
                if current_line:
                    wrapped_lines.append(" ".join(current_line))
                current_line = [word]
                current_len = len(word)
        if current_line:
            wrapped_lines.append(" ".join(current_line))

        return "\n".join(wrapped_lines[:max_lines])

    @classmethod
    def calculate_cps(cls, text: str, duration_seconds: float) -> float:
        """Calculate Characters Per Second (excluding newlines)."""
        if duration_seconds <= 0.05:
            return 0.0
        cleaned = text.replace("\n", " ").strip()
        return round(len(cleaned) / duration_seconds, 2)

    @classmethod
    def validate_batch(
        cls,
        requested_cues: List[Dict[str, Any]],
        llm_raw_response: str,
        relationship_matrix: Optional[Dict[str, Any]] = None,
        glossary: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, List[TranslationItemOutput], List[Dict[str, Any]]]:
        """Runs the 4-Tier Guardrail Pipeline against LLM output.
        Returns (is_valid, validated_translations, violations_list).
        """
        violations = []
        translations: List[TranslationItemOutput] = []

        # TIER 1: Format & Schema Guard
        cleaned_json = cls.clean_json_response(llm_raw_response)
        try:
            parsed = json.loads(cleaned_json)
            raw_translations = parsed.get("translations", [])
        except Exception as e:
            violations.append({
                "tier": 1,
                "type": "JSON_SYNTAX_ERROR",
                "message": f"Failed to parse LLM JSON: {str(e)}",
                "raw_sample": cleaned_json[:200]
            })
            return False, [], violations

        # Normalize glossary into mapping {source_term: target_term} safely
        glossary_map: Dict[str, str] = {}
        if isinstance(glossary, dict):
            for k, v in glossary.items():
                if isinstance(v, dict):
                    tgt = v.get("target_term") or v.get("target") or ""
                else:
                    tgt = str(v)
                if k and tgt:
                    glossary_map[str(k).strip()] = str(tgt).strip()
        elif isinstance(glossary, list):
            for item in glossary:
                if isinstance(item, dict):
                    src = item.get("source_term") or item.get("source") or ""
                    tgt = item.get("target_term") or item.get("target") or ""
                    if src and tgt:
                        glossary_map[str(src).strip()] = str(tgt).strip()

        cue_map = {cue["id"]: cue for cue in requested_cues}
        parsed_map = {item.get("id"): item.get("text", "") for item in raw_translations if isinstance(item, dict)}

        # Check for missing IDs
        for cue_id in cue_map:
            if cue_id not in parsed_map:
                violations.append({
                    "tier": 1,
                    "cue_id": cue_id,
                    "type": "MISSING_TRANSLATION_ID",
                    "message": f"Translation for cue ID {cue_id} was missing from output."
                })

        for cue_id, orig_cue in cue_map.items():
            trans_text = parsed_map.get(cue_id, "").strip()
            if not trans_text:
                continue

            duration = orig_cue.get("duration", 2.0)
            speaker = orig_cue.get("speaker", "SPEAKER_00")
            target_speaker = orig_cue.get("target_speaker")

            # Format text first for both Tier 2 & Tier 4
            formatted_text = cls.auto_wrap_text(
                trans_text,
                max_chars_per_line=settings.MAX_SUBTITLE_LINE_LENGTH,
                max_lines=settings.MAX_SUBTITLE_LINES
            )
            normalized_trans_lower = " ".join(formatted_text.lower().split())

            # TIER 2: Pronoun & Gender Consistency Guard
            if relationship_matrix and target_speaker:
                rel_key = f"{speaker}_to_{target_speaker}"
                if rel_key in relationship_matrix:
                    rel_rules = relationship_matrix[rel_key]
                    allowed_self = [p.strip().lower() for p in rel_rules.get("self", "").split("/") if p.strip()]
                    allowed_target = [p.strip().lower() for p in rel_rules.get("target", "").split("/") if p.strip()]
                    allowed_all = set(allowed_self + allowed_target)
                    
                    strict_pronouns = [
                        "mày", "tao", "ngươi", "ta", "anh", "em", "chị", "tôi", "ông", "bà", "cô", "chú"
                    ]
                    
                    # Remove punctuation to better match exact words
                    import string
                    clean_text = normalized_trans_lower.translate(str.maketrans('', '', string.punctuation))
                    # Protect compounds like 'chúng ta' and 'người ta' from false-matching singular archaic 'ta'
                    clean_text = clean_text.replace("chúng ta", "__chung_ta__").replace("người ta", "__nguoi_ta__")
                    padded_text = f" {clean_text} "
                    
                    used_strict = [p for p in strict_pronouns if f" {p} " in padded_text]
                    
                    for p in used_strict:
                        if p not in allowed_all:
                            violations.append({
                                "tier": 2,
                                "cue_id": cue_id,
                                "type": "PRONOUN_MISMATCH",
                                "message": f"Sử dụng đại từ '{p}' không khớp với relationship_matrix (Cho phép: {', '.join(allowed_all)}).",
                                "current_text": formatted_text
                            })

            # TIER 4: Physical Subtitle Limits & Auto-wrap
            lines = formatted_text.split("\n")
            max_line_len = max(len(l) for l in lines) if lines else 0
            cps = cls.calculate_cps(formatted_text, duration)

            if max_line_len > settings.MAX_SUBTITLE_LINE_LENGTH + 5:  # Tolerance buffer
                violations.append({
                    "tier": 4,
                    "cue_id": cue_id,
                    "type": "LINE_TOO_LONG",
                    "message": f"Line length {max_line_len} exceeds limit of {settings.MAX_SUBTITLE_LINE_LENGTH}.",
                    "current_text": formatted_text,
                    "duration": duration
                })

            if cps > settings.MAX_CPS + 4:  # Tolerance buffer
                violations.append({
                    "tier": 4,
                    "cue_id": cue_id,
                    "type": "CPS_TOO_HIGH",
                    "message": f"Reading speed {cps} CPS exceeds max {settings.MAX_CPS} CPS.",
                    "current_text": formatted_text,
                    "duration": duration
                })

            # TIER 3: Glossary & Term Enforcement Guard
            if glossary_map:
                orig_text_lower = orig_cue.get("text", "").lower()
                normalized_trans_lower = " ".join(formatted_text.lower().split())
                import string
                clean_trans_lower = normalized_trans_lower.translate(str.maketrans('', '', string.punctuation))
                padded_clean_trans = f" {clean_trans_lower} "

                for src_term, tgt_term in glossary_map.items():
                    if src_term.lower() in orig_text_lower:
                        normalized_tgt = " ".join(tgt_term.lower().split())
                        clean_tgt = normalized_tgt.translate(str.maketrans('', '', string.punctuation))
                        # Match either in normalized or clean translation
                        if normalized_tgt not in normalized_trans_lower and f" {clean_tgt} " not in padded_clean_trans and clean_tgt not in clean_trans_lower:
                            violations.append({
                                "tier": 3,
                                "cue_id": cue_id,
                                "type": "GLOSSARY_MISMATCH",
                                "message": f"Expected term '{tgt_term}' for '{src_term}' was not found in translation.",
                                "current_text": formatted_text
                            })

            translations.append(TranslationItemOutput(id=cue_id, text=formatted_text))

        is_valid = len(violations) == 0
        return is_valid, translations, violations
