"""Optional bounded-chunk pyannote adapter with cross-chunk identity matching.

Adapter contract: https://huggingface.co/pyannote/speaker-diarization-community-1
Models are loaded only when ENABLE_SPEAKER_DIARIZATION is explicitly enabled.
"""
from app.config import settings


def match_speakers(embeddings, registry: list, threshold: float = 0.75) -> list[str]:
    import numpy as np
    identities, used = [], set()
    for embedding in embeddings:
        vector = np.asarray(embedding, dtype=np.float32)
        norm = np.linalg.norm(vector)
        if not np.isfinite(vector).all() or norm <= 0:
            raise RuntimeError('Diarization returned an invalid speaker embedding')
        vector = vector / norm
        scores = [float(np.dot(vector, previous)) if i not in used else -1 for i, previous in enumerate(registry)]
        best = int(np.argmax(scores)) if scores else -1
        if best < 0 or scores[best] < threshold:
            if len(registry) >= 100:
                raise RuntimeError('Diarization exceeded the configured 100-speaker safety limit')
            best = len(registry)
            registry.append(vector)
        else:
            average = registry[best] + vector
            registry[best] = average / np.linalg.norm(average)
        used.add(best)
        identities.append(f'SPEAKER_{best:02d}')
    return identities


def assign_turns(segments: list[dict], turns: list[tuple], identities: dict) -> list[dict]:
    result = []
    for segment in segments:
        candidates = [(max(0., min(segment['end'], end) - max(segment['start'], start)), label) for start, end, label in turns]
        overlap, label = max(candidates, default=(0., None))
        result.append({**segment, 'speaker': identities[label] if overlap > 0 else 'UNKNOWN'})
    return result


class DiarizationService:
    def __init__(self):
        self.pipeline = None

    def analyze(self, audio_path, segments, registry):
        if not settings.HF_TOKEN:
            raise RuntimeError('Diarization requires HF_TOKEN and accepted model terms')
        if self.pipeline is None:
            try:
                from pyannote.audio import Pipeline
                import torch
            except ImportError as error:
                raise RuntimeError('Install the diarization optional dependency to enable speaker recognition') from error
            self.pipeline = Pipeline.from_pretrained('pyannote/speaker-diarization-community-1', token=settings.HF_TOKEN)
            self.pipeline.to(torch.device('cuda' if settings.DIARIZATION_DEVICE == 'cuda' else 'cpu'))
        output = self.pipeline(str(audio_path))
        labels = output.speaker_diarization.labels()
        mapped = dict(zip(labels, match_speakers(output.speaker_embeddings, registry)))
        turns = [(float(turn.start), float(turn.end), label) for turn, _, label in output.exclusive_speaker_diarization.itertracks(yield_label=True)]
        return assign_turns(segments, turns, mapped)


diarization_service = DiarizationService()
