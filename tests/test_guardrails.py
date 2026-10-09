import pytest
from app.services.guardrails import SubtitleGuardrails


def test_clean_json_response():
    raw_markdown = "```json\n{\"translations\": [{\"id\": 1, \"text\": \"Xin chào\"}]}\n```"
    cleaned = SubtitleGuardrails.clean_json_response(raw_markdown)
    assert cleaned.startswith("{")
    assert cleaned.endswith("}")
    assert "```" not in cleaned


def test_auto_wrap_text_short():
    text = "Câu ngắn gọn."
    wrapped = SubtitleGuardrails.auto_wrap_text(text, max_chars_per_line=40, max_lines=2)
    assert wrapped == "Câu ngắn gọn."


def test_auto_wrap_text_long():
    text = "Đây là một câu thoại rất dài vượt quá giới hạn ký tự chuẩn của một dòng phụ đề bình thường."
    wrapped = SubtitleGuardrails.auto_wrap_text(text, max_chars_per_line=35, max_lines=2)
    lines = wrapped.split("\n")
    assert len(lines) <= 2
    for line in lines:
        assert len(line) <= 45  # Reasonable wrapping boundary


def test_calculate_cps():
    text = "Xin chào các bạn"  # 16 chars
    cps = SubtitleGuardrails.calculate_cps(text, duration_seconds=2.0)
    assert cps == 8.0


def test_validate_batch_glossary_enforcement():
    requested = [
        {"id": 1, "text": "We need to fix the database cache.", "duration": 3.0}
    ]
    raw_llm = '{"translations": [{"id": 1, "text": "Chúng ta cần sửa bộ nhớ đệm cơ sở dữ liệu."}]}'
    glossary = {"database": "cơ sở dữ liệu"}
    
    is_valid, translations, violations = SubtitleGuardrails.validate_batch(
        requested_cues=requested,
        llm_raw_response=raw_llm,
        glossary=glossary
    )
    assert is_valid is True
    assert len(translations) == 1
    assert "cơ sở dữ liệu" in " ".join(translations[0].text.split())

def test_validate_batch_pronoun_enforcement():
    requested = [
        {
            "id": 1, 
            "text": "Hey what are you doing?", 
            "duration": 3.0,
            "speaker": "SPEAKER_00",
            "target_speaker": "SPEAKER_01"
        }
    ]
    # LLM translated it with forbidden pronouns "mày"
    raw_llm = '{"translations": [{"id": 1, "text": "Ê mày đang làm gì đấy?"}]}'
    
    relationship_matrix = {
        "SPEAKER_00_to_SPEAKER_01": {
            "self": "Anh",
            "target": "Em"
        }
    }
    
    is_valid, translations, violations = SubtitleGuardrails.validate_batch(
        requested_cues=requested,
        llm_raw_response=raw_llm,
        relationship_matrix=relationship_matrix
    )
    
    assert is_valid is False
    assert len(violations) == 1
    assert violations[0]["type"] == "PRONOUN_MISMATCH"
    assert "mày" in violations[0]["message"]
    
    # Now test with correct pronouns
    raw_llm_correct = '{"translations": [{"id": 1, "text": "Ê em đang làm gì đấy?"}]}'
    is_valid_2, trans_2, vio_2 = SubtitleGuardrails.validate_batch(
        requested_cues=requested,
        llm_raw_response=raw_llm_correct,
        relationship_matrix=relationship_matrix
    )
    assert is_valid_2 is True
    assert len(vio_2) == 0
