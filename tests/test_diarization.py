import pytest


def test_speaker_identity_matches_embeddings_across_chunks():
    from app.services.diarization_service import match_speakers
    registry = []
    first = match_speakers([[1., 0.], [0., 1.]], registry)
    second = match_speakers([[0.01, 0.99], [0.99, 0.01]], registry)
    assert first == ['SPEAKER_00', 'SPEAKER_01']
    assert second == ['SPEAKER_01', 'SPEAKER_00']


def test_diarization_assigns_maximum_time_overlap():
    from app.services.diarization_service import assign_turns
    segments = [{'start': 1., 'end': 3., 'text': 'hello'}]
    result = assign_turns(segments, [(0., 1.5, 'A'), (1.5, 4., 'B')], {'A': 'SPEAKER_00', 'B': 'SPEAKER_01'})
    assert result[0]['speaker'] == 'SPEAKER_01'
