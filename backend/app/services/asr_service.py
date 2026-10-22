import os
import re
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from app.config import settings

logger = logging.getLogger(__name__)


class ASRService:
    """Automatic Speech Recognition (ASR) with large-audio chunking & GPU/CPU fallback."""

    def __init__(self):
        self.model = None

    def get_audio_duration(self, audio_path: Path) -> float:
        """Extracts exact audio duration in seconds using FFmpeg."""
        ffmpeg_bin = settings.get_ffmpeg_bin()
        if not ffmpeg_bin or not audio_path.exists():
            return 0.0
        try:
            res = subprocess.run(
                [ffmpeg_bin, "-i", str(audio_path)],
                capture_output=True,
                text=True,
                errors="ignore", timeout=30
            )
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
            if m:
                h, mins, s = m.groups()
                return int(h) * 3600 + int(mins) * 60 + float(s)
        except Exception as e:
            logger.warning(f"Could not parse audio duration with FFmpeg: {e}")
        return 0.0

    def _get_or_load_model(self):
        """Loads WhisperModel on GPU if available, or CPU int8 with zero errors."""
        if self.model is not None:
            return self.model

        from faster_whisper import WhisperModel
        model_size = getattr(settings, "WHISPER_MODEL_SIZE", "tiny")
        device_pref = getattr(settings, "WHISPER_DEVICE", "auto")
        compute_pref = getattr(settings, "WHISPER_COMPUTE_TYPE", "int8")

        if device_pref in ["cuda", "auto"]:
            try:
                ct = "float16" if compute_pref in ["auto", "float16"] else compute_pref
                self.model = WhisperModel(model_size, device="cuda", compute_type=ct)
                logger.info(f"Loaded faster-whisper model '{model_size}' on CUDA ({ct}) successfully.")
                return self.model
            except Exception as e:
                logger.warning(f"CUDA Whisper model loading failed ({e}). Falling back to CPU int8.")

        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        logger.info(f"Loaded faster-whisper model '{model_size}' on CPU (int8) successfully.")
        return self.model

    async def transcribe_audio(
        self, audio_path: Path, source_language: str = "auto",
        enable_diarization: Optional[bool] = None,
        progress_callback: Optional[Callable[[int, str], Any]] = None,
        max_duration_seconds: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Transcribe bounded chunks, checkpoint successes, and never invent cues."""
        import hashlib
        import json
        import math
        from app.services.media_process import run_media
        if not audio_path.is_file() or audio_path.stat().st_size == 0:
            raise FileNotFoundError(f"Audio input is missing or empty: {audio_path.name}")
        if not hasattr(self, '_inference_lock'):
            self._inference_lock = asyncio.Lock()
        async with self._inference_lock:
            model = await self._blocking(self._get_or_load_model)
            total = await self._blocking(lambda: self.get_audio_duration(audio_path))
            if not math.isfinite(total) or total <= 0:
                raise RuntimeError("Could not determine audio duration")
            limit = max_duration_seconds if max_duration_seconds is not None else settings.ASR_MAX_DURATION_SECONDS
            if limit and total > limit:
                raise ValueError("Audio exceeds configured ASR duration limit; refusing a partial transcript")
            stat = audio_path.stat()
            fingerprint = hashlib.sha256(f"{audio_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{settings.WHISPER_MODEL_SIZE}:{source_language}:{settings.WHISPER_BEAM_SIZE}".encode()).hexdigest()
            cache_dir = settings.TEMP_SCRATCH_DIR / 'asr' / fingerprint
            cache_dir.mkdir(parents=True, exist_ok=True)
            cues = []
            registry = []
            diarization = settings.ENABLE_SPEAKER_DIARIZATION if enable_diarization is None else enable_diarization
            chunk_size = 600.
            boundaries = [0.]
            while boundaries[-1] < total:
                target = min(total, boundaries[-1] + chunk_size)
                boundary = target
                if target < total:
                    # Search only the preceding four seconds, so chunks never
                    # exceed the memory bound. Prefer a natural speech pause.
                    offset = max(boundaries[-1], target - 4.)
                    _, diagnostics = await run_media([settings.get_ffmpeg_bin(), '-hide_banner', '-ss', str(offset), '-i', str(audio_path), '-t', str(target - offset), '-af', 'silencedetect=noise=-35dB:d=0.25', '-f', 'null', '-'])
                    pauses = re.findall(r'silence_end:\s*([0-9.]+)', diagnostics.decode(errors='ignore'))
                    if pauses:
                        candidate = offset + float(pauses[-1])
                        if candidate > boundaries[-1] + 1.:
                            boundary = min(target, candidate)
                boundaries.append(boundary)
            for index, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
                duration = end - start
                checkpoint = cache_dir / f'{index}_{start:.3f}_{duration:.3f}.json'
                chunk_file = cache_dir / f'{index}.wav'
                if checkpoint.exists():
                    try:
                        segments = json.loads(checkpoint.read_text(encoding='utf-8'))
                        if not isinstance(segments, list):
                            raise ValueError('Invalid ASR checkpoint')
                    except (ValueError, OSError) as error:
                        logger.warning('Discarding invalid ASR checkpoint %s: %s', checkpoint.name, error)
                        checkpoint.unlink(missing_ok=True)
                        segments = None
                else:
                    segments = None
                if segments is None:
                    try:
                        await run_media([settings.get_ffmpeg_bin(), '-y', '-ss', str(start), '-i', str(audio_path), '-t', str(duration), '-ar', '16000', '-ac', '1', str(chunk_file)])
                        def infer():
                            stream, info = model.transcribe(
                                str(chunk_file), language=None if source_language in ('auto', '', None) else source_language,
                                beam_size=settings.WHISPER_BEAM_SIZE, vad_filter=True, word_timestamps=True,
                            )
                            return [{'start': float(s.start), 'end': float(s.end), 'text': s.text.strip()} for s in stream if s.text.strip()]
                        segments = await self._blocking(infer)
                        temp = checkpoint.with_suffix('.tmp')
                        temp.write_text(json.dumps(segments, ensure_ascii=False), encoding='utf-8')
                        temp.replace(checkpoint)
                    finally:
                        chunk_file.unlink(missing_ok=True)
                if diarization:
                    from app.services.diarization_service import diarization_service
                    try:
                        await run_media([settings.get_ffmpeg_bin(), '-y', '-ss', str(start), '-i', str(audio_path), '-t', str(duration), '-ar', '16000', '-ac', '1', str(chunk_file)])
                        segments = await self._blocking(lambda: diarization_service.analyze(chunk_file, segments, registry))
                    finally:
                        chunk_file.unlink(missing_ok=True)
                for segment in segments:
                    seg_start = max(start, start + float(segment['start']))
                    seg_end = min(start + duration, start + float(segment['end']))
                    if not math.isfinite(seg_start + seg_end) or seg_end <= seg_start:
                        raise RuntimeError('ASR returned invalid timestamps')
                    cues.append({'cue_index': len(cues) + 1, 'start_time': round(seg_start, 3),
                                 'end_time': round(seg_end, 3), 'original_text': segment['text'],
                                 'speaker_tag': segment.get('speaker', 'SPEAKER_00')})
                if progress_callback:
                    await progress_callback(int((index + 1) / (len(boundaries) - 1) * 100), f"ASR: {index + 1}/{math.ceil(total / chunk_size)} chunks, {len(cues)} cues")
            return cues

    @staticmethod
    async def _blocking(function):
        # Cancellation must not release the model lock while inference is still
        # using it in another thread. Job cancellation stays pending until safe.
        future = asyncio.create_task(asyncio.to_thread(function))
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            await future
            raise


asr_service = ASRService()
