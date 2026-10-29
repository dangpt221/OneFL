# RULE: TECHNICAL BOUNDARIES & DOs AND DON'Ts

Tài liệu này xác định ranh giới kỹ thuật bất khả xâm phạm cho hệ thống **OneFL**.

---

## 1. RANH GIỚI KIẾN TRÚC & CÔNG NGHỆ

| Thành phần | Công nghệ CHUẨN (ĐƯỢC DÙNG) | Điều CẤM (KHÔNG ĐƯỢC DÙNG) |
| :--- | :--- | :--- |
| **Backend Framework** | FastAPI (Python 3.10+), Async def | Chuyển sang Flask, Django, ExpressJS, NestJS |
| **Data Validation** | Pydantic V2 (`pydantic>=2.7.0`), `pydantic-settings` | Pydantic V1 syntax cũ, schema không typing |
| **Database ORM** | SQLAlchemy 2.0 (Async Session), asyncpg, aiosqlite | Prisma, Drizzle, Peewee, raw sync cursor |
| **Realtime Channel** | WebSockets (`websockets>=12.0`, FastAPI WebSocket) | Polling liên tục không cần thiết |
| **Subtitle Format** | ASS, SRT, VTT qua thư viện `pysubs2` | Tự regex parse phụ đề thiếu kiểm soát cú pháp thời gian |
| **TTS Engine** | `edge-tts`, `gTTS` | Cài đặt các engine thương mại đắt tiền mà không có API key |
| **Frontend Framework** | Next.js 14 (App Router), React 18, TypeScript | Next.js Pages router cũ, Vue, Angular, Svelte |
| **UI Styling** | Tailwind CSS, Lucide React, `clsx`, `tailwind-merge` | Styled-components, Bootstrap, viết CSS nội dòng bừa bãi |

---

## 2. VIỆC NÊN LÀM (DOs)
1. **Kiểm tra dung lượng và tài nguyên**:
   - Hệ thống thiết kế cho video lên tới 10 tiếng (50GB+). Mọi hàm xử lý audio/video phải dùng stream, chunking, hoặc tiến trình ngầm (background task / worker pool).
   - Tuyệt đối không đọc toàn bộ video 50GB vào RAM (`file.read()` trực tiếp).
2. **Quản lý tiến trình bền bỉ**:
   - Ghi nhận checkpoint trạng thái (VD: Ingestion $\rightarrow$ ASR $\rightarrow$ Translation $\rightarrow$ Render $\rightarrow$ Complete) để nếu crash có thể khôi phục được từ bước gần nhất.
3. **Format link file chuẩn**:
   - Khi báo cáo với người dùng, mọi đường dẫn tệp phải là định dạng markdown có thể click được: `[tên_file](file:///D:/OneFL/...)`.

---

## 3. VIỆC TUYỆT ĐỐI KHÔNG ĐƯỢC LÀM (DON'Ts)
1. ❌ **Không tự ý cài đặt package ngoài luồng**: Không chạy `pip install` hoặc `npm install` các thư viện lớn mà không báo trước hoặc khi không có trong `requirements.txt` / `package.json`.
2. ❌ **Không can thiệp vào các đường dẫn nhạy cảm**:
   - Không can thiệp vào thư mục `.venv`, `.next`, `node_modules`, `.git`.
   - Không chạy lệnh xóa thư mục gốc hoặc junction bừa bãi.
3. ❌ **Không viết code đồng bộ (blocking) trong hàm async**:
   - Không dùng `time.sleep()`, `requests.get()` đồng bộ trong route FastAPI async; bắt buộc dùng `asyncio.sleep()` và `httpx.AsyncClient()`.
4. ❌ **Không bỏ qua việc dọn dẹp file tạm**:
   - Các file trích xuất audio tạm (`.wav`), subtitle tạm (`.srt`, `.ass`), video chunk (`.ts`, `.mp4`) trong `tmp/` phải có cơ chế dọn dẹp sau khi ghép nối hoàn tất hoặc khi job thất bại.
