# Kế Hoạch Triển Khai: Bộ Golden Dataset (1000 Ca Kiểm Thử) & Nâng Cấp Toàn Diện Engine Dịch Thuật Tiếng Việt Theo Ngữ Cảnh Video

> **Mục tiêu**: Xây dựng bộ Golden Dataset gồm 1000 kịch bản phụ đề video chất lượng cao (Anh, Trung, Nhật, Hàn -> Việt) để kiểm thử toàn diện toàn bộ pipeline (Backend, Frontend, Agent, Tools). Đồng thời cập nhật toàn bộ hệ thống từ vựng, từ điển thuật ngữ tiếng Việt chuẩn điện ảnh, cẩm nang quy tắc dịch thuật dựa trên ngữ cảnh thị giác của video (video visual context) và nâng cấp Guardrails.  
> **Kiến trúc & Tác động**: Tác động tích cực đến toàn bộ pipeline OneFL; cung cấp bộ benchmark chuẩn mực cho ASR, LLM Router, 4-Tier Guardrails, Subtitle Generator và Frontend VideoPlayer; tuyệt đối không gây suy giảm hiệu năng xử lý video 10h/50GB.  
> **Tech Stack liên quan**: Python 3.11, FastAPI, Pydantic V2, pysubs2, Pytest, Next.js 14, TypeScript, JSON Schema.  

---

## 1. TIÊU CHUẨN KỸ THUẬT ONEFL (ONEFL TECHNICAL GATE)
- [x] **RAM & VRAM Scale**: Dataset được lưu trữ dạng JSON có cấu trúc tối ưu (hoặc theo streaming chunk), script benchmark chạy batching không ngốn RAM.
- [x] **Async Non-blocking**: Mọi kiểm thử và service liên quan tuân thủ tuyệt đối chuẩn bất đồng bộ của FastAPI/asyncio.
- [x] **WebSocket & DB Sync**: Đảm bảo cấu trúc cues trong Golden Dataset tương thích 100% với schema `SubtitleCue`, `SpeakerProfile`, `RelationshipMatrix` và các bản tin WebSocket.
- [x] **Cleanup**: Script sinh và test dataset ghi trực tiếp vào `data/golden_dataset_1000.json` và dọn dẹp các tệp tạm nếu có.
- [x] **Windows Shell**: Đường dẫn, lệnh chạy pytest và encoding UTF-8 tương thích 100% môi trường Windows PowerShell.

---

## 2. BẢNG TỆP TIN ẢNH HƯỞNG (FILE IMPACT MATRIX)

