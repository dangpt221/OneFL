# Mặc định Ngọc Huyền và sửa nghe thử 502 — 2026-10-22

Đã cấu hình `DEFAULT_TTS_VOICE=vieneu-ngoc-huyen` trong cấu hình triển khai, cấu hình mẫu và mặc định ứng dụng. Ngọc Huyền là profile Edge Hoài My sẵn có, chỉnh pitch −32 Hz, rate +12% và EQ; không phải tích hợp engine Vbee. Profile âm thanh không được thay đổi trong tác vụ này.

## Lỗi và thay đổi

Log backend thực tế lúc 13:41 cho thấy cả ba lần Edge WebSocket handshake đều trả HTTP403. `RuntimeError` bị chuyển thành 502 ở `/api/v1/tts/preview`; lỗi không xuất phát từ Next.js proxy hoặc mã giọng không tồn tại. Thư viện đang dùng là edge-tts7.2.8.

Đã cài wheel chính thức **7.3.1** và nâng yêu cầu tối thiểu trong hai manifests. Upstream7.3.0 bổ sung Sec-MS-GECv2, 7.3.1 sửa thêm lỗi xử lý ngày server phụ thuộc locale. Không tự sửa token/host/UA. [Release7.3.0](https://github.com/rany2/edge-tts/releases/tag/7.3.0), [release7.3.1](https://github.com/rany2/edge-tts/releases/tag/7.3.1).

Mặc định được đồng bộ qua ORM, schema, API, Agent preview, synthesis/timeline và danh sách giọng. Các giá trị lấy từ cấu hình, không hardcode Hoài My ở từng nhánh. Ma trận nhân vật giữ giọng đã chọn và giọng nam; thao tác upsert speaker bỏ trống voice không ghi đè giọng cũ. Các preset nhân vật theo thể loại vẫn giữ cấu hình riêng.

Giao diện ưu tiên giọng của lần lồng tiếng đã lưu → giọng của project → mặc định từ catalog → Ngọc Huyền dự phòng. Bỏ nhãn Nova cố định trên nút Studio, gắn nhãn radio và hiển thị mặc định. Lỗi provider giữ nguyên giọng, hiện hướng xử lý; không âm thầm đổi giọng hoặc tạo audio giả. Đóng hộp thoại/đổi giọng, tốc độ hoặc model vô hiệu hóa yêu cầu nghe thử cũ. Promise `play()` cũ không được dừng mẫu mới.

## Kiểm chứng

| Hạng mục | Kết quả |
| --- | --- |
| Backend toàn bộ | **225 passed**, 0 failures/errors/skips, 36,23 giây; một cảnh báo Starlette/AnyIO có sẵn |
| Provider | HTTP403 trả detail an toàn; lỗi tạm thời thử lại cùng giọng; cancellation xóa file tạm; lỗi FFmpeg không bị biến thành lỗi provider; unknown voice422 |
| Default và bảo toàn lựa chọn | Cấu hình/schema/ORM/API/Agent dùng default; giọng nam, giọng đã lưu, ma trận hiện có và preset riêng được giữ |
| Frontend | `npm.cmd test`, TypeScript: exit0 |
| Production build riêng | Exit0; standalone trace-copy EPERM do junction node_modules trên Windows. Bundle chạy được; chưa chứng nhận đóng gói standalone |
| Chromium | **7/7** kịch bản pass, không pageerror; default/preview, detail502, lỗi đến sau khi mở lại, kết quả đến sau đổi giọng, promiseplay cũ, durable dubbing lưu/mở lại và viewport390px |
| Giọng thật qua thư viện mới | Một mẫu catalog Ngọc Huyền dài **6,84 giây**, MP3 27.788 bytes, RMS **0,1443**, giải mã được; Edge7.3.1 không lỗi403 trong lần kiểm tra này |
| API/proxy đang chạy | Yêu cầu Ngọc Huyền1x/tts-1 và GET audio trả **200** ở cả backend8000 và proxy3000, đúng file mẫu thật đã kiểm chứng |

[Nghe mẫu thật](/D:/OneFl/tmp/ngoc-huyen/ngoc-huyen-preview.mp3), [bằng chứng giọng thật](/D:/OneFl/tmp/ngoc-huyen/real-provider/evidence.json), [backend log](/D:/OneFl/tmp/ngoc-huyen/backend-full.log), [JUnit](/D:/OneFl/tmp/ngoc-huyen/backend-full.junit.xml), [frontend log](/D:/OneFl/tmp/ngoc-huyen/frontend-tests.log), [TypeScript](/D:/OneFl/tmp/ngoc-huyen/typecheck.log), [build](/D:/OneFl/tmp/ngoc-huyen/build.log), [browser JSON](/D:/OneFl/tmp/ngoc-huyen/browser-results.json), [trace](/D:/OneFl/tmp/ngoc-huyen/tts-default-trace.zip), [ảnh chọn giọng](/D:/OneFl/tmp/ngoc-huyen/ngoc-huyen-selected.png), [mobile](/D:/OneFl/tmp/ngoc-huyen/ngoc-huyen-mobile.png).

Browser fixture thay các lời gọi dịch/ASR/TTS bên ngoài bằng dữ liệu thử, còn auth/API/database/job/FFmpeg chạy thật. Kiểm tra Edge thực hiện riêng bằng một mẫu catalog công khai, không lồng tiếng toàn bộ video người dùng hoặc gọi giọng trả phí. Mẫu ngắn không chứng nhận phát âm/độ tự nhiên của toàn bộ phim.

## Runtime hiện tại và nạp khi rảnh

Trong lúc sửa, người dùng đã chạy DOWNLOAD job `2e4d83f1-0568-4d0f-9546-4acf081008b5`. Backend28704/launcher2860 vẫn chạy8000; frontend do người dùng khởi động lại hiện13428/3000. Không dừng lượt tải. API từ chối PATCH default của project đang bận bằng409, nên giọng lưu của project hiện tại vẫn là Hoài My trong tiến trình cũ. Chưa tuyên bố tiến trình đó đã nạp cấu hình/thư viện mới.

Đã đưa mẫu Edge7.3.1 thật vào đúng cache preview có owner/hash của ứng dụng. Vì vậy nghe thử Ngọc Huyền mặc định1x/tts-1 qua tiến trình cũ hiện trả200; các tốc độ/text/voice chưa cache vẫn cần nạp thư viện mới. Không dùng audio giả hoặc âm thanh giọng khác để che lỗi. [Trạng thái project/preview](/D:/OneFl/tmp/ngoc-huyen/live-default-preview.json), [proxy](/D:/OneFl/tmp/ngoc-huyen/live-proxy-preview.json).

Đã khởi chạy một helper chờ hàng đợi rảnh, launcher26752. [Helper](/D:/OneFl/tmp/ngoc-huyen/apply_when_idle.py) kiểm tra đúng PID, thời điểm tạo, executable, quan hệ cha/con, listener8000, database đang cấu hình và mặc định Ngọc Huyền. Khi toàn bộ job/project đều rảnh hai lần liên tiếp, helper sao lưu SQLite, đổi giọng project cũ chỉ khi không có cấu hình/audio/render/speaker riêng, rồi nạp backend mới. Khóa ghi SQLite bao quanh lần kiểm tra cuối và stop để không ngắt job vừa được nhận. Frontend giữ nguyên.

Helper chạy tối đa6giờ và chỉ thực hiện một lần. Nếu backend được người dùng khởi động lại, cấu hình đổi hoặc guard không còn đúng, helper dừng và ghi ABORTED, không đụng tiến trình lạ. Sáu kiểm tra guard và chế độ `--check-only` đạt; nhánh stop/restart trên runtime đang bận chưa được thực thi. Trạng thái tại lúc bàn giao là **WAITING**, chưa phải COMPLETED. Xem [state](/D:/OneFl/tmp/ngoc-huyen/apply-when-idle.state.json); khi xong có [completed](/D:/OneFl/tmp/ngoc-huyen/apply-when-idle.completed.json). Không cần khởi động lại backend giữa lượt tải.

Một cảnh báo môi trường riêng còn tồn tại: `pip check` báo gTTS2.5.4 yêu cầu click<8.2 trong khi môi trường có click8.5.0. Lần nâng này chỉ thay edge-tts bằng `--no-deps`; không âm thầm thay các package khác. Ngọc Huyền dùng Edge và đã được kiểm tra thực tế; Google TTS không được chứng nhận bởi mẫu này.

Không thay source media, reset/xóa project, đổi cấu hình diarization, tự chạy lại pipeline hoặc đăng video lên mạng. Backend đang tải nguồn không đồng nghĩa dự án đã hoàn tất ASR/dịch/lồng tiếng.
