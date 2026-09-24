import sys
import os
import time
import json
import uuid
import sqlite3
import asyncio
import subprocess
import re
import edge_tts
from pathlib import Path

# Setup paths and UTF-8
sys.path.insert(0, "d:/OneFl/backend")
sys.stdout.reconfigure(encoding="utf-8")

import imageio_ffmpeg
from faster_whisper import WhisperModel
import numpy as np
from gtts import gTTS
from concurrent.futures import ThreadPoolExecutor

from app.config import settings
from app.services.llm_router import llm_router
from app.services.prompt_builder import PromptBuilder

PROJECT_ID = "ccf2249c-5a6e-4475-828e-9cd5e13b21be"
DB_PATH = "d:/OneFl/backend/onefl_videotrans.db"
OUTPUT_DIR = Path(f"d:/OneFl/data/outputs/{PROJECT_ID}")
AUDIO_PATH = OUTPUT_DIR / "extracted_audio.wav"
VIDEO_PATH = OUTPUT_DIR / "video_BV1mdYD6kEjh_p1.mp4"
SCRATCH_DIR = Path("d:/OneFl/tmp/scratch")
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR = SCRATCH_DIR / f"dub_full_{PROJECT_ID[:8]}"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

# Clips directory for synthesized speech
LOG_FILE = Path("d:/OneFl/pipeline.log")

