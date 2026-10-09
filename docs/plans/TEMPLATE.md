# [Tên tính năng / Module] Implementation Plan

> **Mục tiêu**: [Mô tả ngắn gọn, súc tích 1-2 câu về kết quả cụ thể cần đạt]  
> **Kiến trúc & Tác động**: [Cách tiếp cận, tác động tới pipeline xử lý video 10h/50GB, tối ưu VRAM/RAM, WebSockets, DB]  
> **Tech Stack liên quan**: [FastAPI / Pydantic V2 / SQLAlchemy / Next.js 14 / Whisper / FFmpeg]  

---

## 1. TIÊU CHUẨN KỸ THUẬT ONEFL (ONEFL TECHNICAL CHECKLIST)
- [ ] **RAM & VRAM Scale**: Đã có giải pháp stream/chunking, không load cả file lớn vào RAM.
- [ ] **Async Non-blocking**: Không có hàm đồng bộ blocking trong luồng FastAPI async.
- [ ] **WebSocket & DB Sync**: Đã tính toán việc cập nhật trạng thái realtime tới client.
- [ ] **Cleanup**: Đã có hàm dọn dẹp file tạm trong `tmp/` khi job hoàn thành hoặc lỗi.
- [ ] **Windows Shell**: Đường dẫn và tham số tương thích hoàn toàn môi trường Windows PowerShell.

---

## 2. BẢNG TỆP TIN ẢNH HƯỞNG (FILE IMPACT MATRIX)

| Hành động | Đường dẫn file | Mô tả thay đổi |
| :--- | :--- | :--- |
| **Create** | `backend/app/...` | Tạo mới schema/service |
| **Modify** | `backend/app/...:LineX-LineY` | Chỉnh sửa logic xử lý |
| **Test** | `tests/...` | Unit test / integration test |

---

## 3. DANH SÁCH TÁC VỤ NGUYÊN TỬ (ATOMIC TASKS)

### Task 1: [Tên thành phần 1]
- **File mục tiêu**: `exact/path/to/file.py:L10-L40`
- **Chi tiết thực hiện**:
  - Triển khai hàm / class...
  - Xử lý ngoại lệ...
- **Mã nguồn dự kiến**:
  ```python
  # Code snippet
  ```
- **Lệnh kiểm chứng (Verification)**:
  - Lệnh chạy: `python -m py_compile path/to/file.py`
  - Kết quả mong đợi: Exit code 0, không có syntax error.

### Task 2: [Tên thành phần 2]
- **File mục tiêu**: `exact/path/to/file.py:L50-L90`
- **Chi tiết thực hiện**:
  - ...
- **Lệnh kiểm chứng (Verification)**:
  - Lệnh chạy: `pytest tests/test_feature.py -v`
  - Kết quả mong đợi: All tests passed.

---

## 4. CHECKPOINT & KẾ HOẠCH KHÔI PHỤC (ROLLBACK)
- **Review Checkpoint**: Dừng lại xác nhận với người dùng sau Task N trước khi thực hiện bước tiếp theo.
- **Rollback Strategy**: Nếu gặp lỗi không thể giải quyết, khôi phục code bằng `git checkout ...` hoặc phương án dự phòng.
