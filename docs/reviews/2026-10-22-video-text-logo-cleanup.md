# Xóa chữ Trung và logo trên video — 2026-10-22

Đã bổ sung chế độ **Xóa chữ/logo — phục hồi nền** vào **Burn Video**. Backend hiện chạy bản mới; OpenAPI cổng 8000 đã có `inpaint` và endpoint báo cáo. Frontend cổng 3000 được giữ nguyên, chỉ cần tải lại Studio.

## Cách dùng

1. Tải xong nguồn, nhận diện/dịch và kiểm duyệt phụ đề như trước.
2. Mở **Burn Video → Xóa chữ/logo — phục hồi nền**. Giữ **Tự dò và xóa chữ Trung** nếu cần OCR toàn khung hình.
3. Với logo hình/tiếng Anh/chữ bị bỏ sót, dừng video ở khung rõ rồi chọn **Khoanh vùng trên video**. Có thể thêm/sửa vùng bằng các ô tọa độ %. Tối đa 12 vùng, từng vùng nằm trong khung và nhỏ hơn nửa ảnh.
4. Vùng cố định áp dụng suốt video. Với logo di chuyển/xuất hiện từng lúc, bật **Bám theo logo di chuyển**, chọn mốc mẫu có logo rõ và khoanh gọn. Mất dấu thì không xóa tùy tiện vùng khác; báo cáo ghi nhận lượt mất dấu.
5. Bấm **Bắt Đầu Burn Video**. Xem video đầu ra và **Kết quả xóa chữ/logo** trước khi tải/đăng. Render lại nếu cần chỉnh vùng hoặc giảm chu kỳ dò chữ.

Cấu hình lưu cùng project và mở lại được. Lỗi 409/422 giữ bản nháp trong hộp thoại. Ảnh chọn vùng chỉ là video nguồn với khung đánh dấu; không giả lập kết quả đã phục hồi.

## Thay đổi kỹ thuật

- [Schema](/D:/OneFl/backend/app/schemas/video_cleanup.py) kiểm tra tọa độ hữu hạn/chuẩn hóa, reference time, số vùng và tham số OCR; [BurnOptions](/D:/OneFl/backend/app/schemas/translation.py) thêm `inpaint` và `cleanup_options`, không thay schema database.
- [OCR](/D:/OneFl/backend/app/services/cleanup_ocr.py) chạy RapidOCR 3.10.0 trên CPU/ONNX Runtime, giới hạn cạnh OCR 1280 và 2 luồng. Chỉ nhận các chuỗi có ký tự CJK, lọc confidence. Model lấy từ wheel đã cài, sao chép có chủ đích và kiểm SHA-256 dưới `data/models/video_cleanup`. Không tự tải model lúc render.
- [Xử lý video](/D:/OneFl/backend/app/services/video_cleanup.py) theo từng frame BGR, mask OCR/vùng thủ công, template matching giữa lần dò, OpenCV Telea inpainting. FFmpeg giữ âm thanh của nguồn được chọn; ASS dịch được áp dụng sau xóa. Giữ kích thước/SAR; chuẩn hóa CFR theo FPS hữu tỉ của nguồn để thời gian xử lý khớp audio. Không nạp cả video vào RAM.
- Một cleanup worker chạy mỗi lần; pipeline vẫn dùng các checkpoint/chunk hiện có. Hủy/timeout giết và chờ các tiến trình sở hữu, dọn đầu ra dở. Lỗi encoder phần cứng mới thử lại CPU; lỗi OCR/geometry không bị che bằng fallback.
- [Workflow](/D:/OneFl/backend/app/services/workflow_engine.py) đưa cấu hình/phiên bản xử lý vào signature, yêu cầu báo cáo hợp lệ khi tái dùng chunk, gộp số liệu đúng theo thứ tự chunk. Báo cáo `.cleanup.json` gắn với output hiện tại và được bảo vệ khỏi retention; sửa dữ liệu làm mất tham chiếu output/báo cáo cũ.
- [API](/D:/OneFl/backend/app/api/v1/pipeline.py) kiểm tra dependency/model trước khi enqueue. `GET /api/v1/projects/{id}/pipeline/cleanup-report` kiểm tra ownership và đường dẫn output hiện tại; thiếu báo cáo trả 404, báo cáo hỏng trả lỗi rõ ràng.
- [Editor](/D:/OneFl/frontend/src/components/VideoCleanupEditor.tsx) dùng đúng tỷ lệ video, pointer capture và ô số để chọn vùng bằng bàn phím; [modal](/D:/OneFl/frontend/src/components/BurnProgressModal.tsx), [API client](/D:/OneFl/frontend/src/lib/api.ts) và Studio dùng chung kiểu BurnOptions. [Báo cáo UI](/D:/OneFl/frontend/src/components/CleanupQualitySummary.tsx) hủy request cũ khi đổi output, có thao tác đọc lại.
- Dependency cleanup là extra tùy chọn. CI cài extra để chạy kiểm tra pixel/media. Docker có build arg `INSTALL_CLEANUP=true`; phải chuẩn bị model rõ ràng trên volume data. Đã kiểm tra trên Windows, chưa chạy container.

