# Sửa đồng bộ lồng tiếng/subtitle và nâng cấp Studio — 2026-10-22

Đã triển khai DS01–DS03 trong [báo cáo readiness](/D:/OneFl/docs/reviews/2026-10-21-dubbing-subtitle-readiness.md) cùng báo cáo thời lượng TTS. Các thay đổi nằm trong working tree; chưa commit/push và không chạy trên database/video đang sử dụng.

## Hành vi sau sửa

| Vấn đề | Thay đổi |
| --- | --- |
| DS01: audio dùng khoảng nghỉ sau cue hoặc phần đuôi video | [TTS](/D:/OneFl/backend/app/services/tts_service.py:493) giải mã speech thành PCM 24 kHz, đo số sample, giới hạn theo chính `end_time` của cue và độ dài nguồn. Đặt đúng offset, đo lại sau mỗi lần chỉnh tempo, tối đa ba lần và hệ số <=2,5. Không cắt audio để ép vừa; nếu vẫn quá dài, job thất bại với cue index và hướng dẫn rút gọn lời/sửa timing |
| DS02: preview chỉ hiện câu bắt đầu sau | [Timeline index](/D:/OneFl/frontend/src/lib/subtitleTimeline.ts:3) trả về tất cả cue đang active theo thứ tự start. [Player](/D:/OneFl/frontend/src/components/VideoPlayer.tsx:82) hiện đủ các dòng cùng thời gian; khoảng active là `[start,end)`. ASS vẫn giữ các event chồng nhau; Studio đánh dấu để người duyệt kiểm tra |
| DS03: thiếu thao tác sửa mốc | [Editor](/D:/OneFl/frontend/src/components/SubtitleEditor.tsx:70) thêm **Sửa thời gian**, input giây đến mili giây và lưu text/start/end cùng request. Client và backend kiểm tra thứ tự, số hợp lệ, giới hạn độ dài video. Lỗi lưu giữ draft; thay đổi từ tab khác hiện xung đột và chặn ghi đè draft. Tạm dừng auto-follow khi đang sửa |
| Timestamp hiển thị sai số thập phân | Formatter làm tròn theo số mili giây nguyên; 2,8 s hiện 00:02.800, có carry đúng qua giây/phút/giờ. Hàng điều khiển được phép xuống dòng trên viewport hẹp |

Giữ hội thoại đồng thời hợp lệ; hệ thống không tự bỏ một người nói để loại overlap. Việc hiển thị cùng các cue không đồng nghĩa pixel/font/line-wrap của preview trùng tuyệt đối với libass khi burn.

## Báo cáo kiểm tra đồng bộ

- Mỗi audio mới có sidecar `.timing.json` cùng phiên bản. [Schema](/D:/OneFl/backend/app/schemas/tts.py:20) gồm thời gian cue, độ dài PCM trước/sau fit, mốc audio kết thúc, hệ số tempo và cờ overlap.
- `GET /api/v1/tts/projects/{project_id}/timing` chỉ đọc báo cáo của audio hiện được project thuộc user tham chiếu. Path ngoài thư mục project bị từ chối. Báo cáo thiếu ở output cũ trả 404 kèm hướng dẫn tạo lại; file hỏng trả lỗi rõ ràng và ghi log.
- [Studio summary](/D:/OneFl/frontend/src/components/DubbingQualitySummary.tsx) hiện số cue, mức tăng tốc tối đa và số câu chồng nhau, có danh sách tối đa 50 câu cần chú ý. Báo lỗi tải có retry; request cũ bị hủy khi đổi output. Không gọi provider thêm để tạo báo cáo.
- Sửa cue vẫn dùng cơ chế invalidate audio/burn + revision/WebSocket hiện có: tab thứ hai bỏ output cũ và báo cáo cũ. Dọn cache giữ sidecar của audio còn được tham chiếu; report cũ không còn tham chiếu có thể được dọn theo retention.
- Báo cáo đo thời lượng PCM, bao gồm cả khoảng lặng provider trả về; không phải forced alignment theo từng từ, điểm phát âm, dịch đúng nghĩa hay lip-sync.

## Bằng chứng kiểm chứng

