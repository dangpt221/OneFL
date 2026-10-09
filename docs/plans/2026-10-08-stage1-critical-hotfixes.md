# Giai đoạn 1: Vá Lỗi Chặn Hệ Thống & Khởi Tạo Bộ Test Tự Động (Stage 1 Critical Hotfixes) Implementation Plan

> **Mục tiêu**: Loại bỏ triệt để nguy cơ sập RAM (OOM Crash) khi tải lên video 10h/50GB bằng cơ chế Stream-to-Disk, đồng bộ đường dẫn FFmpeg trong video burner, và thiết lập bộ Test Suite tự động đầu tiên cho OneFL.  
> **Kiến trúc & Tác động**: Tối ưu hóa xử lý I/O luồng dữ liệu lớn theo khối 8MB, loại bỏ nghẽn RAM, đảm bảo FFmpeg chạy mượt mà trên Windows kể cả khi không cài đặt FFmpeg toàn cục trong PATH.  
> **Tech Stack liên quan**: FastAPI, UploadFile, aiofiles, pytest, pytest-asyncio, FFmpeg.  

---

## 1. TIÊU CHUẨN KỸ THUẬT ONEFL (ONEFL TECHNICAL CHECKLIST)
- [x] **RAM & VRAM Scale**: Thay thế `await file.read()` bằng `while chunk := await file.read(chunk_size)`, bộ nhớ RAM chỉ tốn cố định 8MB thay vì 50GB.
- [x] **Async Non-blocking**: Sử dụng `aiofiles` bất đồng bộ hoàn toàn khi ghi file.
- [x] **Windows Shell & FFmpeg**: Đồng bộ sử dụng `settings.get_ffmpeg_bin()` tránh lỗi thiếu biến môi trường PATH.
- [x] **Zero Regressions**: Tạo bộ unit test độc lập có thể chạy bằng `pytest`.

---

## 2. BẢNG TỆP TIN ẢNH HƯỞNG (FILE IMPACT MATRIX)

| Hành động | Đường dẫn file | Mô tả thay đổi |
| :--- | :--- | :--- |
| **Modify** | `backend/app/services/storage_service.py:L31-L40` | Bổ sung phương thức `save_upload_file_stream` (Chunk 8MB) |
| **Modify** | `backend/app/api/v1/projects.py:L244-L246` | Chuyển endpoint upload sang stream-to-disk |
| **Modify** | `backend/app/services/video_burner.py:L235-L245` | Sử dụng `settings.get_ffmpeg_bin()` thay vì `settings.FFMPEG_PATH` |
| **Create** | `tests/__init__.py` | Đánh dấu package tests |
| **Create** | `tests/conftest.py` | Cấu hình fixtures cho môi trường test pytest |
| **Create** | `tests/test_storage.py` | Kiểm thử stream-to-disk |
| **Create** | `tests/test_video_burner.py` | Kiểm thử logic bộ giải mã FFmpeg và filter subtitle |
| **Create** | `tests/test_guardrails.py` | Kiểm thử 4-Tier Guardrails chất lượng phụ đề |

---

## 3. DANH SÁCH TÁC VỤ NGUYÊN TỬ (ATOMIC TASKS)

### Task 1: Cập nhật `StorageService` với cơ chế Stream-to-Disk (Chunked I/O)
- **File mục tiêu**: [`backend/app/services/storage_service.py:L30-L40`](file:///D:/OneFL/backend/app/services/storage_service.py#L30-L40)
- **Chi tiết**: Thêm `save_upload_file_stream(project_id, upload_file, chunk_size)` đọc từng khối 8MB và ghi trực tiếp vào ổ đĩa.
- **Lệnh kiểm chứng**: `python -m py_compile backend/app/services/storage_service.py` -> Expected: exit 0.

### Task 2: Chuyển đổi Endpoint Upload trong `projects.py`
- **File mục tiêu**: [`backend/app/api/v1/projects.py:L240-L250`](file:///D:/OneFL/backend/app/api/v1/projects.py#L240-L250)
- **Chi tiết**: Thay thế `content = await file.read()` bằng `await storage_service.save_upload_file_stream(project_id, file)`.
- **Lệnh kiểm chứng**: `python -m py_compile backend/app/api/v1/projects.py` -> Expected: exit 0.

### Task 3: Sửa lỗi tham chiếu FFmpeg trong `video_burner.py`
- **File mục tiêu**: [`backend/app/services/video_burner.py:L235-L245`](file:///D:/OneFL/backend/app/services/video_burner.py#L235-L245)
- **Chi tiết**: Thay `settings.FFMPEG_PATH` bằng `settings.get_ffmpeg_bin()`.
- **Lệnh kiểm chứng**: `python -m py_compile backend/app/services/video_burner.py` -> Expected: exit 0.

### Task 4: Thiết lập Thư mục Tests và Viết Test Suite cho Core Services
- **Files tạo mới**: `tests/conftest.py`, `tests/test_storage.py`, `tests/test_video_burner.py`, `tests/test_guardrails.py`.
- **Chi tiết**: Viết tests kiểm tra stream upload, filter graph FFmpeg và guardrail rules.
- **Lệnh kiểm chứng**: `.venv\Scripts\pytest tests/ -v` hoặc `python -m pytest tests/ -v` -> Expected: All tests pass.

---

## 4. CHECKPOINT & ĐỒNG BỘ SESSION STATE
- Đánh dấu hoàn thành [x] từng task vào [`SESSION_STATE.md`](file:///D:/OneFL/.agents/SESSION_STATE.md).
- Báo cáo kết quả và log output thực tế cho người dùng.