## Bằng chứng thực tế

| Kiểm tra | Kết quả |
| --- | --- |
| Backend đầy đủ | **183 passed**, một cảnh báo deprecation Starlette/AnyIO có sẵn |
| Frontend regression và TypeScript | `npm.cmd test` và `tsc --noEmit --incremental false`: exit 0 |
| Production build nguồn sao chép | Exit 0; gặp EPERM khi copy symlink node_modules cho standalone. Bundle hoạt động; chưa chứng nhận đóng gói standalone |
| Chromium trên frontend production/FastAPI fixture | **5/5** kịch bản pass; không có pageerror |
| Khoanh vùng | Pointer đúng tọa độ, nhập số, bật/tắt tracking, giữ bản nháp sau HTTP 422/409, lưu/mở lại cấu hình, không tràn ngang viewport 390px |
| Render từ UI thật | Job BURN COMPLETED, 45/45 frame có xóa vùng, báo cáo/MP4 tải được; giữ audio và phụ đề mới |
| Kiểm pixel đầu ra UI | Dấu trắng gốc mean 254,805 → vùng đã xóa mean 99,662 trên nền màu; phụ đề mới max 251, kích thước giữ 320×240 |
| Render nhiều chunk + resume | Giữ audio/duration, gộp báo cáo 2 chunk/30 frame và tái dùng checkpoint hợp lệ |
| Lỗi/hủy | Thiếu model không tạo job; người khác không đọc được báo cáo; guard 50%; giữ SAR; từ chối HDR; hủy chờ worker dừng; encoder GPU lỗi thử CPU đúng cấu hình |
| OCR thật trên video 1080p | 1920×1080, 2 giây/30 frame, audio có; 4 lần OCR, 8 lượt nhận hai vùng chữ Trung, 30 frame được xử lý, 0 mất dấu |
| Chất lượng mẫu nền phẳng 1080p | OCR sau xử lý không còn đọc được chữ Trung; chữ Anh và ASS Việt còn. Sai lệch vùng chữ với nền trước 16,310 → sau 3,496 (thang pixel, so với nền ảnh tương ứng), không phải thang đo chất lượng video tổng quát |
| Tốc độ mẫu OCR 1080p trên CPU | Pha streaming 5,454 giây cho 2 giây video, khoảng 5,5 fps; không bao gồm toàn bộ khởi tạo/probe. Không phải realtime hay benchmark video dài |
| NVENC thật | Máy nhận `h264_nvenc`; mẫu xóa vùng 1920×1080, 8 frame, audio, output 0,53 giây pass. Không suy ra hiệu năng OCR hoặc độ ổn định NVENC nhiều giờ |

Fixture chỉ thay URL/AI provider, không gọi dịch/TTS thật. Job, DB, auth, API, WebSocket, FFmpeg, OpenCV và OCR ở các mẫu nêu trên chạy thực tế; audio kiểm chứng là tone tổng hợp, không đánh giá chất lượng giọng đọc.

Lệnh backend (DSN dùng thử):