def log(msg):
    ts = time.strftime("%H:%M:%S")
    formatted = f"[{ts}] {msg}"
    print(formatted, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

# -------------------------------------------------------------
# STEP 1: ASR TRANSCRIPTION (Remaining chunks: 1800s to end)
# -------------------------------------------------------------
def run_transcription():
    log("=== BƯỚC 1: NHẬN DIỆN GIỌNG NÓI TOÀN BỘ 6 GIỜ 20 PHÚT ===")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Get last cue index and start_time
    cur.execute("SELECT MAX(cue_index), MAX(end_time) FROM subtitle_cues WHERE project_id = ?", (PROJECT_ID,))
    max_idx, max_end = cur.fetchone()
    current_cue_index = max_idx or 0
    start_second = max_end or 0.0
    
    log(f"Đã có {current_cue_index} câu thoại (đến {start_second:.1f}s). Bắt đầu phiên âm phần còn lại...")
    
    # Measure full duration
    p = subprocess.run([ffmpeg, "-i", str(AUDIO_PATH)], capture_output=True, text=True, errors="ignore")
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", p.stderr)
    total_dur = 22805.36
    if m:
        total_dur = int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))
    
    log(f"Tổng thời lượng audio: {total_dur:.1f}s (~{total_dur/3600:.2f} giờ)")
    
    CHUNK_SIZE = 600.0 # 10 minutes
    start_chunk = int(start_second // CHUNK_SIZE)
    total_chunks = int(total_dur // CHUNK_SIZE) + (1 if total_dur % CHUNK_SIZE > 0 else 0)
    
    log(f"Khởi tạo Whisper ASR (tiny, 8 threads CPU)...")
    model = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=8)
    
    new_cues_count = 0
    for chunk_idx in range(start_chunk, total_chunks):
        c_start = chunk_idx * CHUNK_SIZE
        c_dur = min(CHUNK_SIZE, total_dur - c_start)
        if c_dur <= 0.5:
            break
            
        chunk_wav = SCRATCH_DIR / f"chunk_{chunk_idx}.wav"
        subprocess.run([
            ffmpeg, "-y", "-ss", str(c_start), "-t", str(c_dur),
            "-i", str(AUDIO_PATH), "-c", "copy", str(chunk_wav)
        ], capture_output=True)
        
        t0 = time.time()
        segs, _ = model.transcribe(str(chunk_wav), language="zh", beam_size=5)
        seg_list = list(segs)
        t_el = time.time() - t0
        
        try:
            chunk_wav.unlink()
        except Exception:
            pass
            
        # Insert segments into DB
        for s in seg_list:
            txt = s.text.strip()
            if not txt:
                continue
            seg_start = round(c_start + s.start, 3)
            seg_end = round(c_start + s.end, 3)
            
            # Skip overlap with already transcribed
            if seg_start < start_second - 0.5:
                continue
                
            current_cue_index += 1
            cur.execute("""
                INSERT INTO subtitle_cues (id, project_id, cue_index, start_time, end_time, original_text, speaker_tag, cps, line_count, max_line_length, has_guardrail_violation, is_edited, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'SPEAKER_00', 0.0, 1, 0, 0, 0, datetime('now'), datetime('now'))
            """, (str(uuid.uuid4()), PROJECT_ID, current_cue_index, seg_start, seg_end, txt))
            new_cues_count += 1
            
        conn.commit()
        pct = int((chunk_idx + 1) / total_chunks * 100)
        log(f"[{pct}%] Xong đoạn {chunk_idx+1}/{total_chunks} ({c_start/60:.1f}m - {(c_start+c_dur)/60:.1f}m): {len(seg_list)} câu (mất {t_el:.1f}s). Tổng câu: {current_cue_index}")

    cur.execute("UPDATE projects SET video_duration_seconds = ? WHERE id = ?", (total_dur, PROJECT_ID))
    conn.commit()
    conn.close()
    log(f"Hoàn thành nhận diện giọng nói! Đã thêm {new_cues_count} câu mới. Tổng câu thoại: {current_cue_index}")

# -------------------------------------------------------------
# STEP 2: TRANSLATE UNTRANSLATED CUES WITH GEMINI FLASH
# -------------------------------------------------------------
async def run_translation():
    log("=== BƯỚC 2: DỊCH CÁC CÂU THOẠI MỚI SANG TIẾNG VIỆT (GEMINI FLASH) ===")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT cue_index, start_time, end_time, original_text 
        FROM subtitle_cues 
        WHERE project_id = ? AND (translated_text IS NULL OR translated_text = '' OR translated_text = original_text)
        ORDER BY cue_index
    """, (PROJECT_ID,))
    untranslated = cur.fetchall()
    log(f"Số câu thoại cần dịch: {len(untranslated)}")
    
    if not untranslated:
        conn.close()
        return

    BATCH_SIZE = 100
    updated_count = 0
    total_batches = (len(untranslated) + BATCH_SIZE - 1) // BATCH_SIZE
    # Query speakers, relationship matrix, and glossary from DB for translation
    c.execute("SELECT speaker_tag, display_name, original_name, gender, role, tone, notes FROM speaker_profiles WHERE project_id=?", (PROJECT_ID,))
    db_speakers = {
        r[0]: {
            "name": r[1],
            "original_name": r[2] or "",
            "gender": r[3],
            "role": r[4] or "",
            "tone": r[5] or "",
            "notes": r[6] or ""
        }
        for r in c.fetchall()
    }
    c.execute("SELECT source_speaker, target_speaker, self_pronoun, target_pronoun, relationship_type, honorific_notes FROM relationship_matrices WHERE project_id=?", (PROJECT_ID,))
    db_rels = [
        {
            "source_speaker": r[0],
            "target_speaker": r[1],
            "self_pronoun": r[2],
            "target_pronoun": r[3],
            "relationship_type": r[4] or "Đối thoại",
            "honorific_notes": r[5] or ""
        }
        for r in c.fetchall()
    ]
    c.execute("SELECT source_term, target_term, context_note FROM glossaries WHERE project_id=?", (PROJECT_ID,))
    db_glossary = [
        {
            "source_term": r[0],
            "target_term": r[1],
            "context_note": r[2] or ""
        }
        for r in c.fetchall()
    ]
    log(f"Đã nạp {len(db_speakers)} nhân vật, {len(db_rels)} quan hệ xưng hô, {len(db_glossary)} thuật ngữ glossary vào AI Translation.")

    log(f"Tổng số {len(untranslated)} câu chia thành {total_batches} đợt dịch (100 câu/đợt)...")

    for b_idx in range(0, len(untranslated), BATCH_SIZE):
        batch = untranslated[b_idx:b_idx + BATCH_SIZE]
        batch_num = (b_idx // BATCH_SIZE) + 1
        
        cues_payload = [
            {"id": r[0], "text": r[3], "speaker": "SPEAKER_00", "duration": round(r[2] - r[1], 2)}
            for r in batch
        ]
        prompts = PromptBuilder.build_translation_prompt(
            source_lang="zh",
            target_lang="vi",
            cues_to_translate=cues_payload,
            speaker_profiles=db_speakers,
            relationship_matrix=db_rels,
            glossary=db_glossary,
            previous_context=[]
        )
        
        system_prompt = prompts["system_prompt"] + (
            "\nQUY TẮC BẮT BUỘC:\n"
            "1. Đây là phim hoạt hình Anime Khoa huyễn / Cơ Giáp (Mecha). Nhân vật chính Cố Vãn Chu (顾晚舟), Linh Thất (零七) LÀ NỮ. Tuyệt đối không dịch thành 'anh ta'/'hắn'. Phải xưng là 'cô ấy', 'nàng', 'em', 'tôi'.\n"
            "2. Giọng văn tự nhiên, chuẩn phong cách kênh YouTube Review Phim Hoạt Hình.\n"
            "3. Trả về đúng JSON format: {\"translations\": [{\"id\": ..., \"translated_text\": \"...\"}]}"
        )

        success = False
        for attempt in range(4):
            try:
                res = await llm_router.generate_completion(system_prompt, prompts["user_prompt"], model_override="gemini-3.1-flash-lite")
                clean_res = res.strip()
                if clean_res.startswith("```"):
                    lines = clean_res.split("\n")
                    clean_res = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
                parsed = json.loads(clean_res)
                t_list = parsed.get("translations", [])
                
                batch_saved = 0
                for idx, t in enumerate(t_list):
                    if isinstance(t, str):
                        vi_txt = t.strip()
                        c_id = None
                    elif isinstance(t, dict):
                        vi_txt = (t.get("text") or t.get("translated_text") or "").strip()
                        c_id = t.get("id")
                    else:
                        continue

                    if not vi_txt:
                        continue

                    target_idx = None
                    for b in batch:
                        if b[0] == c_id:
                            target_idx = c_id
                            break
                    if target_idx is None and idx < len(batch):
                        target_idx = batch[idx][0]
                        
                    if target_idx is not None:
                        cur.execute("UPDATE subtitle_cues SET translated_text = ? WHERE project_id = ? AND cue_index = ?", (vi_txt, PROJECT_ID, target_idx))
                        batch_saved += 1
                        updated_count += 1

                conn.commit()
                log(f"[{batch_num}/{total_batches}] Dịch thành công {batch_saved}/{len(batch)} câu. (Đã lưu tổng: {updated_count}/{len(untranslated)})")
                success = True
                break
            except Exception as err:
                log(f"Thử lại đợt {batch_num} lần {attempt+1}/4: {err}")
                await asyncio.sleep(4.0 * (attempt + 1))

        # Pace requests to comply with Google AI RPM
        await asyncio.sleep(2.5)

    conn.close()
    log(f"Đã hoàn thành dịch {updated_count}/{len(untranslated)} câu thoại tiếng Việt!")

# -------------------------------------------------------------
# STEP 3: EXPORT SUBTITLES (.ASS & .SRT)
# -------------------------------------------------------------
def export_subtitles():
    log("=== BƯỚC 3: XUẤT PHỤ ĐỀ TIẾNG VIỆT HOÀN CHỈNH (.ASS & .SRT) ===")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT cue_index, start_time, end_time, original_text, translated_text FROM subtitle_cues WHERE project_id = ? ORDER BY cue_index", (PROJECT_ID,))
    rows = cur.fetchall()
    conn.close()
    
    ass_path = OUTPUT_DIR / "subtitles.ass"
    srt_path = OUTPUT_DIR / "subtitles.srt"
    
    def format_ass_time(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        cs = int((sec - int(sec)) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def format_srt_time(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int((sec - int(sec)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    # Write ASS with 1280x720 video alignment and centered bold typography
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("[Script Info]\nTitle: OneFl Vietnamese Subtitles\nScriptType: v4.00+\nPlayResX: 1280\nPlayResY: 720\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n")
        f.write("[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        f.write("Style: Default,Arial,30,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,2,30,30,42,1\n\n")
        f.write("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for r in rows:
            text = (r[4] or r[3] or "").replace("\n", "\\N")
            f.write(f"Dialogue: 0,{format_ass_time(r[1])},{format_ass_time(r[2])},Default,,0,0,0,,{text}\n")

    # Write SRT
    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, r in enumerate(rows, start=1):
            text = r[4] or r[3] or ""
            f.write(f"{idx}\n{format_srt_time(r[1])} --> {format_srt_time(r[2])}\n{text}\n\n")

    log(f"Đã xuất file phụ đề: {ass_path} ({os.path.getsize(ass_path)/1024:.1f} KB), {srt_path} ({os.path.getsize(srt_path)/1024:.1f} KB)")

# -------------------------------------------------------------
# STEP 4: ULTRA-FAST NEURAL SPEECH SYNTHESIS (Edge-TTS: HoaiMy)
# -------------------------------------------------------------
async def run_speech_synthesis(voice: str = "vi-VN-HoaiMyNeural", rate: str = "+0%", pitch: str = "+0Hz"):
    log(f"=== BƯỚC 4: TỔNG HỢP GIỌNG LỒNG TIẾNG NỮ REVIEW PHIM ({voice}, tốc độ {rate}, cao độ {pitch}) ===")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT cue_index, start_time, end_time, translated_text, original_text FROM subtitle_cues WHERE project_id = ? ORDER BY cue_index", (PROJECT_ID,))
    rows = cur.fetchall()
    conn.close()
    
    total = len(rows)
    log(f"Tổng số câu cần chuẩn bị âm thanh: {total}")
    
    sem = asyncio.Semaphore(12)
    done_count = 0
    t0 = time.time()
    
    async def process_cue(row):
        nonlocal done_count
        idx, st, et, vi_text, zh_text = row
        clip_path = CLIPS_DIR / f"clip_{idx:04d}.mp3"
        if clip_path.exists() and clip_path.stat().st_size > 500:
            done_count += 1
            return
            
        # NEVER fall back to Chinese original_text - dubbing must be in Vietnamese!
        txt = (vi_text or "...").strip()
        txt = re.sub(r'[\r\n\t]+', ' ', txt).strip()
        if not txt:
            txt = "..."
            
        async with sem:
            for attempt in range(3):
                try:
                    comm = edge_tts.Communicate(txt, voice, rate=rate, pitch=pitch)
                    await comm.save(str(clip_path))
                    if clip_path.exists() and clip_path.stat().st_size > 300:
                        break
                except Exception:
                    await asyncio.sleep(1.0 * (attempt + 1))
            else:
                dur = max(0.5, min(5.0, (et - st) if et > st else 1.0))
                subprocess.run([
                    ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                    "-t", str(dur), "-c:a", "libmp3lame", str(clip_path)
                ], capture_output=True)
                
            done_count += 1
            if done_count % 200 == 0 or done_count == total:
                elapsed = time.time() - t0
                speed = done_count / max(1.0, elapsed)
                eta_sec = (total - done_count) / max(0.1, speed)
                log(f"[TTS] Đã sinh âm thanh: {done_count}/{total} câu ({done_count/total*100:.1f}%) | {speed:.1f} câu/s | Còn khoảng {eta_sec/60:.1f} phút")

    tasks = [asyncio.create_task(process_cue(r)) for r in rows]
    await asyncio.gather(*tasks)
    log(f"Đã hoàn thành sinh toàn bộ file giọng nói cho {total} câu thoại trong {time.time() - t0:.1f}s!")

# -------------------------------------------------------------
# STEP 5: ULTRA-FAST PCM TIMELINE MIXING WITH DYNAMIC TEMPO SYNC
# -------------------------------------------------------------
def mix_full_audio_timeline():
    log("=== BƯỚC 5: HÒA ÂM TIMELINE ÂM THANH ĐỒNG BỘ SUB (PCM MATRIX) ===")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT cue_index, start_time, end_time FROM subtitle_cues WHERE project_id = ? ORDER BY cue_index", (PROJECT_ID,))
    rows = cur.fetchall()
    cur.execute("SELECT video_duration_seconds FROM projects WHERE id = ?", (PROJECT_ID,))
    p_dur = cur.fetchone()[0] or 22805.36
    conn.close()

    sample_rate = 24000
    total_samples = int((p_dur + 10.0) * sample_rate)
    log(f"Khởi tạo ma trận PCM {total_samples} samples ({p_dur/3600:.2f} giờ, sample_rate={sample_rate})...")
    timeline = np.zeros(total_samples, dtype=np.int32)
    
    t0 = time.time()
    rows_with_next = []
    for i, r in enumerate(rows):
        c_idx, st, et = r
        next_st = rows[i + 1][1] if i + 1 < len(rows) else (et + 5.0)
        rows_with_next.append((c_idx, st, et, next_st))

    def read_clip(item):
        c_idx, st, et, next_st = item
        clip_path = CLIPS_DIR / f"clip_{c_idx:04d}.mp3"
        if not clip_path.exists() or clip_path.stat().st_size < 300:
            return None

        # Decode raw PCM
        cmd = [ffmpeg, "-i", str(clip_path), "-f", "s16le", "-ar", str(sample_rate), "-ac", "1", "-"]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if not (proc.returncode == 0 and proc.stdout):
            return None

        samples = np.frombuffer(proc.stdout, dtype=np.int16)
        dur = len(samples) / sample_rate

        # Sync window
        window = max(0.5, et - st)
        max_limit = min(window * 1.25, max(window, next_st - st - 0.05))

        # Dynamic tempo adjustment to guarantee speech finishes within subtitle timing
        if dur > max_limit and max_limit > 0.4:
            speed = min(1.5, dur / max_limit)
            if speed > 1.08:
                cmd_tempo = [
                    ffmpeg, "-i", str(clip_path),
                    "-filter:a", f"atempo={speed:.2f}",
                    "-f", "s16le", "-ar", str(sample_rate), "-ac", "1", "-"
                ]
                proc2 = subprocess.run(cmd_tempo, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                if proc2.returncode == 0 and proc2.stdout:
                    samples = np.frombuffer(proc2.stdout, dtype=np.int16)

        # Gentle boundary clamping to prevent bleed-over into next cue
        max_samples = int((next_st - st) * sample_rate)
        if max_samples > 0 and len(samples) > max_samples:
            samples = samples[:max_samples]

        return (st, samples)

    log(f"Đang giải mã song song và đồng bộ hóa {len(rows)} file âm thanh...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(read_clip, rows_with_next))

    for res in results:
        if res is not None:
            st, samples = res
            s_idx = int(st * sample_rate)
            e_idx = min(len(timeline), s_idx + len(samples))
            timeline[s_idx:e_idx] += samples[:e_idx - s_idx]

    log(f"Hoàn thành đặt {len(rows)} câu vào timeline trong {time.time() - t0:.1f}s! Đang nén xuất file MP3...")
    del results
    import gc
    gc.collect()

    np.clip(timeline, -32768, 32767, out=timeline)
    
    out_audio = OUTPUT_DIR / f"{PROJECT_ID}_dubbed.mp3"
    enc_cmd = [
        ffmpeg, "-y",
        "-f", "s16le", "-ar", str(sample_rate), "-ac", "1",
        "-i", "-",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        str(out_audio)
    ]
    p_enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    CHUNK_SIZE = sample_rate * 60
    for i in range(0, len(timeline), CHUNK_SIZE):
        chunk = timeline[i:i + CHUNK_SIZE].astype(np.int16)
        p_enc.stdin.write(chunk.tobytes())
    p_enc.stdin.close()
    p_enc.wait()

    del timeline
    gc.collect()
    log(f"Xuất file âm thanh lồng tiếng hoàn chỉnh 6.33 giờ: {out_audio} ({os.path.getsize(out_audio)/(1024*1024):.1f} MB)")

# -------------------------------------------------------------
# STEP 6: FAST MUX WITH ORIGINAL VIDEO (30s)
# -------------------------------------------------------------
def mux_dubbed_video():
    log("=== BƯỚC 6: HÒA TRỘN ÂM THANH LỒNG TIẾNG VÀO VIDEO GỐC ===")
    out_audio = OUTPUT_DIR / f"{PROJECT_ID}_dubbed.mp3"
    out_dubbed_video = OUTPUT_DIR / f"{PROJECT_ID}_dubbed.mp4"
    
    # Mix original BGM at 15% volume with dubbed voiceover at 100% volume
    cmd = [
        ffmpeg, "-y",
        "-i", str(VIDEO_PATH),
        "-i", str(out_audio),
        "-filter_complex", "[0:a]volume=0.15[bgm];[bgm][1:a]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "0:v:0",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        str(out_dubbed_video)
    ]
    log(f"Bắt đầu muxing âm thanh vào video 6.33 giờ (stream copy video siêu nhanh)...")
    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode == 0 and out_dubbed_video.exists():
        log(f"Đã tạo video lồng tiếng 6.33 giờ thành công trong {time.time() - t0:.1f}s! Dung lượng: {os.path.getsize(out_dubbed_video)/(1024*1024):.1f} MB")
        
        # Update DB
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("""
            UPDATE projects 
            SET dubbed_video_url = ?, dubbed_audio_url = ?, status = 'COMPLETED', progress_percentage = 100 
            WHERE id = ?
        """, (f"/static/data/outputs/{PROJECT_ID}/{PROJECT_ID}_dubbed.mp4", f"/static/data/outputs/{PROJECT_ID}/{PROJECT_ID}_dubbed.mp3", PROJECT_ID))
        conn.commit()
        conn.close()
    else:
        log(f"Lỗi muxing: {res.stderr.decode(errors='ignore')[-500:]}")

# -------------------------------------------------------------
# STEP 7: HARD-BURN SUBTITLES WITH CHINESE CONCEALMENT (NVENC)
# -------------------------------------------------------------
def burn_subtitles_nvenc():
    log("=== BƯỚC 7: HARD-BURN PHỤ ĐỀ TIẾNG VIỆT & CHE PHỤ ĐỀ TRUNG CŨ (GPU NVENC) ===")
    ass_path = OUTPUT_DIR / "subtitles.ass"
    out_dubbed_video = OUTPUT_DIR / f"{PROJECT_ID}_dubbed.mp4"
    out_burned = OUTPUT_DIR / "output_burned.mp4"
    
    # Use relative ass filename to avoid Windows colon path bug in filtergraph
    ass_name = ass_path.name
    vf_filter = f"drawbox=x=0:y=ih-102:w=iw:h=88:color=black@1.0:t=fill,ass={ass_name}"
    
    cmd = [
        ffmpeg, "-y",
        "-i", str(out_dubbed_video.resolve()),
        "-vf", vf_filter,
        "-c:v", "h264_nvenc",
        "-preset", "p4",
        "-cq", "23",
        "-c:a", "copy",
        str(out_burned.resolve())
    ]
    log(f"Bắt đầu render GPU NVENC: {' '.join(cmd[:8])}...")
    t0 = time.time()
    res = subprocess.run(cmd, cwd=str(OUTPUT_DIR), capture_output=True)
    if res.returncode == 0 and out_burned.exists():
        log(f"Hoàn thành hard-burn phụ đề tiếng Việt 6.33 giờ trong {time.time() - t0:.1f}s! Dung lượng: {os.path.getsize(out_burned)/(1024*1024):.1f} MB")
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE projects SET burned_video_url = ? WHERE id = ?", (f"/static/data/outputs/{PROJECT_ID}/output_burned.mp4", PROJECT_ID))
        conn.commit()
        conn.close()
    else:
        log(f"Lỗi NVENC render: {res.stderr.decode(errors='ignore')[-500:]}")

# -------------------------------------------------------------
# MAIN PIPELINE EXECUTION
# -------------------------------------------------------------
async def main():
    log(">>> BẮT ĐẦU QUY TRÌNH XỬ LÝ TOÀN DIỆN 6 GIỜ 20 PHÚT <<<")
    run_transcription()
    await run_translation()
    export_subtitles()
    await run_speech_synthesis()
    mix_full_audio_timeline()
    mux_dubbed_video()
    burn_subtitles_nvenc()
    log(">>> TOÀN BỘ QUY TRÌNH 6 GIỜ 20 PHÚT ĐÃ HOÀN TẤT THÀNH CÔNG! <<<")

if __name__ == "__main__":
    asyncio.run(main())
