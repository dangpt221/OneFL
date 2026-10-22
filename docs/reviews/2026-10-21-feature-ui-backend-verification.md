# Rà soát tính năng, giao diện và đồng bộ backend — 2026-10-21

Đã sửa thêm các lỗi được tái hiện trong lượt kiểm tra sau remediation. Các luồng chính đã chạy qua giao diện Chromium với API, database, hàng đợi, WebSocket và FFmpeg thật trong môi trường cô lập. Kết quả này xác nhận hành vi của các kịch bản bên dưới; chưa đủ để kết luận toàn bộ mục tiêu kiến trúc hoặc chất lượng AI ở môi trường sản xuất đã đạt.

## Môi trường và phạm vi

- Windows, Python trong virtualenv hiện có, Next.js 14.2.4, Chromium headless; desktop 1440 × 1000 và mobile viewport 390 × 844; hai tab cùng phiên đăng nhập để kiểm tra đồng bộ.
- Fixture [backend](/D:/OneFl/tests/e2e_backend.py) dùng SQLite và thư mục media riêng dưới `tmp/feature-audit/runtime`, không sử dụng database/project đang làm việc. Token trong fixture chỉ dành cho test.
- ASR trả hai cue xác định, LLM trả JSON dịch xác định, TTS tạo tone bằng FFmpeg, URL download sao chép video mẫu. Đây là các biên provider được thay thế; không gọi model/nhà cung cấp thật và không phát sinh phí AI.
- Video đầu vào thực dài 3 giây. Upload, auth/session, API, SQL, job admission/execution, WebSocket qua proxy cùng origin, xuất subtitle, PCM mixing, burn/mux/probe và phát video đều đi qua code ứng dụng thật. Render dùng CPU libx264, không kiểm chứng NVENC.
- Có một phản hồi PATCH 409 được chủ động chèn ở browser để kiểm tra giữ bản nháp và hiển thị lỗi. Kịch bản provider outage được chèn ở biên LLM để xác nhận job FAILED và reset.

## Đối chiếu tính năng đã chạy

| # | Tính năng/kịch bản | Kết quả quan sát |
|---|---|---|
| 1 | Đăng nhập/session | Trang được bảo vệ chuyển sang login; token sai hiện lỗi; token đúng vào dashboard |
| 2 | Tạo và upload qua UI | Tạo project, upload video, giữ CREATED khi không auto-start; duration 3 giây; player đọc metadata |
| 3 | Pipeline và cập nhật trực tiếp | Nút gửi job, queue chạy, xuất hiện 2 cue, trạng thái WAITING_REVIEW, nút được mở lại |
| 4 | Player | Thời gian video thực tăng, pause được, phát đến ended và trở lại nút phát |
| 5 | Sửa subtitle | Dữ liệu lưu DB, cờ is_edited được giữ, tab thứ hai tự cập nhật |
| 6 | Lỗi lưu subtitle | PATCH 409 hiện thông báo, giữ nguyên nội dung đang sửa |
| 7 | Hồ sơ nhân vật | Tạo/sửa từ API phản ánh lên UI; draft trong modal không bị reset; thay đổi từ xa hiện conflict, chặn ghi đè đến khi tải lại; lưu tốc độ từng người |
| 8 | Thuật ngữ | Thêm qua UI, nhập/xuất CSV có dấu nháy và nhiều dòng, số lượng đồng bộ giữa tab |
| 9 | Dịch lại cue đã chọn | Durable job chạy và thay bản dịch đúng các cue đã chọn |
| 10 | Lồng tiếng | Preview có audio; model chọn được truyền; lưu speed/model/matrix; per-speaker speed đến hàm synthesis; FFmpeg tạo video/audio; mở lại modal giữ cấu hình |
| 11 | Burn và nguồn phát | Chế độ không che được lưu; FFmpeg render thật; UI phát đúng output mới, không phát thêm audio lồng tiếng lần nữa |
| 12 | Render lại | Project đã hoàn thành vẫn render lại được với cinema bars; URL output có phiên bản mới |
| 13 | Export và artifact hết hạn | Xuất SRT/ASS/VTT; sửa subtitle xóa tham chiếu output cũ ở backend và cả hai tab |
| 14 | Mobile | Không tràn ngang toàn trang; điều khiển chính và nút lưu modal nằm trong viewport; có ảnh chụp kiểm chứng |
| 15 | Dashboard queue | Hai download job được nhận; project QUEUED xuất hiện trong bộ lọc PROCESSING; reset/cancel được |
| 16 | Settings | UI tải cấu hình từ backend, storage local; không thử key thật |
| 17 | Mất và nối lại WebSocket | Đóng socket, đổi cue khi ngắt kết nối, nối lại và hiển thị dữ liệu mới |
| 18 | Lỗi provider và khôi phục | LLM fixture lỗi làm FAILED; UI hiện lỗi, reset về review và mở lại thao tác |
| 19 | Xóa project ở tab khác | Tab Studio đang mở chuyển về dashboard; API project trả 404 |
| 20 | Lỗi runtime/tài nguyên | Không có pageerror JavaScript hoặc requestfailed ngoài dự kiến trong lượt chạy đạt |

