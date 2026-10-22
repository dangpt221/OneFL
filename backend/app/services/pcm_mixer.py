"""Overlap-add PCM to disk with memory bounded independently of video duration."""
from pathlib import Path


def mix_pcm_blocks(clips: list[tuple[int, Path]], output: Path, total_samples: int, block_samples: int = 240000) -> None:
    import numpy as np
    if total_samples <= 0 or block_samples <= 0:
        raise ValueError('Timeline and block size must be positive')
    ordered = sorted((start, path, path.stat().st_size // 2) for start, path in clips)
    if any(start < 0 or length <= 0 for start, path, length in ordered):
        raise ValueError('PCM clip has invalid start or length')
    active, index = [], 0
    with open(output, 'wb') as destination:
        for block_start in range(0, total_samples, block_samples):
            count = min(block_samples, total_samples - block_start)
            block_end = block_start + count
            while index < len(ordered) and ordered[index][0] < block_end:
                active.append(ordered[index])
                index += 1
            block = np.zeros(count, dtype=np.int32)
            for start, path, length in active:
                left, right = max(start, block_start), min(start + length, block_end)
                if right <= left:
                    continue
                with open(path, 'rb') as source:
                    source.seek((left - start) * 2)
                    samples = np.frombuffer(source.read((right - left) * 2), dtype='<i2')
                if len(samples) != right - left:
                    raise RuntimeError('Incomplete PCM clip')
                block[left - block_start:right - block_start] += samples
            np.clip(block, -32768, 32767, out=block)
            destination.write(block.astype('<i2').tobytes())
            active = [clip for clip in active if clip[0] + clip[2] > block_end]
