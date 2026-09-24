import json
import logging
from typing import List, Dict, Any, Optional
from app.services.llm_router import llm_router

logger = logging.getLogger(__name__)


class SpeakerProfiler:
    """Analyzes ASR transcript cues to deduce speaker profiles and relationship matrix."""

    @classmethod
    async def analyze_speakers_and_matrix(
        cls,
        cues_sample: List[Dict[str, Any]],
        source_lang: str = "en"
    ) -> Dict[str, Any]:
        """Analyzes speaker dialogue patterns and produces SpeakerProfiles + RelationshipMatrix."""
        
        # Extract unique speaker tags
        unique_speakers = list(set(cue.get("speaker", "SPEAKER_00") for cue in cues_sample))
        if not unique_speakers:
            unique_speakers = ["SPEAKER_00"]

        # Default fallback structure if LLM analysis is skipped or fails
        fallback_profiles = {}
        for i, spk in enumerate(unique_speakers):
            fallback_profiles[spk] = {
                "speaker_tag": spk,
                "display_name": f"Nhân vật {i+1}",
                "gender": "unknown",
                "age_group": "adult",
                "role": "Người nói chính" if i == 0 else "Người đối thoại",
                "tone": "Lịch sự, tự nhiên",
                "notes": "Tự động trích xuất"
            }

        fallback_matrix = []
        for s1 in unique_speakers:
            for s2 in unique_speakers:
                if s1 != s2:
                    fallback_matrix.append({
                        "source_speaker": s1,
                        "target_speaker": s2,
                        "self_pronoun": "Tôi",
                        "target_pronoun": "Bạn",
                        "relationship_type": "Đồng nghiệp / Bạn bè",
                        "honorific_notes": "Xưng hô trung tính lịch sự"
                    })

        # Try LLM-based deep character profiling if we have sample dialogue
        if len(cues_sample) >= 3:
            try:
                system_prompt = """Bạn là Chuyên gia Phân tích Nhân vật và Quan hệ Xã hội trong Kịch bản Video/Phim.
Nhiệm vụ: Đọc đoạn hội thoại mẫu được cung cấp và suy luận:
1. Danh sách nhân vật (Speaker ID, tên dự đoán, giới tính: male/female/neutral, độ tuổi: child/young_adult/adult/senior, vai trò, giọng điệu).
2. Ma trận xưng hô 2 chiều (ví dụ: Sếp - Nhân viên thì sếp xưng 'Anh/Tôi' gọi 'Em/Linh', nhân viên xưng 'Em' gọi 'Sếp/Anh Alex').

ĐỊNH DẠNG ĐẦU RA BẮT BUỘC (JSON ONLY):
{
  "speakers": {
    "SPEAKER_00": {
      "display_name": "Tên hoặc Vai trò",
      "gender": "male",
      "age_group": "adult",
      "role": "Giám đốc / MC",
      "tone": "Chuyên nghiệp, tự tin"
    }
  },
  "relationships": [
    {
      "source_speaker": "SPEAKER_00",
      "target_speaker": "SPEAKER_01",
      "self_pronoun": "Anh",
      "target_pronoun": "Em",
      "relationship_type": "Cấp trên - Cấp dưới"
    }
  ]
}
"""
                sample_dialogues = [
                    f"{c.get('speaker', 'SPEAKER_00')}: {c.get('text', '')}"
                    for c in cues_sample[:30]
                ]
                user_prompt = f"Ngôn ngữ video: {source_lang}\nĐoạn hội thoại mẫu:\n" + "\n".join(sample_dialogues)

                raw_resp = await llm_router.generate_completion(system_prompt, user_prompt, temperature=0.2)
                
                # Parse JSON
                cleaned = raw_resp.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.split("\n")
                    if lines[0].startswith("```"): lines = lines[1:]
                    if lines and lines[-1].strip().startswith("```"): lines = lines[:-1]
                    cleaned = "\n".join(lines).strip()
                
                parsed = json.loads(cleaned)
                parsed_speakers = parsed.get("speakers", {})
                parsed_rels = parsed.get("relationships", [])

                # Merge with fallbacks to ensure full coverage
                final_profiles = {}
                for spk in unique_speakers:
                    if spk in parsed_speakers:
                        data = parsed_speakers[spk]
                        final_profiles[spk] = {
                            "speaker_tag": spk,
                            "display_name": data.get("display_name", f"Nhân vật {spk}"),
                            "gender": data.get("gender", "unknown"),
                            "age_group": data.get("age_group", "adult"),
                            "role": data.get("role", "Diễn giả"),
                            "tone": data.get("tone", "Tự nhiên"),
                            "notes": "Phân tích tự động bằng AI"
                        }
                    else:
                        final_profiles[spk] = fallback_profiles[spk]

                return {
                    "speakers": final_profiles,
                    "relationships": parsed_rels if parsed_rels else fallback_matrix
                }
            except Exception as e:
                logger.warning(f"LLM Speaker Profiling failed, falling back to default matrix: {e}")

        return {
            "speakers": fallback_profiles,
            "relationships": fallback_matrix
        }


speaker_profiler = SpeakerProfiler()
