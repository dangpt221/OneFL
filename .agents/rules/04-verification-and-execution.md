# RULE: VERIFICATION BEFORE COMPLETION & EXECUTION PROTOCOL

Không bao giờ được tuyên bố hoàn thành hoặc thể hiện sự thỏa mãn nếu chưa có bằng chứng kiểm nghiệm thực tế từ terminal hoặc hệ thống.

---

## 1. NGUYÊN TẮC THÉP (THE IRON LAW)

```
KHÔNG CÓ BẰNG CHỨNG KIỂM TRA MỚI NHẤT = KHÔNG ĐƯỢC BÁO CÁO HOÀN THÀNH
```

Nếu chưa chạy lệnh kiểm chứng trực tiếp trong lượt làm việc này, Agent không được phép khẳng định code chạy tốt hay lỗi đã được sửa xong.

---

## 2. GIAO THỨC KIỂM TRA 5 BƯỚC (THE 5-STEP GATE)

Trước khi gửi câu trả lời kết luận đến người dùng:

1. **XÁC ĐỊNH (IDENTIFY)**: Lệnh terminal nào sẽ chứng minh code vừa sửa hoạt động đúng?
   - Cú pháp Python: `python -m py_compile <path_to_file>`
   - Lỗi import / dependencies: `python -c "import <module>"`
   - Type check / linter: `mypy`, `ruff`, hoặc chạy test `pytest`
   - Frontend build / lint: `npm run build` hoặc `npx tsc --noEmit`
2. **CHẠY (RUN)**: Thực thi lệnh đó với công cụ terminal / run_command.
3. **ĐỌC (READ)**: Đọc toàn bộ stdout, stderr, mã thoát (exit code).
4. **ĐÁNH GIÁ (VERIFY)**:
   - Nếu có lỗi / exit code != 0: Báo cáo trung thực lỗi thực tế và đưa ra phương án khắc phục ngay.
   - Nếu exit code == 0 và kết quả như kỳ vọng: Trích dẫn bằng chứng cụ thể.
5. **KẾT LUẬN (REPORT)**: Chỉ khi đó mới được thông báo hoàn thành nhiệm vụ.

---

## 3. CÁC TÍN HIỆU CẢNH BÁO ĐỎ (RED FLAGS - PHẢI DỪNG LẠI NGAY)
- Chuẩn bị dùng các từ: "chắc chắn sẽ chạy", "có vẻ đã ổn", "should work", "probably fixed".
- Báo cáo "đã hoàn thành" ngay sau khi vừa viết code mà chưa chạy lệnh kiểm thử nào.
- Tự cho rằng code chạy đúng vì logic nhìn có vẻ hợp lý.