- Regression viết trước sửa tái hiện audio vượt cue, câu quá dài không bị từ chối, timing vượt video không bị chặn và API report chưa tồn tại. Frontend regression thất bại trước khi có all-active index và timing validator/formatter.
- **9 regression mới** trong [test_dubbing_sync.py](/D:/OneFl/tests/test_dubbing_sync.py) đạt: khoảng nghỉ/câu cuối, real FFmpeg tempo/decode/mux/burn, overflow, sửa timing/invalidation, quyền sở hữu/current artifact, missing/corrupt/outside report, retention.
- Với cue **1,000–2,000 s**, tone provider trả **1,800 s**: PCM sau fit dài **0,99075 s**, kết thúc **1,99075 s**, hệ số **1,82368×**. Audio giải mã từ MP4 trong vùng sau cue (sample 50000–70000 ở 24 kHz, khoảng 2,083–2,917 s) có **RMS = 0**. Câu cuối có cùng kết quả, không mượn phần đuôi video. [Số đo](/D:/OneFl/tmp/dubbing-upgrade/measurements.json), [video đã sửa](/D:/OneFl/tmp/dubbing-upgrade/verified/test_speech_stays_inside_own_c0/fixed.mp4).
- Full backend cuối: **133 passed**, 33,79 giây; một Starlette/AnyIO DeprecationWarning. [JUnit](/D:/OneFl/tmp/dubbing-upgrade/pytest-results.xml).
- Frontend `npm.cmd test`, TypeScript `--noEmit --incremental false` và production build đạt. Python app/test: **86 file** compile hợp lệ; kiểm tra whitespace các file tracked thay đổi đạt. Không ghi nhận đã chạy Ruff/Bandit/MyPy.
- Production Chromium: lượt đầu **25/25 scenario đạt**, không pageerror/unexpected requestfailed. Sau sửa formatter, chạy lại cùng suite với kiểm tra form timing trên viewport 390 px và ảnh QC; kết quả cuối ghi trong execution record bên dưới.

Một lượt full suite khi chạy đồng thời browser gặp lỗi test scheduler: hủy query làm mất kết nối SQLite `:memory:`, sau đó connection mới không còn bảng `worker_leases`. Đã đổi riêng fixture scheduler lifecycle sang SQLite file tạm có nhiều connection; **7 performance contracts** và full **133 test** sau đó đạt. Không thay đổi worker hay DSN production để che lỗi.

Lệnh tái chạy từ root (PowerShell), luôn dùng DSN tạm:

```powershell
$env:DATABASE_URL='sqlite+aiosqlite:///:memory:'
backend/.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp=tmp/dubbing-upgrade/recheck
```

Frontend: `npm.cmd test`, `node node_modules/typescript/bin/tsc --noEmit --incremental false`, `npm.cmd run build`. Browser fixture theo [README](/D:/OneFl/README.md:73); không trỏ fixture vào project/database đang dùng.

## Phạm vi còn lại

Không thêm model tách vocal/BGM, voice cloning hay lip-sync. Không gọi provider ASR/LLM/TTS thật, không tải model, không đổi `.env`. Giữ giới hạn worker, block mixing và checkpoint speech cache; fit tempo được đo lại theo cue, không thay quality/model settings để tăng tốc.

Chưa có bằng chứng chất lượng nhận dạng, nghĩa bản dịch, phát âm/đúng speaker trên video thật; chưa đo drift và RAM/VRAM cho 10h/50GB, NVENC hoặc thiết bị thật. Các bản lồng tiếng tạo trước thay đổi cần **tạo lại lồng tiếng rồi burn lại** để áp dụng quy tắc mới và có báo cáo.

## Execution record

- Lượt browser cuối trên production build sau sửa formatter: **25/25 đạt**, `errors: []`, `networkErrors: []`. Có kiểm tra bounds của cả hai input timing ở viewport 390 px, draft khi 409, xung đột từ tab khác, overlap preview, report hiện sau dubbing và biến mất khi cue thay đổi.
- [Browser results](/D:/OneFl/tmp/feature-audit/browser-results.json), [form timing mobile](/D:/OneFl/tmp/feature-audit/timing-editor-mobile.png), [QC trong Studio](/D:/OneFl/tmp/feature-audit/dubbing-quality.png), [preview overlap](/D:/OneFl/tmp/feature-audit/overlapping-preview.png). Đã mở xem các ảnh mới để kiểm tra bố cục.
- Log backend cuối chỉ có lỗi provider được cố ý tiêm vào scenario; không lỗi queue poll/pool reset. Next fixture có cảnh báo `next start` với standalone output và Node `util._extend`; không lỗi build/runtime ở lượt cuối. Docker/standalone packaging chưa được kiểm chứng bởi test này.
- Một lượt browser trung gian dùng fixture frontend cũ sau khi rebuild nên lỗi chunk; đã dừng đúng PID cũ, khởi động lại fixture và chạy lại đủ 25 scenario đạt. Dùng socket/netstat xác minh lifecycle vì Get-NetTCPConnection không trả listener trong môi trường hiện tại.
- Fixture backend/frontend đã dừng đúng PID sở hữu. Socket xác nhận không còn listener tại 8000/8100/3100. Build giữ địa chỉ backend thông thường 127.0.0.1:8000. Không còn tác vụ kiểm chứng đang chạy.
