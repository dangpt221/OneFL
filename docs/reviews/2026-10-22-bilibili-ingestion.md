# Sửa tải video Bilibili — 2026-10-22

Đã sửa lỗi đọc `INITIAL_STATE` cho video `BV1MHh66uEFH` và nạp mã vào backend đang chạy. Qua proxy frontend 3000, URL gốc của project trả `success: true`, platform Bilibili, duration 17550.186 giây. Project hiện tại được giữ nguyên, chưa tự chạy lại tác vụ tải/AI.

## Nguyên nhân có bằng chứng

Người dùng xác nhận video phát công khai, không cần đăng nhập. Trang video hiện không chứa `window.__INITIAL_STATE__`. API metadata không ký trả HTTP 412, nhưng endpoint WBI đã ký trả code 0, đúng BV/cid, duration 17551 giây, một page và quyền download=1. Extractor upstream chỉ dùng response này để kiểm tra chuyển hướng Bangumi, bỏ qua metadata hợp lệ của video thông thường rồi báo lỗi trích xuất.

Cả yt-dlp cũ 2026.08.19 và mới 2026.10.21 đều tái hiện lỗi trước adapter. GitHub API và PyPI trực tiếp xác nhận bản 2026.10.21; trang release do công cụ tìm kiếm lưu cache vẫn hiển thị bản tháng 8. Không lấy thông tin cache đó làm kết luận cuối.

## Thay đổi

- [Adapter Bilibili](/D:/OneFl/backend/app/services/bilibili_extractor.py:1) chuyển metadata View/owner/tags thật từ WBI sang schema initial-state để tái sử dụng phần xử lý định dạng, player, phụ đề và multipart của upstream. Chỉ đăng ký thay extractor BiliBili; không ảnh hưởng matcher YouTube/Douyin. Kiểm tra response thành công, đúng BV/AV, có cid/title/pages; giữ xử lý risk challenge, trang có state và Bangumi redirect của upstream.
- [Downloader](/D:/OneFl/backend/app/services/video_downloader.py:15) dùng adapter cho cả kiểm tra URL và tải video; phân loại lỗi Bilibili thành thông báo có hướng xử lý, giữ nguyên nguyên nhân trong log. Nhận diện nền tảng theo hostname, tránh chọn sai từ query string. Giữ validation URL, worker thread/cancellation, giới hạn fragment và selector chất lượng hiện hành.
- [Router pipeline](/D:/OneFl/backend/app/api/v1/pipeline.py:17) chạy lại DOWNLOAD khi nguồn còn là URL và chưa có file local. Chặn nhảy thẳng sang giai đoạn sau trong trường hợp thiếu nguồn; [ingestion](/D:/OneFl/backend/app/services/ingestion_service.py:11) giữ force_reprocess khi chuyển sang pipeline.
- [Modal tạo project](/D:/OneFl/frontend/src/components/CreateProjectModal.tsx:50) hiện lỗi metadata dù HTTP 200 với success:false, hiển thị lỗi proxy và bỏ phản hồi/timer trạng thái lỗi thời khi URL thay đổi, đổi sang upload hoặc đóng modal.
- Cập nhật đồng bộ [pyproject](/D:/OneFl/backend/pyproject.toml:26), [requirements](/D:/OneFl/backend/requirements.txt:20) và môi trường backend sang yt-dlp 2026.10.21. Không thêm cookie, thư viện tải khác hoặc thay `.env`.

## Kiểm chứng

| Kiểm tra | Kết quả |
| --- | --- |
| Regression backend trước sửa | 17 fail, 1 pass; lỗi thiếu adapter, thông báo, nhận diện host và retry |
| Full backend sau sửa, yt-dlp 2026.10.21 | 161 pass; một cảnh báo Starlette/AnyIO đã có |
| Metadata video thật | Đúng BV1MHh66uEFH, 17550.186 giây, 15 định dạng, 3 định dạng audio |
| Độ phân giải nguồn được liệt kê | Chiều cao 360, 480, 718 và 1078; không tuyên bố nguồn chính xác 1080p |
| CDN thật, đọc giới hạn | Video và audio mỗi luồng trả HTTP 206, đọc 65536 byte; tổng 128 KiB |
| Frontend regression / TypeScript | `npm.cmd test` và `tsc --noEmit --incremental false` exit 0 |
| Chromium modal | 6/6 pass, 0 pageerror; lỗi API/proxy, URL cũ, loading race, chuyển upload, đóng modal |
| Build nguồn riêng | Compile/types/prerender exit 0; standalone copy có symlink EPERM do junction node_modules |
| Backend đang dùng | Khởi động thành công; health 8000/3000 HTTP 200; kiểm tra URL qua 3000 success:true |
| Bảo toàn runtime | Backup SQLite trước restart; 0 job hoạt động; danh sách ID/status/source/local path trước–sau bằng nhau |

