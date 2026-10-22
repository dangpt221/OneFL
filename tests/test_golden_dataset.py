import json
import os
import pytest
from pathlib import Path
from app.services.guardrails import SubtitleGuardrails
from app.services.prompt_builder import PromptBuilder
from app.services.subtitle_generator import SubtitleGenerator, format_timestamp_ass, format_timestamp_srt

DATASET_PATH = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "translation_cases.json"
FRONTEND_SAMPLE_PATH = Path("frontend/src/data/golden_dataset_sample.json")


@pytest.fixture(scope="session")
def golden_dataset():
    assert DATASET_PATH.exists(), f"Golden dataset file not found at {DATASET_PATH}"
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def test_golden_dataset_structure_and_count(golden_dataset):
    """Verify total count, schema completeness, and language distribution of Golden Dataset."""
    assert len(golden_dataset) >= 12
    assert len({tuple(c['original_text'] for c in item['input_cues']) for item in golden_dataset}) == len(golden_dataset)

    lang_counts = {"en": 0, "zh": 0, "ja": 0, "ko": 0}
    required_keys = [
        "id", "source_language", "target_language", "category", "scene_title",
        "video_context", "speaker_profiles", "relationship_matrix", "glossary",
        "input_cues", "ground_truth_translation", "guardrail_stress_type", "test_flow_targets"
    ]

    for item in golden_dataset:
        for k in required_keys:
            assert k in item, f"Missing key '{k}' in item #{item.get('id')}"

        lang = item["source_language"]
        assert lang in lang_counts, f"Unexpected language: {lang}"
        lang_counts[lang] += 1

        assert len(item["input_cues"]) >= 1
        assert len(item["ground_truth_translation"]) == len(item["input_cues"])
        assert len(item["video_context"]) > 10, "Video context description must be informative"

    assert all(count >= 2 for count in lang_counts.values())


def test_golden_dataset_guardrails_validation(golden_dataset):
    """Positive references pass; short-window references must be rejected for CPS."""
    # Exercise every independent case with explicit, reviewed expected outcomes.
    sample_items = golden_dataset
    total_violations = 0

    for item in sample_items:
        requested_cues = [
            {
                "id": cue["cue_index"],
                "text": cue["original_text"],
                "duration": cue["duration"],
                "speaker": cue["speaker_tag"],
                "target_speaker": cue.get("target_speaker_tag")
            }
            for cue in item["input_cues"]
        ]

        raw_llm = json.dumps({"translations": item["ground_truth_translation"]})

        is_valid, translations, violations = SubtitleGuardrails.validate_batch(
            requested_cues=requested_cues,
            llm_raw_response=raw_llm,
            relationship_matrix=item["relationship_matrix"],
            glossary=item["glossary"]
        )

        assert len(translations) == len(requested_cues)
        originals = {t['id']: t['text'] for t in item['ground_truth_translation']}
        for translated in translations:
            assert translated.text.split() == originals[translated.id].split(), 'QC must preserve all reference words'
        assert {v['type'] for v in violations} == set(item['expected_rule_violations'])
        assert is_valid is (not item['expected_rule_violations'])


def test_prompt_builder_integration_with_golden_case(golden_dataset):
    """Verify that PromptBuilder correctly incorporates video_context, language rules, and glossaries."""
    sample = golden_dataset[0]  # English tech case
    prompts = PromptBuilder.build_translation_prompt(
        source_lang=sample["source_language"],
        target_lang="vi",
        cues_to_translate=[
            {
                "id": c["cue_index"],
                "text": c["original_text"],
                "speaker": c["speaker_tag"],
                "duration": c["duration"]
            }
            for c in sample["input_cues"]
        ],
        speaker_profiles=sample["speaker_profiles"],
        relationship_matrix=sample["relationship_matrix"],
        glossary=sample["glossary"],
        video_context=sample["video_context"]
    )

    sys_prompt = prompts["system_prompt"]
    user_prompt = prompts["user_prompt"]

    # Verify visual context and rules
    assert "VIDEO-GROUNDED TRANSLATION" in sys_prompt
    assert "QUY TẮC DỊCH TIẾNG ANH CHUYÊN SÂU" in sys_prompt
    assert "VIDEO VISUAL CONTEXT" in user_prompt
    assert sample["video_context"] in user_prompt
    assert "microservices" in user_prompt.lower()


def test_subtitle_generator_with_golden_cues(golden_dataset):
    """Verify timestamps and ASS/SRT styling functions on golden dataset cues."""
    sample = golden_dataset[10]
    cue = sample["input_cues"][0]

    ass_ts = format_timestamp_ass(cue["start_time"])
    srt_ts = format_timestamp_srt(cue["start_time"])

    # ASS format: H:MM:SS.cc
    assert ":" in ass_ts
    assert "." in ass_ts
    # SRT format: HH:MM:SS,mmm
    assert ":" in srt_ts
    assert "," in srt_ts


def test_frontend_sample_sync():
    """Verify that the frontend sample dataset is present, valid, and populated."""
    assert FRONTEND_SAMPLE_PATH.exists()
    with open(FRONTEND_SAMPLE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) >= 12
    assert {item['source_language'] for item in data} == {'en', 'zh', 'ja', 'ko'}
    assert data[0]["source_language"] == "en"
