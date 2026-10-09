# Kế Hoạch Triển Khai: Platform Production, PostgreSQL, Docker uv & Chuẩn Hoá Giọng Đọc TTS 100%

> **Mục tiêu**: Hoàn thiện toàn diện dự án OneFL như một hệ thống enterprise production thực thụ: Hoàn thiện file `.env` & `.env.example`, kết nối và tự động khởi tạo database PostgreSQL (kèm script tự tạo CSDL & migration), đóng gói hệ thống Docker Compose chuẩn hoá với `uv` package manager (Rust-based ultra fast build), và triệt tiêu 100% lỗi sai lệch giọng đọc lồng tiếng (TTS voice matching guarantee).  
> **Tác động kiến trúc**: Cấu hình môi trường đa nền tảng (PostgreSQL + Async SQLAlchemy 2.0, fallback SQLite), Dockerfile multi-stage với `uv`, docker-compose đầy đủ (PostgreSQL 16, Redis 7, Backend, Frontend, MinIO), và Voice Dispatching Engine chuẩn xác 100%.  
> **Tech Stack liên quan**: Python 3.11+, FastAPI, Pydantic V2, SQLAlchemy 2.0 Async, asyncpg, PostgreSQL 16, Docker, Docker Compose, uv, Next.js 14, Edge-TTS, OpenAI TTS, gTTS.

---

## 1. TIÊU CHUẨN KỸ THUẬT ONEFL (TECHNICAL GATES)
- [x] **PostgreSQL 16 Enterprise**: Sử dụng `postgresql+asyncpg` với connection pool tối ưu (`pool_size=20`, `max_overflow=10`, `pool_recycle=3600`, `pool_pre_ping=True`). Tự động fallback sang SQLite nếu PostgreSQL offline trong môi trường dev local.
- [x] **Database Auto-Provisioning**: Tự động tạo database `onefl_videotrans` nếu chưa có trên PostgreSQL, sinh toàn bộ bảng `projects`, `video_chunks`, `subtitles`, `speaker_profiles`, `speaker_relationships`, `glossary_terms`.
- [x] **Docker Platform & uv**: Multi-stage build với `ghcr.io/astral-sh/uv:latest` cho backend giúp build nhanh gấp 10-100 lần pip thông thường; Next.js 14 standalone output cho frontend.
- [x] **100% TTS Voice Selection Accuracy**: Giọng đọc người dùng chọn (Hoài My, Nam Minh, Minh Quân, Thùy Dung, Ngọc Linh, Ngọc Huyền, Mai Lan Google, Nova, Onyx, Alloy, Echo, Fable, Shimmer) phải được thực thi chính xác 100%, không bị profile nhân vật ghi đè ngoài ý muốn, cache độc lập theo hash voice + text.

---

## 2. BẢNG TỆP TIN ẢNH HƯỞNG (FILE IMPACT MATRIX)

