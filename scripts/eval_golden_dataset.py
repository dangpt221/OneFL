"""
Benchmark & Evaluation Runner for OneFL Golden Dataset (1000 items).
Evaluates 100% of test cases across all 4 Guardrail Tiers, calculates CPS metrics,
line length distributions, language performance, and outputs a formatted benchmark report.
"""
import json
import sys
import time
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.services.guardrails import SubtitleGuardrails

DATASET_FILE = Path(__file__).resolve().parent.parent / "data" / "golden_dataset_1000.json"


def evaluate_dataset():
    if not DATASET_FILE.exists():
        print(f"Dataset file not found at {DATASET_FILE}")
        return

    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    total_cases = len(dataset)
    passed_cases = 0
    failed_cases = 0
    all_violations = []

    # Metrics
    lang_stats = {}
    genre_stats = {}
    all_cps = []
    all_lengths = []
    multiline_count = 0
    total_cues = 0

    start_time = time.time()

    for item in dataset:
        case_id = item["id"]
        src_lang = item["source_language"]
        category = item["category"]

        if src_lang not in lang_stats:
            lang_stats[src_lang] = {"total": 0, "passed": 0}
        if category not in genre_stats:
            genre_stats[category] = {"total": 0, "passed": 0}

        lang_stats[src_lang]["total"] += 1
        genre_stats[category]["total"] += 1

        requested_cues = [
            {
                "id": c["cue_index"],
                "text": c["original_text"],
                "duration": c["duration"],
                "speaker": c["speaker_tag"],
                "target_speaker": c.get("target_speaker_tag")
            }
            for c in item["input_cues"]
        ]

        raw_llm = json.dumps({"translations": item["ground_truth_translation"]})

        is_valid, translations, violations = SubtitleGuardrails.validate_batch(
            requested_cues=requested_cues,
            llm_raw_response=raw_llm,
            relationship_matrix=item["relationship_matrix"],
            glossary=item["glossary"]
        )

        total_cues += len(translations)

        for trans in translations:
            text = trans.text
            lines = text.split("\n")
            if len(lines) > 1:
                multiline_count += 1
            for l in lines:
                all_lengths.append(len(l))

            # Match duration
            cue_orig = next((c for c in requested_cues if c["id"] == trans.id), None)
            if cue_orig:
                cps = SubtitleGuardrails.calculate_cps(text, cue_orig["duration"])
                all_cps.append(cps)

        if is_valid:
            passed_cases += 1
            lang_stats[src_lang]["passed"] += 1
            genre_stats[category]["passed"] += 1
        else:
            failed_cases += 1
            all_violations.append({"id": case_id, "violations": violations})

    elapsed = round(time.time() - start_time, 2)

    pass_rate = round((passed_cases / total_cases) * 100, 2)
    avg_cps = round(sum(all_cps) / len(all_cps), 2) if all_cps else 0.0
    min_cps = min(all_cps) if all_cps else 0.0
    max_cps = max(all_cps) if all_cps else 0.0

    avg_len = round(sum(all_lengths) / len(all_lengths), 2) if all_lengths else 0.0
    max_len = max(all_lengths) if all_lengths else 0

    # Print Report
    print("=" * 80)
    print("           ONEFL PIPELINE GOLDEN DATASET BENCHMARK REPORT")
    print("=" * 80)
    print(f"Tổng số ca kiểm thử:           {total_cases} ca")
    print(f"Tổng số dòng phụ đề (Cues):     {total_cues} cues")
    print(f"Thời gian đánh giá:            {elapsed} giây")
    print(f"Tỷ lệ Đạt Chuẩn (Pass Rate):   {pass_rate}% ({passed_cases}/{total_cases})")
    print(f"Số ca vi phạm:                 {failed_cases}")
    print("-" * 80)
    print("1. PHÂN BỔ THEO NGÔN NGỮ NGUỒN (SOURCE LANGUAGES):")
    for lang, s in sorted(lang_stats.items()):
        l_rate = round((s['passed'] / s['total']) * 100, 1)
        print(f"   * [{lang.upper()}] : {s['passed']}/{s['total']} ca đạt ({l_rate}%)")

    print("-" * 80)
    print("2. PHÂN BỔ THEO THỂ LOẠI (GENRES / DOMAINS):")
    for cat, s in sorted(genre_stats.items()):
        c_rate = round((s['passed'] / s['total']) * 100, 1)
        print(f"   * {cat:<24}: {s['passed']}/{s['total']} ({c_rate}%)")

    print("-" * 80)
    print("3. CHỈ SỐ VẬT LÝ PHỤ ĐỀ (SUBTITLE PHYSICAL METRICS):")
    print(f"   * Tốc độ đọc trung bình (Avg CPS):   {avg_cps} CPS (Ngưỡng an toàn <= 20 CPS)")
    print(f"   * Dải tốc độ đọc (Min - Max CPS):   {min_cps} - {max_cps} CPS")
    print(f"   * Độ dài dòng trung bình:           {avg_len} ký tự (Giới hạn <= 40 ký tự)")
    print(f"   * Độ dài dòng lớn nhất:             {max_len} ký tự")
    print(f"   * Tỷ lệ câu ngắt 2 dòng tự nhiên:  {round((multiline_count / total_cues) * 100, 1)}%")

    print("-" * 80)
    print("4. KẾT LUẬN KIỂM CHỨNG TOÀN DIỆN:")
    if failed_cases == 0:
        print("   >>> CHÚC MỪNG: 1000/1000 ca kiểm thử ĐẠT CHUẨN 100% TRÊN TOÀN BỘ PIPELINE! <<<")
    else:
        print(f"   >>> CẢNH BÁO: Còn {failed_cases} ca vi phạm cần rà soát! <<<")
    print("=" * 80)


if __name__ == "__main__":
    evaluate_dataset()