Đây là kiểm tra chức năng và bố cục theo kịch bản, không phải chứng nhận accessibility đầy đủ hoặc kiểm tra mọi thiết bị/trình duyệt.

## Lỗi đã sửa trong lượt này

| Nhóm | Nguyên nhân và thay đổi |
|---|---|
| Đồng bộ dữ liệu con | Chỉ theo dõi status/progress khiến sửa speaker/glossary/subtitle không tạo thay đổi snapshot. Thêm `content_revision`, tăng revision trong cùng transaction và đưa vào chữ ký snapshot WebSocket; theo dõi cả active job/artifact để mở khóa và xóa output đúng lúc. [Service](/D:/OneFl/backend/app/services/project_changes.py), [WebSocket](/D:/OneFl/backend/app/api/v1/websocket.py) |
| Edit đua với nhận job | Kiểm tra trước request không đủ bảo vệ lúc commit. Mutation chỉ commit khi UPDATE project còn `active_job_id IS NULL`; ngược lại rollback cả dữ liệu con và trả 409. Có test hồi quy. |
| Worker sau khi xóa project | Monitor ngủ trong lúc job hoàn thành và bị xóa, sau đó đọc heartbeat trên None. Kiểm tra task đã xong sau sleep; heartbeat UPDATE có điều kiện và xử lý job không còn tồn tại. Test tái hiện lỗi trước sửa và qua sau sửa. [Worker test](/D:/OneFl/tests/test_job_worker.py) |
| Trạng thái queue/loại tác vụ | Dashboard bỏ sót QUEUED; progress còn 100% của lần trước; tracker chọn nhầm DUB khi có cả output burn. Dùng cùng hàm busy, reset progress khi enqueue và lưu `last_job_kind`; tracker phân biệt queue/burn/dub/failure. |
| Output và playback | Source/tab/audio có thể không khớp sau invalidate hoặc khi vừa dub vừa burn. Gom quyết định nguồn phát; xóa output cũ ngay khi nhận job phù hợp và khi sửa dữ liệu; không trộn audio riêng vào video đã chứa tiếng. [Playback contract](/D:/OneFl/frontend/src/lib/projectView.ts) |
| Draft và lỗi API | Bổ sung lỗi hiển thị, giữ draft khi lưu thất bại; speaker modal phát hiện thay đổi từ xa, yêu cầu tải lại trước ghi đè. Chặn full-refresh cũ ghi đè response mới; fallback polling khi mất socket. |
| Cấu hình dub/preview | Modal tải cấu hình đã lưu khi mở; bổ sung tốc độ từng speaker; preview truyền model và cache tách theo model; chặn preview đến muộn sau đóng modal. |
| Burn | Có thể render lại project hoàn thành; đồng bộ preset/range với backend, thêm lựa chọn không che, lưu cấu hình khi mở lại, hiện lỗi submit và khóa thao tác khi project bận. |
| Player và socket lifecycle | Bắt lỗi play/media; dừng đúng tại ended; tránh gọi audio.play trùng. Project bị xóa không reconnect mãi; reconnect lấy lại snapshot. |
| Mobile và tài nguyên | Navbar/action/card/modal responsive, chặn phần trang trí gây tràn ngang; bỏ tải Google Fonts từ mạng ngoài để giao diện chạy offline bằng font fallback; thêm nhãn dialog/nút đóng. |

Các thay đổi kế thừa và giữ nguyên các chỉnh sửa có sẵn trong working tree. Không commit/push, không chạy migration vào database thật. Hai cột metadata mới được cơ chế migration hiện có bổ sung khi khởi động; cần sao lưu database/media trước khi nâng cấp theo [README](/D:/OneFl/README.md).

## Bằng chứng và cách kiểm tra lại

