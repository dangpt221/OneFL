# ONEFL AGENT CONSTITUTION & OPERATING PROTOCOL

Tài liệu này là **Hiến pháp hoạt động tối thượng** cho AI Agent khi làm việc trên dự án **OneFL** (Hệ thống tự động dịch thuật và burn phụ đề video dung lượng lớn). Mọi hành vi, quyết định và mã nguồn phải tuân thủ nghiêm ngặt các nguyên tắc dưới đây.

---

## 1. TRIẾT LÝ VẬN HÀNH (CORE PHILOSOPHY)

1. **Hiểu rõ trước khi gõ phím**: Không bao giờ lập trình dựa trên giả định. Làm rõ yêu cầu thông qua đối thoại và phân tích ngữ cảnh trước khi thay đổi bất kỳ dòng code nào.
2. **Kỷ luật & Nhất quán**: Mọi tính năng phải ăn khớp với thiết kế tổng thể tại [`Architecture.md`](file:///D:/OneFL/Architecture.md) và [`Translation_Engine_Specification.md`](file:///D:/OneFL/Translation_Engine_Specification.md).
3. **Bằng chứng thay cho lời nói**: Chỉ tuyên bố hoàn thành khi có output kiểm chứng thực tế (test pass, server khởi động không lỗi, syntax hợp lệ). Tuyệt đối không dùng các từ mơ hồ như "chắc là được", "should work".
4. **Không mất ngữ cảnh (Anti-Amnesia)**: Sử dụng [`SESSION_STATE.md`](file:///D:/OneFL/.agents/SESSION_STATE.md) làm sổ tay ghi nhận trạng thái liên tục để không bao giờ quên mục tiêu, việc đang làm dở, hoặc các quyết định đã chốt.

---

## 2. QUY TRÌNH 4 GIAI ĐOẠN BẤT BIẾN (THE 4-PHASE LOOP)

Mọi tác vụ phức tạp phải đi qua chu trình 4 pha:

```
[Phase 1: Khảo sát & Brainstorming]
                │
                ▼
[Phase 2: Lập kế hoạch nguyên tử (Planning)]
                │
                ▼
[Phase 3: Thực thi từng bước có kỷ luật (Execution)]
                │
                ▼
[Phase 4: Kiểm chứng bằng chứng thực tế (Verification)]
```

### Phase 1: Khảo sát & Brainstorming (Khởi động tác vụ)
- **Kiểm tra trạng thái**: Đọc [`SESSION_STATE.md`](file:///D:/OneFL/.agents/SESSION_STATE.md) và `git status` để nắm bối cảnh hiện tại.
- **Đối chiếu kiến trúc**: Kiểm tra xem tính năng mới có ảnh hưởng đến pipeline video 10h/50GB, ASR (Whisper), LLM batching, WebSocket hay Next.js UI không.
- **Kích hoạt `brainstorming`**: Nếu yêu cầu còn mơ hồ hoặc có nhiều giải pháp, đặt câu hỏi làm rõ hoặc đề xuất 2-3 phương án có ưu/nhược điểm rõ ràng trước khi code.

### Phase 2: Lập kế hoạch nguyên tử (Comprehensive Atomic Planning)
- **Bắt buộc kích hoạt `writing-plans` / `concise-planning`** đối với mọi tác vụ:
  - Chạm từ 2 file trở lên hoặc ảnh hưởng tới luồng xử lý dữ liệu.
  - Sửa đổi schema database, API contract, hoặc logic pipeline video/ASR/LLM.
  - Khi người dùng yêu cầu lập kế hoạch/lập plan.
- **Tiêu chuẩn độ mịn tác vụ (Bite-Sized Granularity - 2 đến 5 phút/bước)**:
  - Tuyệt đối cấm viết task mơ hồ kiểu: *"Cập nhật ASR service"*, *"Sửa giao diện video"*, *"Fix bug database"*.
  - Mọi task con bắt buộc chỉ rõ:
    - **Tệp mục tiêu**: Đường dẫn chính xác `file:///D:/OneFL/...` kèm phạm vi dòng (ví dụ: `backend/app/services/asr_service.py:45-80`).
    - **Nhiệm vụ cụ thể**: Tên hàm, tham số đầu vào, kiểu dữ liệu trả về, xử lý ngoại lệ.
    - **Lệnh kiểm chứng (Verification Command)**: Lệnh terminal chạy thực tế trên Windows kèm kết quả mong đợi (Expected Output).
- **Cấu trúc tài liệu Kế hoạch chuẩn (Standard Plan Structure)**:
  1. **Goal**: Mục tiêu tối thượng (1-2 câu).
  2. **Architecture & Constraints**: Tác động tới pipeline video dài 10h/50GB, VRAM GPU, non-blocking async, WebSocket.
  3. **File Impact Matrix**: Bảng danh sách file Create / Modify / Delete / Test.
  4. **Detailed Atomic Tasks (Task 1 $\rightarrow$ Task N)**: Mỗi task có mã nguồn dự kiến, lệnh chạy test, và tiêu chí pass.
  5. **Review Checkpoint & Fallback Plan**: Điểm dừng xác nhận với người dùng trước khi chuyển pha thực thi.
- **Lưu trữ & Đồng bộ kế hoạch**:
  - Plan hoàn chỉnh được lưu tại `docs/plans/YYYY-MM-DD-<feature-name>.md` (hoặc đưa vào prompt nếu là tác vụ nhanh).
  - Tóm tắt checklist được ghi nhận ngay vào [`SESSION_STATE.md`](file:///D:/OneFL/.agents/SESSION_STATE.md) để chống mất ngữ cảnh.

### Phase 3: Thực thi có kỷ luật (Disciplined Execution)
- **Kích hoạt `executing-plans`, `clean-code`, `fastapi-pro`, `nextjs-best-practices`**:
  - Làm lần lượt từng bước trong checklist, không nhảy cóc.
  - Viết code có cấu trúc, type hinting đầy đủ (Pydantic V2 cho Python, TypeScript cho Next.js).
  - Bắt lỗi triệt để theo [`error-handling-patterns`](file:///D:/OneFL/.agents/skills/error-handling-patterns), không silent-catch.

### Phase 4: Kiểm chứng thực tế (Evidence-based Verification)
- **Kích hoạt `verification-before-completion`**:
  - Chạy lệnh kiểm tra thực tế: kiểm tra cú pháp Python, build frontend, kiểm tra API endpoint hoặc test unit/integration.
  - Kiểm tra log lỗi: đảm bảo không có cảnh báo nghiêm trọng hoặc ngoại lệ tiềm ẩn.
  - Đánh dấu hoàn thành [x] trong [`SESSION_STATE.md`](file:///D:/OneFL/.agents/SESSION_STATE.md).

---

## 3. BẢNG NGUYÊN TẮC DOs & DON'Ts

### NHỮNG VIỆC BẮT BUỘC LÀM (DOs)
- ✅ **Đọc file trước khi sửa**: Luôn đọc nội dung file mục tiêu để hiểu context và giữ nguyên cấu trúc/docstring có sẵn.
- ✅ **Cập nhật Session State**: Cập nhật [`SESSION_STATE.md`](file:///D:/OneFL/.agents/SESSION_STATE.md) khi bắt đầu tác vụ mới và sau khi hoàn thành một mốc quan trọng.
- ✅ **Tạo liên kết markdown có thể click được**: Luôn gắn link định dạng `file:///D:/OneFL/...` cho mọi file được nhắc tới.
- ✅ **Bám sát Tech Stack của OneFL**:
  - Backend: Python 3.10+, FastAPI, Async SQLAlchemy, Pydantic V2, WebSockets, WhisperX/Faster-Whisper, FFmpeg NVENC, PostgreSQL, Redis.
  - Frontend: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Lucide icons.
- ✅ **Tối ưu cho tài nguyên lớn**: Mọi giải pháp xử lý video/audio phải tính tới trường hợp video dài tới 10 tiếng, dung lượng 50GB+, tránh OOM RAM và tràn VRAM GPU.

### NHỮNG VIỆC TUYỆT ĐỐI KHÔNG ĐƯỢC LÀM (DON'Ts)
- ❌ **KHÔNG tự ý suy diễn (No Speculative Coding)**: Không tự thêm tính năng hoặc cấu trúc thư viện mới ngoài yêu cầu và kiến trúc dự án.
- ❌ **KHÔNG dùng từ ngữ võ đoán**: Cấm dùng "chắc là chạy được", "should be fine", "probably fixed" mà không chạy lệnh chứng minh.
- ❌ **KHÔNG phá vỡ môi trường**: Không tự ý xóa thư mục ảo `.venv`, `node_modules`, xóa Junction mà chưa hiểu rõ, hoặc chạy các lệnh git phá hủy lịch sử (`git reset --hard`, `git push -f`).
- ❌ **KHÔNG nuốt lỗi âm thầm**: Cấm dùng `except: pass` hoặc catch Exception chung chung mà không ghi log hay trả về mã lỗi rõ ràng.
- ❌ **KHÔNG phá vỡ quy ước đặt tên & kiến trúc**: Không trộn lẫn logic xử lý nặng vào controller/router API; tách biệt rõ ràng giữa Router $\rightarrow$ Service $\rightarrow$ Model $\rightarrow$ Worker.

---

## 4. CHI TIẾT CÁC QUY TẮC BỔ TRỢ

Các quy tắc chi tiết hóa nằm tại [`.agents/rules/`](file:///D:/OneFL/.agents/rules/):
- [`01-brainstorming-and-planning.md`](file:///D:/OneFL/.agents/rules/01-brainstorming-and-planning.md): Hướng dẫn đối thoại làm rõ & lập checklist.
- [`02-context-persistence.md`](file:///D:/OneFL/.agents/rules/02-context-persistence.md): Giao thức duy trì bộ nhớ và cập nhật Session State.
- [`03-dos-and-donts.md`](file:///D:/OneFL/.agents/rules/03-dos-and-donts.md): Danh mục ranh giới kỹ thuật chi tiết.
- [`04-verification-and-execution.md`](file:///D:/OneFL/.agents/rules/04-verification-and-execution.md): Hàng rào kiểm định bằng chứng trước khi kết thúc.
