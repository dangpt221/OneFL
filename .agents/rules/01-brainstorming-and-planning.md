# RULE: BRAINSTORMING & ATOMIC PLANNING PROTOCOL

Tài liệu này định nghĩa chi tiết quy trình bắt buộc về **Làm rõ yêu cầu (Brainstorming)** và **Lập kế hoạch thực thi nguyên tử (Atomic Planning)** trước khi Agent được phép viết bất kỳ dòng mã nào.

---

## 1. KHI NÀO PHẢI LẬP PLAN CHI TIẾT?
Agent **bắt buộc** phải lập Implementation Plan chi tiết khi gặp bất kỳ trường hợp nào sau đây:
1. Tác vụ ảnh hưởng từ **2 file trở lên**.
2. Thay đổi luồng xử lý cốt lõi (Core Pipeline): Upload file lớn, VAD splitting, Whisper ASR, LLM translation batching, Render/Burn FFmpeg NVENC, WebSocket streaming.
3. Thay đổi Database Schema, ORM Models, Pydantic Schemas, hoặc API Contracts.
4. Tác vụ gỡ lỗi phức tạp (Debug) chưa rõ nguyên nhân gốc rễ.
5. Người dùng yêu cầu rõ ràng: *"lập plan"*, *"viết kế hoạch"*, hoặc thảo luận thiết kế tính năng.

---

## 2. QUY CHUẨN ĐỘ MỊN CỦA TÁC VỤ (BITE-SIZED TASK GRANULARITY)

Mọi kế hoạch phải được phân rã thành các **Atomic Tasks (Bước nguyên tử)**. Mỗi bước tương đương **2 đến 5 phút** thực thi của lập trình viên:

### ❌ KHÔNG ĐƯỢC PHÉP (Task mơ hồ, quá lớn):
- *"Tích hợp WhisperX vào ASR service."* (Quá lớn, không kiểm chứng được)
- *"Sửa lỗi render phụ đề."* (Mơ hồ, không rõ phạm vi)
- *"Làm giao diện studio subtitle."* (Quá chung chung)

### ✅ BẮT BUỘC PHẢI VIẾT (Task nguyên tử, rõ ràng, có thể nghiệm thu):
- **Task 1.1**: Tạo dataclass `SpeakerProfile` trong [`backend/app/models/speaker.py`](file:///D:/OneFL/backend/app/models/speaker.py) với các trường `speaker_id`, `gender`, `tone`.
- **Task 1.2**: Viết unit test kiểm tra validate `SpeakerProfile` trong `tests/test_speaker.py`. Chạy lệnh `pytest` xác nhận FAIL (do chưa có logic).
- **Task 1.3**: Triển khai logic tối thiểu trong `speaker_profiler.py:30-45`.
- **Task 1.4**: Chạy lại `pytest`, xác nhận PASS với 0 lỗi.

---

## 3. CHECKLIST KIỂM ĐỊNH ĐẶC THÙ CHO DỰ ÁN ONEFL (ONEFL TECHNICAL GATE)

Trước khi chốt Plan, Agent phải tự trả lời và ghi rõ trong Plan 5 câu hỏi kỹ thuật:
1. **Dung lượng & Bộ nhớ**: Tính năng này có làm tràn RAM/VRAM khi xử lý video 10 tiếng (50GB+) không? (Có dùng streaming/chunking không? Tuyệt đối không đọc toàn bộ file vào RAM).
2. **Bất đồng bộ (Async Non-blocking)**: Có bất kỳ hàm blocking nào (`time.sleep`, `requests`, subprocess đồng bộ) bị đặt trong route FastAPI async không?
3. **Tiến trình ngầm & WebSocket**: Có gửi thông báo trạng thái qua WebSocket cho frontend không? Trạng thái có đồng bộ với DB không?
4. **Dọn dẹp file tạm**: Các file `.wav`, `.srt`, `.ts` tạm sinh ra trong thư mục `tmp/` có được dọn dẹp khi hoàn thành hoặc khi xảy ra lỗi không?
5. **Môi trường Windows**: Đường dẫn file, ffmpeg, yt-dlp có tương thích hoàn toàn với Windows PowerShell và ký tự thoát không?

---

## 4. CẤU TRÚC CHUẨN CỦA BẢN KẾ HOẠCH (STANDARD IMPLEMENTATION PLAN SPEC)

Mọi bản kế hoạch lập ra phải tuân thủ đúng định dạng sau:

```markdown
# [Tên tính năng / Tác vụ] Implementation Plan

> **Mục tiêu**: [1-2 câu mô tả kết quả cụ thể cần đạt được]  
> **Kiến trúc & Tác động**: [Cách tiếp cận, tác động tới luồng 10h/50GB video, VRAM/RAM]  
> **Tech Stack sử dụng**: [VD: FastAPI, Pydantic V2, pysubs2, Next.js 14, WebSockets]  

---

### Bảng tệp tin ảnh hưởng (File Impact Matrix)
- **Tạo mới**: `exact/path/to/new_file.py`
- **Sửa đổi**: `exact/path/to/existing_file.py:L40-L80`
- **Kiểm thử**: `tests/exact/path/to/test_file.py`

---

### Task 1: [Tên thành phần cụ thể]
- **File mục tiêu**: `exact/path/to/file.py:LineX-LineY`
- **Nhiệm vụ chi tiết**:
  - Viết/sửa hàm `function_name(param: Type) -> ReturnType`
  - Bắt ngoại lệ `SpecificException` khi lỗi xảy ra
- **Mã nguồn dự kiến**:
  ```python
  # Code minh họa chữ ký hàm và logic cốt lõi
  ```
- **Lệnh kiểm chứng (Verification)**:
  - Command: `python -m py_compile backend/app/services/new_service.py`
  - Expected: Exit code 0, không có syntax/import error.

---

### Task 2: [Tên thành phần tiếp theo]
...

---

### Checkpoint & Kế hoạch khôi phục (Rollback)
- **Điểm dừng xác nhận**: Dừng lại báo cáo cho người dùng sau Task X trước khi chạy thao tác nặng.
- **Rollback**: Cách khôi phục mã nguồn nếu phát sinh lỗi không lường trước.
```

---

## 5. QUY TRÌNH BÀN GIAO & THỰC THI (HANDOFF & EXECUTION)
1. **Lưu trữ**:
   - Nếu là kế hoạch lớn: Lưu thành tệp `docs/plans/YYYY-MM-DD-<feature-name>.md`.
   - Nếu là tác vụ trong phiên: Trình bày plan rõ ràng trong chat và ghi nhận checklist vào [`SESSION_STATE.md`](file:///D:/OneFL/.agents/SESSION_STATE.md).
2. **Xin xác nhận từ người dùng**:
   - Hỏi người dùng xem có cần điều chỉnh kiến trúc hoặc thêm ràng buộc nào trước khi thực thi không.
3. **Thực thi có kỷ luật**:
   - Bám sát từng task 1 $\rightarrow$ N, đánh dấu hoàn thành [x] sau mỗi bước có bằng chứng kiểm tra thực tế.
