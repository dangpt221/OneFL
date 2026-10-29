# Kế Hoạch Triển Khai: Hệ Thống Agent Toolkit & Function Calling Engine Cho OneFL

> **Mục tiêu**: Xây dựng bộ công cụ chuẩn hoá (Agent Toolkit) gồm 10 tools hoàn chỉnh kèm JSON Schema Pydantic V2, hệ thống Agent Runner tự động điều phối gọi tool (Function Calling / ReAct Loop) và API endpoints quản lý tools cho toàn bộ hệ thống OneFL.  
> **Kiến trúc & Tác động**: Đóng gói các services cốt lõi thành các tools có thể gọi động bởi AI Agent (Gemini / OpenAI); hỗ trợ cơ chế Reflection Loop và Guardrails; tương thích 100% với luồng video dài 10 tiếng, VRAM GPU an toàn và async non-blocking.  
> **Tech Stack liên quan**: Python 3.11, FastAPI, Pydantic V2, SQLAlchemy 2.0 Async, asyncio, Tool Calling JSON Schema.  

---

## 1. TIÊU CHUẨN KỸ THUẬT ONEFL (ONEFL TECHNICAL GATE)
- [x] **RAM & VRAM Scale**: Mọi tool gọi xử lý video/audio đều tuân thủ nguyên tắc streaming/chunking, giới hạn GPU Semaphore(2).
- [x] **Async Non-blocking**: Tất cả 10 tools và Agent Runner đều là hàm `async def`, không chặn FastAPI event loop.
- [x] **Structured Schema**: Mỗi tool có Pydantic Input Model và Output Model rõ ràng, sinh JSON Schema chuẩn Function Calling.
- [x] **Zero Speculative Code**: Tái sử dụng và liên kết chặt chẽ với các services đã được kiểm thử: `asr_service`, `speaker_profiler`, `translation_service`, `guardrails`, `video_burner`, `tts_service`.
- [x] **Windows Shell**: Toàn bộ đường dẫn và kiểm thử tương thích 100% Windows PowerShell.

---

## 2. BẢNG TỆP TIN ẢNH HƯỞNG (FILE IMPACT MATRIX)

| Hành động | Đường dẫn file | Mô tả thay đổi |
| :--- | :--- | :--- |
| **Create** | [`backend/app/agent/tools.py`](file:///D:/OneFL/backend/app/agent/tools.py) | Định nghĩa 10 Agent Tools (Pydantic V2 Schemas, Registry, Tool Execution Handlers) |
| **Create** | [`backend/app/agent/agent_runner.py`](file:///D:/OneFL/backend/app/agent/agent_runner.py) | Bộ điều phối Agent Runner (ReAct loop, Function Calling, Auto-dispatching) |
| **Create** | [`backend/app/agent/__init__.py`](file:///D:/OneFL/backend/app/agent/__init__.py) | Package init export toolkit |
| **Create** | [`backend/app/api/v1/agent.py`](file:///D:/OneFL/backend/app/api/v1/agent.py) | Router RESTful API: `/tools`, `/execute-tool`, `/chat` |
| **Modify** | [`backend/app/main.py`](file:///D:/OneFL/backend/app/main.py) | Đăng ký agent router vào FastAPI |
| **Create** | [`tests/test_agent_tools.py`](file:///D:/OneFL/tests/test_agent_tools.py) | Test suite kiểm thử toàn diện registry và 10 tools |
| **Modify** | [`.agents/SESSION_STATE.md`](file:///D:/OneFL/.agents/SESSION_STATE.md) | Ghi nhận trạng thái hoàn thành Giai đoạn 6 |

---

## 3. DANH SÁCH 10 AGENT TOOLS CHUẨN HÓA

1. `inspect_video_media`: Kiểm tra metadata, thời lượng, độ phân giải và audio sample rate của video.
2. `extract_and_transcribe_audio`: Tách audio và chạy nhận diện giọng nói ASR (Whisper).
3. `analyze_speaker_profiles`: Phân tích và trích xuất hồ sơ nhân vật (tên, giới tính, vai trò, giọng điệu).
4. `build_relationship_matrix`: Thiết lập ma trận quan hệ xưng hô đại từ giữa các nhân vật.
5. `translate_subtitle_chunk`: Dịch lô câu phụ đề theo ngữ cảnh video & sliding context window.
6. `run_subtitle_guardrails`: Kiểm định 4 tầng Guardrails và đề xuất tự động sửa lỗi.
7. `query_master_glossary`: Tra cứu từ điển chuẩn mực 1057 thuật ngữ theo từ khóa, thể loại hoặc ngôn ngữ.
8. `export_subtitles`: Xuất file phụ đề điện ảnh chuẩn ASS, SRT hoặc WebVTT.
9. `generate_dubbing_audio`: Sinh âm thanh lồng tiếng AI (TTS) với tùy chỉnh giọng, tốc độ và ducking.
10. `burn_video_subtitles`: Burn phụ đề vào video kèm xử lý che phụ đề cứng tiếng Trung.

---

## 4. DANH SÁCH TÁC VỤ NGUYÊN TỬ (ATOMIC TASKS)

### Task 1: Xây dựng Module Định Nghĩa Tools & Tool Registry (`backend/app/agent/tools.py`)
- Định nghĩa class `ToolRegistry`, decorator `@tool` hoặc đăng ký hàm có Pydantic model.
- Triển khai 10 tools chuẩn hóa kết nối trực tiếp các service tương ứng.
- Sinh Function Calling JSON Schema tương thích OpenAI & Gemini.
- **Verification**: `python -c "from app.agent.tools import agent_toolkit; assert len(agent_toolkit.list_tools()) == 10"`

### Task 2: Xây dựng Agent Runner & ReAct Engine (`backend/app/agent/agent_runner.py`)
- Xây dựng `OneFLAgentRunner` có khả năng lập kế hoạch, chọn tool, thực thi tool và tổng hợp kết quả.
- Hỗ trợ reflection retry khi tool trả về lỗi.
- **Verification**: Biên dịch không lỗi cú pháp.

### Task 3: Xây dựng API Endpoint Cho Agent (`backend/app/api/v1/agent.py` & `main.py`)
- `GET /api/v1/agent/tools`: Lấy danh sách schema.
- `POST /api/v1/agent/execute-tool`: Chạy tool đơn lẻ.
- `POST /api/v1/agent/chat`: Chat điều phối gọi tool.
- Đăng ký vào `app/main.py`.
- **Verification**: TestClient gọi `/api/v1/agent/tools` trả về 200 OK với 10 tools.

### Task 4: Viết Test Suite Tự Động Toàn Diện (`tests/test_agent_tools.py`)
- Viết các test case kiểm tra:
  - Khởi tạo 10 tools đầy đủ.
  - JSON schema hợp lệ.
  - Thực thi độc lập các tools: `query_master_glossary`, `run_subtitle_guardrails`, `export_subtitles`, v.v.
- **Verification**: `pytest tests/test_agent_tools.py` pass 100%.

### Task 5: Cập Nhật SESSION_STATE.md & Bàn Giao
- Ghi nhận trạng thái hoàn thành vào `SESSION_STATE.md`.
