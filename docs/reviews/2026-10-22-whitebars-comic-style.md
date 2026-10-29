# Dải trắng trên/dưới và kiểu phụ đề theo ảnh — 2026-10-22

Áp dụng yêu cầu che hai dải bằng nền trắng đục và phụ đề Việt in hoa, trắng, đậm nghiêng, viền đen, chữ thu hẹp ngang. Dùng preset `comic` (Arial, 36 ở hệ tọa độ 1280×720, ScaleX 80%, viền 3, bóng 1); không khẳng định trùng chính xác font trong ảnh.

## Sử dụng

1. Mở Studio → **Burn Video** → **Áp dụng kiểu mẫu**.
2. Xem trước câu phụ đề trên video gốc. Nút phát và thanh tua nằm ngoài khung có dải che.
3. Chỉnh **Chiều cao dải trên (%)** (0–28) và **Chiều cao dải dưới (%)** (0–35). Giá trị ban đầu là 11%/15%; 0 tắt riêng dải đó.
4. Chọn **Bắt Đầu Burn Video**, đợi job hoàn thành, rồi tải MP4 hoặc ASS. Dự án đã có bản render chọn **Render lại với cấu hình khác** trước.

Dự án chưa có cấu hình dùng mặc định mới; cấu hình đã lưu vẫn được giữ cho tới khi đổi. Phụ đề chỉ viết hoa khi xuất ASS/video bằng `comic`, không ghi đè chữ trong database/SRT/VTT. ASS tải từ Studio và màn hình hoàn tất dùng preset đã lưu. Menu che/màu trong player là xem trước; cấu hình xuất được lưu qua hộp thoại Burn.

Dải trắng che kín vùng đã chọn trước khi FFmpeg vẽ ASS, giữ kích thước nguồn và tiếng. Chữ/logo nằm ngoài hai dải còn nguyên; cần tăng độ cao hoặc dùng [xóa theo vùng/OCR](/D:/OneFl/docs/reviews/2026-10-22-video-text-logo-cleanup.md). Xem trước HTML minh họa kiểu; xuống dòng và font thực tế cần chốt trên MP4.

## Kiểm chứng

| Hạng mục | Bằng chứng |
| --- | --- |
| Toàn bộ backend | **199 passed**, 0 failures/errors/skips, 33,53 giây; một cảnh báo Starlette/AnyIO có sẵn |
| Bộ kiểm tra frontend + TypeScript | `npm.cmd test` và `tsc --noEmit --incremental false`: exit 0 |
| Production build nguồn sao chép | Exit 0, compile/typecheck/pages hoàn tất. Standalone trace-copy gặp EPERM với junction node_modules trên Windows; bundle phục vụ được, chưa chứng nhận đóng gói standalone |
| Chromium trên bản cuối | **7/7** kịch bản pass, không có pageerror: default/aspect/chữ; phát/dừng/tua ngoài dải; dải 0 và khác 0; giữ draft sau 409/422; BURN thật/ASS/MP4/casing; mở lại/mobile390px; kiểu cũ/dải 0 không làm mất chữ |
| Production build nguồn sao chép | Exit 0, compile/typecheck/pages hoàn tất. Standalone trace-copy gặp EPERM với junction node_modules trên Windows; bundle phục vụ được, chưa chứng nhận đóng gói standalone |
| Chromium trên bản cuối | **7/7** kịch bản pass, không có pageerror: default/aspect/chữ; phát/dừng/tua ngoài dải; dải 0 và khác 0; giữ draft sau 409/422; BURN thật/ASS/MP4/casing; mở lại/mobile390px; kiểu cũ/dải 0 không làm mất chữ |
| Mẫu FFmpeg thật 1080p | 1920×1080 H.264 yuv420p, 15 fps, AAC 24 kHz; nguồn 1,600 giây → output 1,621 giây; có tiếng đo RMS 0,08751 |
| Pixel mẫu 1080p | Dải trên min RGB 255; dưới khi không có cue min 247 do encode; vùng giữa sai lệch mean RGB 0,04762; viền chữ nằm trong dải dưới |
| MP4 tạo từ UI/API/job thật | 320×240, 3 giây, AAC RMS 0,08778; dải trên min RGB 248, cạnh dưới mean 255; vùng giữa mean RGB error 0,1742; phụ đề hiện phía trên lớp che |
| Trường hợp biên | Dải 0 không che toàn ảnh, dải dương rất nhỏ tối thiểu 1 pixel; `mask_original_sub=false` được tôn trọng; kiểu cũ/màu cũ vẫn giữ; thay kiểu vô hiệu hóa checkpoint render cũ |
| Agent tools | Export nhận `comic`, burn nhận `white_bars`; kiểm tra artifact/job/output thật. Default Agent hiện có giữ nguyên |

Browser đã phát hiện và sửa lỗi `settings_override=null` làm Studio lỗi khi mở dự án chưa cấu hình. Có test red/green riêng và kiểu TypeScript nullable đúng API. Một kiểm tra giao diện nữa xác nhận dải trắng che native video controls; phần xem trước được chuyển sang nút phát/thanh tua bên ngoài khung, kèm lỗi phát hiển thị rõ.

Lệnh backend dùng database thử nghiệm riêng:

```powershell
$env:DATABASE_URL='sqlite+aiosqlite:///:memory:'
backend/.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp=tmp/presentation/backend-full
```

Browser dùng [fixture](/D:/OneFl/tests/e2e_backend.py) trên 8100 và bản frontend build riêng trên 3100. URL/ASR/LLM/TTS được thay bằng dữ liệu thử; auth, API, SQL, durable job, WebSocket và FFmpeg chạy thật. Không gọi provider hoặc render nguồn video người dùng.

