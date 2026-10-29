# RULE: CONTEXT PERSISTENCE & ANTI-AMNESIA PROTOCOL

Quy tắc này giải quyết triệt để vấn đề: **Agent quên ngữ cảnh, quên việc đang làm dở, mất định hướng sau nhiều lượt trao đổi**.

---

## 1. NGUỒN SỰ THẬT DUY NHẤT (SINGLE SOURCE OF TRUTH)
File [`d:\OneFl\.agents\SESSION_STATE.md`](file:///D:/OneFL/.agents/SESSION_STATE.md) là bộ nhớ trạng thái duy nhất phản ánh:
- Tác vụ hiện tại đang thực hiện là gì.
- Những quyết định kỹ thuật nào đã được chốt.
- Những việc đã làm xong (Done).
- Những việc đang làm (In Progress).
- Những việc tiếp theo cần làm (Next Steps).
- Các điểm lưu ý/rủi ro kỹ thuật.

---

## 2. GIAO THỨC ĐỌC TRẠNG THÁI (START-OF-TURN HOOK)
Khi nhận một yêu cầu mới từ người dùng:
1. **Kiểm tra trạng thái**:
   - Nếu yêu cầu là tiếp tục công việc ("tiếp tục đi", "làm bước tiếp theo", "xem lại"): Agent **bắt buộc** đọc file [`SESSION_STATE.md`](file:///D:/OneFL/.agents/SESSION_STATE.md) trước khi thao tác.
   - Nếu có tác vụ đang dở dang (`In Progress`), đối chiếu với yêu cầu của người dùng để quyết định tiếp tục hay chuyển đổi mục tiêu.
2. **Kiểm tra hiện trạng mã nguồn**:
   - Chạy lệnh `git status` hoặc kiểm tra file liên quan để đối chiếu giữa bộ nhớ tài liệu và thực tế code trên đĩa.

---

## 3. GIAO THỨC GHI NHẬN TRẠNG THÁI (END-OF-TURN HOOK)
Trước khi kết thúc một lượt làm việc (hoặc sau khi hoàn thành một bước quan trọng):
1. **Cập nhật [`SESSION_STATE.md`](file:///D:/OneFL/.agents/SESSION_STATE.md)**:
   - Đánh dấu `[x]` các mục đã hoàn tất kèm dẫn chứng file/commit ngắn gọn.
   - Chuyển mục tiếp theo sang trạng thái `[ ] Đang thực hiện`.
   - Ghi chú bất kỳ phát hiện bất thường, lỗi phát sinh hoặc quyết định kiến trúc mới.
2. **Thông báo vắn tắt cho người dùng**:
   - Tóm tắt 1-2 câu về những gì vừa làm xong và bước dự kiến tiếp theo, không để người dùng rơi vào trạng thái mơ hồ.