| Hành động | Đường dẫn file | Mô tả thay đổi |
| :--- | :--- | :--- |
| **Modify** | [`.env`](file:///D:/OneFL/.env) | Cập nhật đầy đủ toàn bộ biến môi trường production & local |
| **Modify** | [`.env.example`](file:///D:/OneFL/.env.example) | Chuẩn hóa template cấu hình mẫu với ghi chú tiếng Việt chi tiết |
| **Modify** | [`backend/app/database.py`](file:///D:/OneFL/backend/app/database.py) | Hoàn thiện kết nối PostgreSQL asyncpg với pool chuẩn, auto-init tables |
| **Create** | [`scripts/init_database.py`](file:///D:/OneFL/scripts/init_database.py) | Script CLI tự tạo database PostgreSQL, kiểm tra kết nối & tạo bảng |
| **Modify** | [`backend/app/services/tts_service.py`](file:///D:/OneFL/backend/app/services/tts_service.py) | Bổ sung đầy đủ OpenAI voices catalog, sửa triệt để voice routing và cache key |
| **Modify** | [`backend/app/api/v1/tts.py`](file:///D:/OneFL/backend/app/api/v1/tts.py) | Sửa logic ưu tiên giọng dubbing người dùng chọn 100% |
| **Create** | [`docker-compose.yml`](file:///D:/OneFL/docker-compose.yml) | Docker Compose production cho Postgres, Redis, Backend (uv), Frontend, MinIO |
| **Create** | [`backend/Dockerfile`](file:///D:/OneFL/backend/Dockerfile) | Dockerfile multi-stage sử dụng `uv` và FFmpeg |
| **Create** | [`backend/pyproject.toml`](file:///D:/OneFL/backend/pyproject.toml) | Cấu hình dự án hiện đại chuẩn `uv` package manager |
| **Create** | [`frontend/Dockerfile`](file:///D:/OneFL/frontend/Dockerfile) | Dockerfile multi-stage cho Next.js 14 standalone |
| **Create** | [`.dockerignore`](file:///D:/OneFL/.dockerignore) | Bỏ qua cache, node_modules, .venv, tmp |
| **Create** | [`tests/test_postgres_and_tts.py`](file:///D:/OneFL/tests/test_postgres_and_tts.py) | Test suite kiểm tra kết nối DB, khởi tạo bảng và 100% voice matching |
| **Modify** | [`.agents/SESSION_STATE.md`](file:///D:/OneFL/.agents/SESSION_STATE.md) | Ghi nhận trạng thái hoàn thành Giai đoạn 7 |

---

## 3. DANH SÁCH TÁC VỤ NGUYÊN TỬ (ATOMIC TASKS)

### Task 1: Chuẩn Hoá File `.env` và `.env.example`
- Điền đầy đủ các thông số production, cấu hình PostgreSQL, Redis, Object Storage, TTS, LLM (Gemini, OpenAI), FFmpeg, Video Chunking.
- **Verification**: `python -c "from app.config import settings; print(settings.DATABASE_URL, settings.APP_NAME)"`

### Task 2: Hoàn Thiện Kết Nối PostgreSQL & Script Khởi Tạo Bảng CSDL (`database.py` & `scripts/init_database.py`)
- Cấu hình SQLAlchemy 2.0 Async engine với `postgresql+asyncpg` và pool settings Supabase/PostgreSQL best practices.
- Viết `scripts/init_database.py` kiểm tra kết nối, tự động chạy `CREATE DATABASE` nếu chưa tồn tại, chạy `create_all()` tạo bảng và in bảng kiểm chứng.
- **Verification**: Chạy `python scripts/init_database.py` thành công.

### Task 3: Chuẩn Hoá 100% Độ Chính Xác Giọng Đọc Lồng Tiếng TTS (`tts_service.py` & `tts.py`)
- Mở rộng `VOICE_CATALOG` đầy đủ các giọng OpenAI: `nova`, `onyx`, `alloy`, `echo`, `fable`, `shimmer`.
- Cấu hình ánh xạ `VOICE_PROFILES` chi tiết, sửa cache key đảm bảo không dùng lại audio của giọng khác.
- Sửa hàm `_run_dubbing_task` và `dub_project_timeline`: Khi người dùng chọn giọng trong DubbingModal, giọng đó được áp dụng chính xác 100% cho các câu thoại.
- **Verification**: Chạy unit test xác minh voice matching cho từng giọng.

### Task 4: Xây Dựng Nền Tảng Docker & `uv` Package Manager (`docker-compose.yml`, `backend/Dockerfile`, `pyproject.toml`, `frontend/Dockerfile`)
- Viết `backend/pyproject.toml` định nghĩa dependencies cho `uv`.
- Viết `backend/Dockerfile` sử dụng `ghcr.io/astral-sh/uv:latest` kết hợp `python:3.11-slim`, cài đặt FFmpeg và libass.
- Viết `frontend/Dockerfile` multi-stage build cho Next.js 14.
- Viết `docker-compose.yml` gồm các service: `postgres`, `redis`, `backend`, `frontend`, `minio`.
- Viết `.dockerignore`.
- **Verification**: Kiểm tra cú pháp docker compose và file dockerfile.

### Task 5: Viết Test Suite Xác Minh & Kiểm Chứng Toàn Diện (`tests/test_postgres_and_tts.py`)
- Viết các test case kiểm tra:
  - Khởi tạo bảng CSDL và schema models.
  - Phân giải và khớp chính xác 100% giọng đọc TTS đã chọn.
  - Cache key và voice routing không bao giờ sai lệch.
- **Verification**: Chạy `pytest tests/` pass 100%.

### Task 6: Cập Nhật SESSION_STATE.md & Báo Cáo
- Cập nhật nhật ký dự án và bàn giao cho người dùng.