Bằng chứng: [backend log](/D:/OneFl/tmp/presentation/backend-full.log), [JUnit](/D:/OneFl/tmp/presentation/backend-full.junit.xml), [frontend log](/D:/OneFl/tmp/presentation/frontend-tests.log), [TypeScript](/D:/OneFl/tmp/presentation/typecheck.log), [build](/D:/OneFl/tmp/presentation/build.log), [browser JSON](/D:/OneFl/tmp/presentation/browser-results.json), [trace](/D:/OneFl/tmp/presentation/presentation-trace.zip), [desktop](/D:/OneFl/tmp/presentation/style-desktop.png), [mobile](/D:/OneFl/tmp/presentation/style-mobile.png), [pixel UI](/D:/OneFl/tmp/presentation/browser-pixel-evidence.json).

## Mẫu để xem trực tiếp

- [Ảnh render thật 1080p](/D:/OneFl/tmp/presentation/reference1080/after.png)
- [Video mẫu MP4](/D:/OneFl/tmp/presentation/reference1080/white-bars-comic-1080p.mp4)
- [Ảnh nguồn trước khi che](/D:/OneFl/tmp/presentation/reference1080/before.png)
- [ASS](/D:/OneFl/tmp/presentation/reference1080/comic.ass), [thông số/pixel/audio](/D:/OneFl/tmp/presentation/reference1080/evidence.json), [script tái tạo](/D:/OneFl/tmp/presentation/reference1080/generate.py)

Mẫu là video tổng hợp ngắn, không phải kết quả hoàn thiện nguồn Bilibili của người dùng. Tính năng giữ độ phân giải nguồn, không biến nguồn thấp thành 1080p thật. Chưa chứng nhận video 10 giờ/50 GB, drift nhiều giờ, tốc độ GPU, độ chính xác dịch/giọng hoặc xóa mọi logo. Blocker diarization đã nêu trong [đánh giá khả năng xuất bản](/D:/OneFl/docs/reviews/2026-10-22-publishing-readiness.md) vẫn riêng biệt; không âm thầm thay `.env` hoặc cài Torch.

## Runtime đã bàn giao

Đã sao lưu SQLite, đối chiếu hai lần queue rảnh và inventory giữ nguyên, rồi thay đúng backend 21400/launcher12816 bằng **28704/launcher2860**, cổng 8000. Frontend **21736/3000** giữ nguyên. Health trực tiếp/proxy HTTP200, OpenAPI đã có `comic`/`white_bars` mặc định; Chromium mở Studio thực tế và chọn thử cấu hình trong draft thành công, không có pageerror hoặc request thay đổi project. [Runtime](/D:/OneFl/tmp/presentation/live-verified.json), [browser live](/D:/OneFl/tmp/presentation/live-browser.json), [ảnh live](/D:/OneFl/tmp/presentation/live-style.png), [inventory](/D:/OneFl/tmp/presentation/live-before.json), [backup](/D:/OneFl/tmp/presentation/live-before.sqlite).

Dự án hiện có vẫn FAILED, chưa có video local hoặc cue; không tự chạy lại download/ASR/dịch/burn. Cập nhật tính năng không đồng nghĩa đã tạo xong video thật của dự án này. Không đổi `.env`, xóa media/recovery, gọi provider, commit/push hoặc đăng mạng.

Sau khi xác minh fixture rảnh/identity/listener, đã dừng đúng backend21256/launcher24960 và frontend13572. Socket cuối: 3000/8000 mở, 3100/8100 đóng; [bằng chứng](/D:/OneFl/tmp/presentation/fixture-shutdown.json). Log backend mới và fixture không có ERROR/Traceback; Next có cảnh báo standalone và Node util._extend đã nêu. Chưa kiểm chứng Docker/standalone packaging.

## Runtime đã bàn giao

Đã sao lưu SQLite, đối chiếu hai lần queue rảnh và inventory giữ nguyên, rồi thay đúng backend 21400/launcher12816 bằng **28704/launcher2860**, cổng 8000. Frontend **21736/3000** giữ nguyên. Health trực tiếp/proxy HTTP200, OpenAPI đã có `comic`/`white_bars` mặc định; Chromium mở Studio thực tế và chọn thử cấu hình trong draft thành công, không có pageerror hoặc request thay đổi project. [Runtime](/D:/OneFl/tmp/presentation/live-verified.json), [browser live](/D:/OneFl/tmp/presentation/live-browser.json), [ảnh live](/D:/OneFl/tmp/presentation/live-style.png), [inventory](/D:/OneFl/tmp/presentation/live-before.json), [backup](/D:/OneFl/tmp/presentation/live-before.sqlite).

Dự án hiện có vẫn FAILED, chưa có video local hoặc cue; không tự chạy lại download/ASR/dịch/burn. Cập nhật tính năng không đồng nghĩa đã tạo xong video thật của dự án này. Không đổi `.env`, xóa media/recovery, gọi provider, commit/push hoặc đăng mạng.

Sau khi xác minh fixture rảnh/identity/listener, đã dừng đúng backend21256/launcher24960 và frontend13572. Socket cuối: 3000/8000 mở, 3100/8100 đóng; [bằng chứng](/D:/OneFl/tmp/presentation/fixture-shutdown.json). Log backend mới và fixture không có ERROR/Traceback; Next có cảnh báo standalone và Node util._extend đã nêu. Chưa kiểm chứng Docker/standalone packaging.