```powershell
$env:DATABASE_URL='sqlite+aiosqlite:///:memory:'
backend/.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp=tmp/video-cleanup/final-backend
```

Bằng chứng: [log tests](/D:/OneFl/tmp/video-cleanup/backend-tests.log), [frontend tests](/D:/OneFl/tmp/video-cleanup/frontend-tests.log), [build](/D:/OneFl/tmp/video-cleanup/build.log), [browser JSON](/D:/OneFl/tmp/video-cleanup/browser-results.json), [trace](/D:/OneFl/tmp/video-cleanup/cleanup-trace.zip), [ảnh chọn vùng](/D:/OneFl/tmp/video-cleanup/cleanup-selection.png), [mobile](/D:/OneFl/tmp/video-cleanup/cleanup-mobile.png), [pixel UI](/D:/OneFl/tmp/video-cleanup/browser-pixel-evidence.json), [OCR 1080p](/D:/OneFl/tmp/video-cleanup/ocr1080/evidence.json), [ảnh trước](/D:/OneFl/tmp/video-cleanup/ocr1080/before.png), [ảnh sau](/D:/OneFl/tmp/video-cleanup/ocr1080/after.png), [video mẫu](/D:/OneFl/tmp/video-cleanup/ocr1080/clean1080.mp4), [NVENC](/D:/OneFl/tmp/video-cleanup/ocr1080/hardware-evidence.json).

## Runtime và giới hạn

Đã sao lưu SQLite, hai lần đối chiếu không có job và giữ nguyên inventory project trước khi thay backend PID 13276/launcher 27612. Backend mới **21400/launcher 12816** chạy cổng 8000; frontend **21736/3000** giữ nguyên. Health trực tiếp/proxy trả healthy, OpenAPI có mode/báo cáo mới. Project đang FAILED không được tự chạy lại, không thay nguồn hoặc dữ liệu người dùng. [Bằng chứng runtime](/D:/OneFl/tmp/video-cleanup/live-verified.json), [inventory](/D:/OneFl/tmp/video-cleanup/live-before.json).

Đã dừng đúng fixture 17420/launcher 27424 và frontend 2104 sau khi xác nhận idle/identity/listener. Socket cuối: 3000/8000 mở, 3100/8100 đóng. [Bằng chứng](/D:/OneFl/tmp/video-cleanup/fixture-shutdown.json). Không đổi `.env`, xóa media/recovery, chạy video người dùng nhiều giờ, gọi provider trả phí hay đăng lên mạng.

Đây là [inpainting Telea của OpenCV](https://docs.opencv.org/4.x/df/d3d/tutorial_py_inpainting.html), phục hồi từ pixel xung quanh. Nền phức tạp/che khuất lớn có thể nhòe, mất chi tiết hoặc nhấp nháy; chữ cách điệu/chữ xuất hiện ngắn giữa lần OCR có thể lọt. Logo không có CJK cần chọn thủ công. Không hứa xóa sạch mọi logo/chữ hoặc tái tạo đúng nền vốn bị che; zero tracking misses không chứng nhận video sạch. OCR chỉ có mẫu kiểm chứng, chưa đo recall trên nguồn Bilibili thật.

Giới hạn hiện tại: SDR 8-bit, tối đa 4K và 1–120 fps; HDR/10-bit báo lỗi yêu cầu chuyển SDR. Giữ kích thước nguồn, không biến nguồn 720p thành 1080p thật. Chưa kiểm chứng VFR phức tạp, drift/RAM 10 giờ/50 GB, chất lượng lồng tiếng/dịch của nguồn thực hay đóng gói Docker/standalone. Blocker diarization thiếu `pyannote.audio` trong [đánh giá trước](/D:/OneFl/docs/reviews/2026-10-22-publishing-readiness.md) vẫn là việc riêng, không được âm thầm thay cấu hình trong tác vụ xóa logo.

Tham khảo model/runtime: [RapidOCR 3.10.0](https://pypi.org/project/rapidocr/3.10.0/), [cấu hình upstream](https://github.com/RapidAI/RapidOCR/blob/main/python/rapidocr/config.yaml). Cài đặt và giới hạn vận hành ở [README](/D:/OneFl/README.md).