- Backend: **97 passed**, không fail/skip. Có một DeprecationWarning từ Starlette/AnyIO; không phải lỗi test. [JUnit](/D:/OneFl/tmp/feature-audit/pytest-results.xml).
- Frontend regression: 5 modal mở từ trạng thái đóng, CSV quoted/multiline, timeline chồng/chưa sắp xếp, hợp đồng nguồn phát/busy và queue/completed/failed workflow đều pass. [Test](/D:/OneFl/frontend/tests/regressions.cjs).
- TypeScript `--noEmit` và Next production build exit 0, dựng đủ các route. Backend/app và tests: **80 file Python** compile trong memory; `git diff --check` pass.
- Browser: [script 20 kịch bản](/D:/OneFl/frontend/tests/browser-flow.cjs), [JSON kết quả](/D:/OneFl/tmp/feature-audit/browser-results.json), [Playwright trace](/D:/OneFl/tmp/feature-audit/browser-trace.zip). Trace chứa snapshot và media mẫu nên có dung lượng lớn; artifact nằm trong thư mục tmp, không phải source cần commit.
- Lượt cuối chạy đủ 20 kịch bản trên Next production build, proxy cùng origin từ frontend 3100 đến fixture backend 8000, sau bản sửa worker. Không có lỗi queue poll ngoài dự kiến. Server `next start` có thông báo khuyến nghị dùng standalone entry point và Node `util._extend` deprecation; chưa kiểm chứng đóng gói/container standalone. Build cuối vẫn trỏ backend mặc định 127.0.0.1:8000.
- Lượt cuối chạy đủ 20 kịch bản trên Next production build, proxy cùng origin từ frontend 3100 đến fixture backend 8000, sau bản sửa worker. Không có lỗi queue poll ngoài dự kiến. Server `next start` có thông báo khuyến nghị dùng standalone entry point và Node `util._extend` deprecation; chưa kiểm chứng đóng gói/container standalone. Build cuối vẫn trỏ backend mặc định 127.0.0.1:8000.
- Hình thực tế: [Studio desktop](/D:/OneFl/tmp/feature-audit/studio-desktop.png), [Studio mobile](/D:/OneFl/tmp/feature-audit/studio-mobile.png), [speaker modal mobile](/D:/OneFl/tmp/feature-audit/speaker-modal-mobile.png), [dashboard queue](/D:/OneFl/tmp/feature-audit/dashboard-queued.png), [frame video đang phát](/D:/OneFl/tmp/feature-audit/video-playing.png).

```powershell
$env:DATABASE_URL='sqlite+aiosqlite:///:memory:'
backend/.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp=tmp/verification --junitxml=tmp/verification-results.xml
npm.cmd --prefix frontend test
frontend/node_modules/.bin/tsc.cmd --project frontend/tsconfig.json --noEmit --incremental false
npm.cmd --prefix frontend run build
```

Hướng dẫn khởi động fixture/browser nằm trong [README](/D:/OneFl/README.md). Log backend có lỗi `Fixture provider unavailable` được chủ động tạo trong kịch bản 18; đó là bằng chứng đường lỗi hoạt động. Không diễn giải việc mock provider thành kiểm chứng chất lượng mô hình.

Đã dừng các tiến trình backend/frontend fixture do lượt kiểm thử tạo ra sau khi thu thập bằng chứng.

## Những yêu cầu chưa có bằng chứng đầy đủ

- Chưa đo ASR/diarization, suy luận nhân vật, dịch ngữ cảnh/xưng hô, vision, chất lượng giọng và URL tải mạng thực với provider thật. Cần media đại diện và cấu hình model hợp lệ để đánh giá.
- Chưa chạy input 10 giờ/50 GB, stress nhiều người dùng, đo RAM/VRAM/đĩa và A/V drift dài hạn; video ngắn không thay thế kiểm tra tải.
- Chưa chạy Docker/Compose, migration PostgreSQL thật, proxy HTTPS production, Secure-cookie qua HTTPS, Firefox/Safari hoặc thiết bị mobile thật. Quyền sở hữu và bảo mật có test backend, không phải pentest toàn diện.
- S3/R2/MinIO, Temporal, Redis transport và scheduler GPU phân tán vẫn là mục tiêu kiến trúc. Triển khai hiện tại là single-host, local persistent storage, DB lease và OS worker lock.

Do đó, các luồng lõi được kiểm thử đã đạt hành vi quan sát nêu trên và các lỗi tái hiện đã được sửa; không ghi nhận hệ thống đã đáp ứng trọn vẹn các mục tiêu production/scale còn thiếu bằng chứng.
