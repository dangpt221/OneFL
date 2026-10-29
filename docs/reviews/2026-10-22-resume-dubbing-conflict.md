# Sửa lỗi resume-dubbing 409 — 2026-10-22

## Nguyên nhân

Người dùng xác nhận Response là `Project already has an active job`. Backend chặn một request tạo job lồng tiếng thứ hai khi project đã có job. Giao diện trước sửa lại hiện cả **Tiếp tục chạy** và **Tiếp tục từ điểm dừng** cho mọi trạng thái processing, gồm QUEUED và DUBBING đang hoạt động. Vì vậy người dùng được mời bấm một thao tác sẽ xung đột với chính job hiện có.

Lượt này GET ID được báo trên API hiện truy cập được trả 404; bản SQLite legacy trong thư mục root có ID đó nhưng thiếu các cột job/config của schema hiện tại. Không dùng bản legacy để kết luận heartbeat/job thực đang khỏe hay bị treo; không sửa dữ liệu đó. Nguyên nhân trên được tái hiện bằng test độc lập và thông báo 409 người dùng cung cấp.

## Thay đổi

- [Resume API](/D:/OneFl/backend/app/api/v1/projects.py:391) trả cùng job ID và `already_active=true` khi project đang có đúng job DUBBING, trạng thái QUEUED/RUNNING, chưa yêu cầu hủy. Request lặp không tạo job mới và không báo đã hoàn tất media.
- Khi hai request cùng đọc trạng thái idle, một request thắng admission; request còn lại rollback, đọc lại và trả cùng job nếu đó là DUBBING. Job thuộc thao tác khác, đang hủy, thiếu record hoặc tham chiếu không nhất quán vẫn trả 409. Không clear lock để ép chạy.
- [Recovery policy](/D:/OneFl/frontend/src/lib/projectView.ts:8) chỉ cho resume khi FAILED/CANCELLED, không còn job/busy state, đúng luồng dubbing và có cấu hình đã lưu. Thiếu cấu hình hiện hướng dẫn mở Lồng Tiếng AI; job đang chạy/chờ chỉ hiện thông tin theo dõi và cơ chế tự recovery của worker.
- [Tracker](/D:/OneFl/frontend/src/components/PipelineProgressTracker.tsx:380) dùng cùng điều kiện ở cả hai vị trí nút, kiểm tra lại project trước POST, refresh nếu có job từ tab khác. Ref khóa submit ngay trong cùng lượt click để ngăn nhấp đúp; lỗi còn lại hiện inline. Failed dubbing không còn nút Thử lại gọi nhầm pipeline dịch.
- Fixture browser có work directory riêng dưới `tmp` và delay TTS để kiểm tra race. Không thay đổi model/media algorithm hoặc schema production.

## Kiểm chứng

- Regression trước sửa thất bại ở active/repeated/racing resume và hiển thị nút khi job đang hoạt động. Các trường hợp bảo vệ khác vẫn được kiểm tra sau sửa.
- **8 test backend mới**: active queued/running không cần suy diễn config, failed saved config queue một lần, conflict khác operation/đang hủy, thiếu config, request race, orphan reference không bị clear.
- Frontend `npm.cmd test` và TypeScript `--noEmit --incremental false` đạt. React SSR test trực tiếp tracker cho active/queued/failed/created/cancelled và thiếu cấu hình.
- **6/6 kịch bản production Chromium đạt**: ẩn hai resume action khi active; preflight thấy job từ tab khác và không POST; ba request HTTP đồng thời trả một job ID; nhấp đúp chỉ POST một lần và sinh MP4; 409 hợp lệ hiện inline; failed translation không hiện dubbing resume. `errors: []`, `networkErrors: []`. [JSON](/D:/OneFl/tmp/resume-dubbing-fix/browser-results.json), [ảnh lỗi inline](/D:/OneFl/tmp/resume-dubbing-fix/resume-error.png), [video sau resume trong Studio](/D:/OneFl/tmp/resume-dubbing-fix/resumed-output.png).
- Build frontend được chạy trên bản sao source trong `tmp/resume-dubbing-fix/frontend`, backend fixture cổng 8100, frontend fixture 3100. Compilation/type/static generation và build exit 0. Windows báo EPERM khi Next thử tạo symlink cho standalone packaging qua node_modules junction; browser dùng production bundle qua next start. Chưa xác nhận standalone packaging trong bản sao này.
- Full backend đầu đạt **140 passed**, một Starlette/AnyIO warning. Lượt cuối gồm thêm regression orphan được ghi dưới execution record. Python sửa đổi compile hợp lệ; `git diff --check` đạt.
- Log fixture chỉ có các lỗi TTS/translation cố ý tiêm vào để kiểm tra recovery; không lỗi queue-poll/pool reset. Next fixture có standalone/Node deprecation notices.

## Áp dụng

Tải lại Studio để nhận điều kiện nút mới. Khi job đang chạy, để worker tiếp tục theo dõi/xử lý. Sau khi job hiện tại kết thúc, khởi động lại backend nếu tiến trình không bật autoreload để nạp API sửa đổi. Không cần reset project đang chạy chỉ để loại 409.

Lượt sửa không gọi resume/reset/delete trên project thật, không restart server của người dùng, không gọi provider thật. Server người dùng 3000/8000 vẫn reachable sau khi fixture 3100/8100 được dừng đúng PID và kiểm tra bằng socket. Không đổi `.env`, DSN, migration, commit/push hoặc tăng GPU concurrency.

## Execution record

- Full suite cuối: **141 passed**, 26,43 giây, không fail/skip; một Starlette/AnyIO DeprecationWarning. [JUnit](/D:/OneFl/tmp/resume-dubbing-fix/pytest-results.xml).
- Browser 6/6 và frontend regressions đạt sau thay đổi production cuối. Regression orphan chỉ bổ sung test backend, không thay bundle browser đã kiểm tra. Fixture đã dừng; server thật 3000/8000 được giữ nguyên.