Kiểm tra full backend cũng chạy qua trên phiên bản cũ để kiểm tra tương thích; kết quả 161 pass. Lần cuối với phiên bản mới là bằng chứng chính. Browser cố ý giả lập phản hồi metadata lỗi/race để kiểm chứng UI; riêng metadata/CDN/live proxy phía trên dùng Bilibili thật, không mock và không cookie.

Các artifact nằm tại `tmp/bilibili-diagnostics`: [extract cũ](/D:/OneFl/tmp/bilibili-diagnostics/extract-2026.08.19.json), [extract mới chưa sửa](/D:/OneFl/tmp/bilibili-diagnostics/extract-2026.10.21.json), [metadata WBI](/D:/OneFl/tmp/bilibili-diagnostics/wbi-metadata.json), [extract và CDN sau sửa](/D:/OneFl/tmp/bilibili-diagnostics/extract-2026.10.21-adapter.json), [pytest XML](/D:/OneFl/tmp/bilibili-diagnostics/pytest-new-version.xml), [browser JSON](/D:/OneFl/tmp/bilibili-diagnostics/browser-results.json), [trace](/D:/OneFl/tmp/bilibili-diagnostics/browser-trace.zip), [ảnh thông báo](/D:/OneFl/tmp/bilibili-diagnostics/url-error.png), [live runtime](/D:/OneFl/tmp/bilibili-diagnostics/live-verified.json).

## Vận hành và giới hạn

Backend cũ PID 26316 được dừng sau hai lần xác nhận không có job và sao lưu SQLite. Backend mới PID 13276, launcher 27612, giữ cổng 8000; frontend người dùng được giữ nguyên. Log khởi động và lần metadata thành công không có ERROR/Traceback. Bản sao frontend dùng node_modules junction nên chưa chứng nhận đóng gói standalone trên Windows; log fixture giữ cảnh báo Next standalone và Node util._extend có sẵn.

Đã dừng đúng fixture sở hữu PID 11764/8100 và 14340/3100 sau kiểm tra tên tiến trình/cổng. Kiểm tra socket cuối xác nhận 3100/8100 trống, server người dùng 3000/8000 trả health HTTP 200. [Bằng chứng](/D:/OneFl/tmp/bilibili-diagnostics/fixture-shutdown.json).

Tải lại tab Studio rồi bấm **Thử lại** để tải lại nguồn. Không cần xóa hoặc tạo lại project. Thông báo lỗi cũ trên project chỉ được thay khi chạy lại; việc kiểm tra metadata không chỉnh sửa trạng thái project.

Chưa tải/mux toàn bộ video dài gần 5 giờ, chưa chạy ASR/dịch/burn với nguồn này. 128 KiB đọc thử xác nhận CDN nhận yêu cầu, không chứng minh hoàn tất file hoặc chất lượng xuất cuối. Adapter phụ thuộc API nội bộ extractor yt-dlp; khi cập nhật phiên bản cần chạy lại [tests](/D:/OneFl/tests/test_video_downloader.py:1). Không xử lý thay đổi hạn chế vùng, quyền tài khoản hoặc challenge ở mọi video; các trường hợp bị từ chối phải báo lỗi rõ ràng.

Tham khảo upstream: [extractor Bilibili](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/bilibili.py), [issue cùng triệu chứng](https://github.com/yt-dlp/yt-dlp/issues/17879), [release API](https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest). Không đăng issue/comment hay gửi thông tin cho bên khác.
