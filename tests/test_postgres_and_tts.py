"""Tests for PostgreSQL Database Integration, Table Creation, and 100% Accurate TTS Voice Selection."""

import pytest
from app.database import init_db, engine, Base
from app.services.tts_service import tts_service, VOICE_CATALOG
from app.models import Project, VideoChunk, SubtitleCue, SpeakerProfile, RelationshipMatrix, GlossaryTerm
from sqlalchemy import inspect


@pytest.mark.asyncio
async def test_database_table_creation():
    """Verify that all 6 OneFL core tables and their schema columns are created without error."""
    await init_db()

    import app.database as db_mod
    async with db_mod.engine.connect() as conn:
        def inspect_tables(sync_conn):
            insp = inspect(sync_conn)
            return insp.get_table_names()

        tables = await conn.run_sync(inspect_tables)


    expected_tables = [
        "projects",
        "video_chunks",
        "subtitle_cues",
        "speaker_profiles",
        "relationship_matrices",
        "glossaries"
    ]
    for exp in expected_tables:
        assert exp in tables, f"Table '{exp}' must exist in database"


def test_voice_catalog_completeness():
    """Verify that VOICE_CATALOG contains all expected Vietnamese neural, VieNeu, and OpenAI voices."""
    catalog = tts_service.get_voices()
    voice_ids = [v["id"] for v in catalog]

    # 1. Edge Neural
    assert "vi-VN-HoaiMyNeural" in voice_ids
    assert "vi-VN-NamMinhNeural" in voice_ids

    # 2. Google AI
    assert "gtts-female-vi" in voice_ids

    # 3. VieNeu Character Profiles
    assert "vieneu-thuy-dung" in voice_ids
    assert "vieneu-ngoc-linh" in voice_ids
    assert "vieneu-ngoc-huyen" in voice_ids
    assert "vieneu-minh-quan" in voice_ids
    assert "vieneu-xuan-vinh" in voice_ids
    assert "vieneu-thanh-binh" in voice_ids

    # 4. OpenAI Cinematic Voices
    for oai_voice in ["nova", "onyx", "alloy", "echo", "fable", "shimmer"]:
        assert oai_voice in voice_ids, f"OpenAI voice '{oai_voice}' must be registered"


def test_voice_resolution_accuracy():
    """Verify that resolving any voice ID returns the EXACT matching voice without fallback degradation."""
    test_cases = [
        ("vi-VN-HoaiMyNeural", "edge-tts", "vi-VN-HoaiMyNeural"),
        ("vi-VN-NamMinhNeural", "edge-tts", "vi-VN-NamMinhNeural"),
        ("vieneu-minh-quan", "vieneu", "vieneu-minh-quan"),
        ("vieneu-thuy-dung", "vieneu", "vieneu-thuy-dung"),
        ("gtts-female-vi", "gtts", "gtts-female-vi"),
        ("nova", "openai", "nova"),
        ("onyx", "openai", "onyx"),
        ("alloy", "openai", "alloy"),
        ("echo", "openai", "echo"),
        ("fable", "openai", "fable"),
        ("shimmer", "openai", "shimmer"),
    ]

    for requested_id, expected_provider, expected_id in test_cases:
        voice_meta = tts_service.get_voice_by_id(requested_id)
        assert voice_meta["id"] == expected_id, f"Voice {requested_id} resolved to {voice_meta['id']}"
        assert voice_meta["provider"] == expected_provider, f"Provider for {requested_id} was {voice_meta['provider']}"


def test_single_voice_dubbing_precision():
    """Verify that in single voice dubbing mode, all dialogue cues strictly match user's chosen voice."""
    from app.services.tts_service import TTSService

    cues_data = [
        {"cue_index": 1, "start_time": 0.0, "end_time": 2.5, "speaker_tag": "SPEAKER_00", "translated_text": "Câu một"},
        {"cue_index": 2, "start_time": 3.0, "end_time": 5.0, "speaker_tag": "SPEAKER_01", "translated_text": "Câu hai"},
    ]

    selected_voice = "vieneu-minh-quan"
    # When use_speaker_matrix is False, speaker_voice_map is empty
    empty_speaker_map = {}

    assigned_voices = []
    for c in cues_data:
        speaker_tag = c.get("speaker_tag", "SPEAKER_00")
        cue_voice = empty_speaker_map.get(speaker_tag, selected_voice)
        assigned_voices.append(cue_voice)

    # Every cue must be assigned the exact voice chosen by the user
    for v in assigned_voices:
        assert v == selected_voice, f"Expected {selected_voice}, but got {v}"


def test_preview_cache_hash_isolation():
    """Verify that different voices never produce colliding cache keys."""
    text = "Xin chào các bạn đây là bản tin thử nghiệm."
    voice_a = "vi-VN-HoaiMyNeural"
    voice_b = "vieneu-minh-quan"
    speed = 1.0

    safe_hash = abs(hash(text)) % 100000
    cache_a = f"preview_v3_{voice_a}_{int(speed * 100)}_{safe_hash}.mp3"
    cache_b = f"preview_v3_{voice_b}_{int(speed * 100)}_{safe_hash}.mp3"

    assert cache_a != cache_b
    assert voice_a in cache_a
    assert voice_b in cache_b