| Hành động | Đường dẫn file | Mô tả thay đổi |
| :--- | :--- | :--- |
| **Create** | [`backend/app/resources/glossary_master.json`](file:///D:/OneFL/backend/app/resources/glossary_master.json) | Từ điển thuật ngữ chuẩn mực 1000+ từ (EN, ZH, JA, KO -> VI) đa thể loại |
| **Modify** | [`backend/app/services/prompt_builder.py`](file:///D:/OneFL/backend/app/services/prompt_builder.py) | Nâng cấp Prompt Engine với quy tắc dịch dựa trên ngữ cảnh thị giác video, xử lý từ đồng âm ASR, từ lóng và khẩu khí nhân vật |
| **Modify** | [`backend/app/services/guardrails.py`](file:///D:/OneFL/backend/app/services/guardrails.py) | Mở rộng Tier 2 đại từ kép/gia đình/chức vụ và Tier 3 regex matching thuật ngữ |
| **Modify** | [`Translation_Engine_Specification.md`](file:///D:/OneFL/Translation_Engine_Specification.md) | Bổ sung Cẩm nang dịch thuật tiếng Việt chuyên sâu theo ngữ cảnh video |
| **Create** | [`scripts/generate_golden_dataset.py`](file:///D:/OneFL/scripts/generate_golden_dataset.py) | Script sinh 1000 ca kiểm thử Golden Dataset đa ngôn ngữ, đa thể loại, giàu ngữ cảnh |
| **Create** | [`data/golden_dataset_1000.json`](file:///D:/OneFL/data/golden_dataset_1000.json) | Bộ dữ liệu Golden Dataset 1000 mẫu hoàn chỉnh |
| **Create** | [`frontend/src/data/golden_dataset_sample.json`](file:///D:/OneFL/frontend/src/data/golden_dataset_sample.json) | Trích xuất mẫu Golden Dataset cho Frontend testing |
| **Create** | [`tests/test_golden_dataset.py`](file:///D:/OneFL/tests/test_golden_dataset.py) | Test suite tự động kiểm thử toàn bộ 1000 ca qua schema, guardrails, subtitle formatting |
| **Create** | [`scripts/eval_golden_dataset.py`](file:///D:/OneFL/scripts/eval_golden_dataset.py) | Công cụ đánh giá benchmark tổng thể (Pass rate, CPS, Line wrap, Độ chính xác từ vựng) |
| **Modify** | [`.agents/SESSION_STATE.md`](file:///D:/OneFL/.agents/SESSION_STATE.md) | Ghi nhận mốc triển khai và trạng thái thực thi |

---

## 3. DANH SÁCH TÁC VỤ NGUYÊN TỬ (ATOMIC TASKS)

### Task 1: Xây dựng Từ điển Thuật ngữ Chuẩn Mực Đa Ngôn Ngữ (`glossary_master.json`)
- **File mục tiêu**: [`backend/app/resources/glossary_master.json`](file:///D:/OneFL/backend/app/resources/glossary_master.json)
- **Chi tiết thực hiện**:
  - Biên tập và chuẩn hóa 1000+ thuật ngữ và quán ngữ cốt lõi (300 EN->VI, 300 ZH->VI, 200 JA->VI, 200 KO->VI).
  - Phân loại rõ theo 8 thể loại: Cơ giáp/Hành động viễn tưởng, Công nghệ/Kinh doanh, Đời thường/Tình cảm, Kiếm hiệp/Cổ trang, Hài hước/Từ lóng, Điều tra/Tội phạm, Esports/Gaming, Khoa học/Tài liệu.
  - Mỗi mục từ bao gồm: `source_term`, `target_term`, `source_lang`, `category`, `video_visual_context_note`, `pronoun_rule`, `example_usage`.
- **Lệnh kiểm chứng**:
  - Lệnh: `& "D:\OneFl\backend\.venv\Scripts\python.exe" -c "import json; d = json.load(open('backend/app/resources/glossary_master.json', encoding='utf-8')); print(f'Total terms: {len(d[\"terms\"])}'); assert len(d[\"terms\"]) >= 1000"`
  - Kết quả mong đợi: `Total terms: >= 1000`, exit code 0.

### Task 2: Nâng cấp Engine Dịch Thuật Dựa Trên Ngữ Cảnh Thị Giác Video (`prompt_builder.py`)
- **File mục tiêu**: [`backend/app/services/prompt_builder.py`](file:///D:/OneFL/backend/app/services/prompt_builder.py)
- **Chi tiết thực hiện**:
  - Bổ sung hàm `get_video_grounded_translation_rules()`: Hướng dẫn LLM giải mã các tín hiệu hình ảnh từ video (biểu cảm gương mặt, khoảng cách nhân vật, hành động trên màn hình, vật thể xung quanh) để chọn đại từ và trợ từ cảm thán (*nhé, chứ, kìa, hử, đâu, dạ, ạ*) chuẩn mực.
  - Nâng cấp `get_language_specific_rules()`: Mở rộng bộ quy tắc dịch thoát nghĩa, xử lý từ đồng âm ASR (tiếng Trung Pinyin), kính ngữ Keigo Nhật Bản và Jondaetmal Hàn Quốc.
  - Cập nhật hàm `build_translation_prompt()`: Cho phép truyền và hiển thị trường `video_context` vào user prompt.
- **Lệnh kiểm chứng**:
  - Lệnh: `& "D:\OneFl\backend\.venv\Scripts\python.exe" -m py_compile backend/app/services/prompt_builder.py`
  - Kết quả mong đợi: Exit code 0, không có lỗi cú pháp.

### Task 3: Nâng cấp Guardrails Hỗ trợ Đại từ Mở rộng và Thuật ngữ Phức hợp (`guardrails.py`)
- **File mục tiêu**: [`backend/app/services/guardrails.py`](file:///D:/OneFL/backend/app/services/guardrails.py)
- **Chi tiết thực hiện**:
  - Mở rộng tập hợp `strict_pronouns` trong Tier 2 để bao gồm các đại từ gia đình và xã hội phổ biến: `sư phụ`, `đồ nhi`, `huynh`, `đệ`, `sếp`, `bác`, `chú`, `cháu`, `con`, `bố`, `mẹ`, `tiền bối`, `hậu bối`, `đại ca`.
  - Cải tiến Tier 3 regex matching: Hỗ trợ tìm kiếm không phân biệt hoa thường và không bị ảnh hưởng bởi dấu câu hay ngắt dòng `\n`.
- **Lệnh kiểm chứng**:
  - Lệnh: `& "D:\OneFl\backend\.venv\Scripts\pytest.exe" tests/test_guardrails.py`
  - Kết quả mong đợi: 6/6 tests pass.

### Task 4: Cập nhật Cẩm nang Dịch Thuật Tiếng Việt Theo Video (`Translation_Engine_Specification.md`)
- **File mục tiêu**: [`Translation_Engine_Specification.md`](file:///D:/OneFL/Translation_Engine_Specification.md)
- **Chi tiết thực hiện**:
  - Bổ sung Mục 6: "CẨM NANG DỊCH THUẬT TIẾNG VIỆT CHUYÊN SÂU DỰA TRÊN NGỮ CẢNH VIDEO".
  - Mô tả chi tiết nguyên lý phối hợp Âm thanh - Hình ảnh - Chữ phụ đề; bảng quy chuẩn dịch xưng hô đối xứng; xử lý chuyển đổi sắc thái cảm xúc điện ảnh.
- **Lệnh kiểm chứng**:
  - Kiểm tra tài liệu hiển thị đầy đủ, liên kết nội bộ hợp lệ.

### Task 5: Xây dựng Script Sinh 1000 Ca Kiểm Thử Golden Dataset (`scripts/generate_golden_dataset.py`)
- **File mục tiêu**: [`scripts/generate_golden_dataset.py`](file:///D:/OneFL/scripts/generate_golden_dataset.py)
- **Chi tiết thực hiện**:
  - Sinh bộ 1000 kịch bản phụ đề phong phú, bao gồm:
    - 300 ca English -> Vietnamese (Tech, Business, Daily life, Slang, Police investigation).
    - 300 ca Chinese -> Vietnamese (Mecha Sci-Fi, Wuxia/Xianxia, Modern romance, Workplace).
    - 200 ca Japanese -> Vietnamese (Keigo workplace, Anime action, Slice of life, Gaming).
    - 200 ca Korean -> Vietnamese (Corporate hierarchy, Medical, Historical drama, K-pop/Youth slang).
  - Mỗi mẫu kiểm thử gồm đầy đủ: `id`, `source_language`, `target_language`, `category`, `scene_title`, `video_context`, `speaker_profiles`, `relationship_matrix`, `glossary`, `input_cues`, `ground_truth_translation`, `guardrail_stress_type`, `test_flow_targets`.
  - Xuất ra tệp [`data/golden_dataset_1000.json`](file:///D:/OneFL/data/golden_dataset_1000.json) và mẫu frontend [`frontend/src/data/golden_dataset_sample.json`](file:///D:/OneFL/frontend/src/data/golden_dataset_sample.json).
- **Lệnh kiểm chứng**:
  - Lệnh: `& "D:\OneFl\backend\.venv\Scripts\python.exe" scripts/generate_golden_dataset.py`
  - Kết quả mong đợi: Sinh thành công 1000 mẫu, tạo tệp `data/golden_dataset_1000.json` (kích thước > 500KB).

### Task 6: Xây dựng Test Suite Tự Động Toàn Diện (`tests/test_golden_dataset.py`)
- **File mục tiêu**: [`tests/test_golden_dataset.py`](file:///D:/OneFL/tests/test_golden_dataset.py)
- **Chi tiết thực hiện**:
  - Kiểm thử cấu trúc Schema (Pydantic validation) cho toàn bộ 1000 mẫu.
  - Kiểm thử 4-Tier Guardrails trên toàn bộ 1000 bản dịch Ground Truth:
    - Tier 1: Cấu trúc JSON & ID toàn vẹn.
    - Tier 2: Không vi phạm ma trận đại từ xưng hô.
    - Tier 3: 100% thuật ngữ bắt buộc trong Glossary xuất hiện chính xác.
    - Tier 4: Độ dài dòng <= 40 ký tự, số dòng <= 2, CPS <= 20.
  - Kiểm thử SubtitleGenerator: Xuất phụ đề định dạng ASS/SRT chuẩn điện ảnh không bị lỗi cú pháp.
  - Kiểm thử tính tương thích thời gian với thuật toán Binary Search của VideoPlayer.
- **Lệnh kiểm chứng**:
  - Lệnh: `& "D:\OneFl\backend\.venv\Scripts\pytest.exe" tests/test_golden_dataset.py -v`
  - Kết quả mong đợi: Toàn bộ tests pass, 100% mẫu đạt chuẩn.

### Task 7: Xây dựng Script Đánh Giá Benchmark Pipeline (`scripts/eval_golden_dataset.py`)
- **File mục tiêu**: [`scripts/eval_golden_dataset.py`](file:///D:/OneFL/scripts/eval_golden_dataset.py)
- **Chi tiết thực hiện**:
  - Thống kê tỷ lệ pass Guardrails, CPS trung bình, phân bổ độ dài dòng, độ bao phủ thuật ngữ và ngôn ngữ.
  - Xuất báo cáo trực quan dạng bảng tổng kết trên terminal.
- **Lệnh kiểm chứng**:
  - Lệnh: `& "D:\OneFl\backend\.venv\Scripts\python.exe" scripts/eval_golden_dataset.py`
  - Kết quả mong đợi: Báo cáo hiển thị 1000/1000 test cases đạt chuẩn (100% pass rate).

---

## 4. CHECKPOINT & KẾ HOẠCH KHÔI PHỤC (ROLLBACK)
- **Review Checkpoint**: Sau khi lập plan, tiến hành triển khai có kỷ luật từng task. Sau mỗi task chạy lệnh kiểm chứng thực tế.
- **Rollback Strategy**: Nếu phát sinh lỗi, khôi phục code thông qua git hoặc file backup tạm thời.
