import re
import json
import math
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

        # Preserve every word; validation requests a shorter translation.
        return "\n".join(wrapped_lines)

    @classmethod
    def calculate_cps(cls, text: str, duration_seconds: float) -> float:
        """Calculate Characters Per Second (excluding newlines)."""
        if not math.isfinite(duration_seconds) or duration_seconds <= 0:
            return float("inf")
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
            if not isinstance(parsed, dict) or not isinstance(parsed.get("translations"), list):
                raise ValueError("Expected an object with a translations array")
            raw_translations = parsed["translations"]
        except Exception as e:
            violations.append({
                "tier": 1,
                "type": "JSON_SYNTAX_ERROR",
                "message": f"Failed to parse LLM JSON: {str(e)}",
                "raw_sample": cleaned_json[:200]
            })
            return False, [], violations

        glossary_map = {}
        entries = glossary.items() if isinstance(glossary, dict) else ((item.get('source_term') or item.get('source'), item) for item in (glossary or []))
        entries = sorted(entries, key=lambda pair: 0 if isinstance(pair[1], dict) and pair[1].get('priority') == 'high' else 1)
        for src, item in entries:
            target = (item.get('target_term') or item.get('target') or '') if isinstance(item, dict) else str(item)
            sensitive = isinstance(item, dict) and str(item.get('case_sensitive', 'false')).lower() == 'true'
            if src and target:
                glossary_map.setdefault(str(src).strip(), (str(target).strip(), sensitive))

        matrix = cls.normalize_relationships(relationship_matrix)
        cue_map = {cue["id"]: cue for cue in requested_cues}
        if len(cue_map) != len(requested_cues):
            raise ValueError("Requested cue IDs must be unique")
        parsed_map = {}
        for item in raw_translations:
            if not isinstance(item, dict) or type(item.get("id")) is not int or not isinstance(item.get("text"), str):
                violations.append({"tier": 1, "type": "INVALID_TRANSLATION_SCHEMA", "message": "Each result requires integer id and string text"})
                continue
            cue_id = item["id"]
            if cue_id in parsed_map or cue_id not in cue_map:
                violations.append({"tier": 1, "cue_id": cue_id, "type": "UNEXPECTED_OR_DUPLICATE_ID", "message": "Output IDs must match input exactly"})
            parsed_map[cue_id] = item["text"]

        # Check for missing IDs
        for cue_id in cue_map:
            if cue_id not in parsed_map:
                violations.append({
                    "tier": 1,
                    "cue_id": cue_id,
                    "type": "MISSING_TRANSLATION_ID",
                    "message": f"Translation for cue ID {cue_id} was missing from output.",
                    "source_text": cue_map[cue_id].get("text", ""),
                    "duration": cue_map[cue_id].get("duration")
                })

        for cue_id, orig_cue in cue_map.items():
            trans_text = parsed_map.get(cue_id, "").strip()
            if not trans_text:
                violations.append({"tier": 1, "cue_id": cue_id, "type": "EMPTY_TRANSLATION", "message": "Translation must not be empty", "source_text": orig_cue.get("text", "")})
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
            if not target_speaker:
                targets = [key.split("_to_", 1)[1] for key in matrix if key.startswith(f"{speaker}_to_")]
                target_speaker = targets[0] if len(targets) == 1 else None
            if settings.ENABLE_GUARDRAILS and settings.GUARDRAIL_CHECK_PRONOUN_CONSISTENCY and matrix and target_speaker:
                rel_key = f"{speaker}_to_{target_speaker}"
                if rel_key in matrix:
                    rel_rules = matrix[rel_key]
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

            if settings.ENABLE_GUARDRAILS and len(lines) > settings.MAX_SUBTITLE_LINES:
                violations.append({"tier": 4, "cue_id": cue_id, "type": "TOO_MANY_LINES", "message": "Subtitle needs shortening without losing meaning", "current_text": formatted_text, "source_text": orig_cue.get("text", ""), "duration": duration})

            if settings.ENABLE_GUARDRAILS and max_line_len > settings.MAX_SUBTITLE_LINE_LENGTH:
                violations.append({
                    "tier": 4,
                    "cue_id": cue_id,
                    "type": "LINE_TOO_LONG",
                    "message": f"Line length {max_line_len} exceeds limit of {settings.MAX_SUBTITLE_LINE_LENGTH}.",
                    "current_text": formatted_text,
                    "duration": duration
                })

            if settings.ENABLE_GUARDRAILS and cps > settings.MAX_CPS:
                violations.append({
                    "tier": 4,
                    "cue_id": cue_id,
                    "type": "CPS_TOO_HIGH",
                    "message": f"Reading speed {cps} CPS exceeds max {settings.MAX_CPS} CPS.",
                    "current_text": formatted_text,
                    "duration": duration
                })

            # TIER 3: Glossary & Term Enforcement Guard
            if settings.ENABLE_GUARDRAILS and settings.GUARDRAIL_STRICT_GLOSSARY and glossary_map:
                orig_text_lower = orig_cue.get("text", "").lower()
                normalized_trans_lower = " ".join(formatted_text.lower().split())
                import string
                clean_trans_lower = normalized_trans_lower.translate(str.maketrans('', '', string.punctuation))
                padded_clean_trans = f" {clean_trans_lower} "

                for src_term, (tgt_term, sensitive) in glossary_map.items():
                    source = orig_cue.get('text', '')
                    target = ' '.join(formatted_text.split())
                    def term_present(term, text):
                        pattern = re.escape(term)
                        # Latin terms must match words, not substrings (AI/chair).
                        if term and term[0].isascii() and term[0].isalnum():
                            pattern = r'(?<!\w)' + pattern
                        if term and term[-1].isascii() and term[-1].isalnum():
                            pattern += r'(?!\w)'
                        return re.search(pattern, text, flags=0 if sensitive else re.IGNORECASE) is not None
                    if term_present(src_term, source):
                        if not term_present(' '.join(tgt_term.split()), target):
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

    @staticmethod
    def normalize_relationships(matrix: Optional[Any]) -> Dict[str, Dict[str, str]]:
        """Normalize DB/API relationships into keyed pronoun rules."""
        result = {}
        entries = matrix.items() if isinstance(matrix, dict) else enumerate(matrix or [])
        for key, value in entries:
            if not isinstance(value, dict):
                raise ValueError("Relationship entries must be objects")
            source, target = value.get("source_speaker"), value.get("target_speaker")
            if not source or not target:
                if not isinstance(key, str) or "_to_" not in key:
                    raise ValueError("Relationship requires source and target")
                source, target = key.split("_to_", 1)
            result[f"{source}_to_{target}"] = {
                "self": value.get("self_pronoun") or value.get("self") or "",
                "target": value.get("target_pronoun") or value.get("target") or "",
            }
        return result
