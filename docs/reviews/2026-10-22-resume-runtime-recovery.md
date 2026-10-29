# Kiểm tra runtime và tìm video project c317… — 2026-10-22

## Kết quả thực tế

- Backend thật cổng 8000 vẫn nạp phiên bản cũ: OpenAPI trước xử lý có description `Resumes interrupted dubbing using existing cached clips on disk.` Sau khi kiểm tra không có job RUNNING/QUEUED hoặc active_job_id, đã sao lưu SQLite và khởi động lại đúng backend để nạp bản sửa. API hiện trả description `Reuse an active dub or queue interrupted speech from its saved config.`
- Frontend cổng 3000 giữ nguyên tiến trình. Đã đọc chunk project thực đang được phục vụ: có `getDubbingRecovery` và khóa `actionPending`. Proxy health qua 3000 healthy. Danh sách ID project hiện tại được giữ nguyên trước/sau restart.
- Project được báo `c317a3cf-f5ae-41a0-b279-2c2cfd1b29a2` **không có trong database hiện backend đang dùng** (`backend/onefl_videotrans.db`). Nó còn trong database legacy ở root (`onefl_videotrans.db`), trạng thái cũ DUBBING/64%, cập nhật từ 2026-10-01. Legacy chưa có user/job/config columns; không coi đây là bằng chứng một job hiện vẫn chạy.
- Legacy còn **6.474 cue đã dịch**, một speaker, video_duration_seconds **17.912 s** (4 giờ 58 phút 32 giây), default voice `vieneu-ngoc-huyen`. Các path source/extracted audio/ASS/SRT lưu trong record không còn trỏ tới file tồn tại tại vị trí đó.

## Tìm file theo yêu cầu người dùng

Đã tìm tên/mã `BV1RvaM6AEhi`, UUID project và phần đầu tiêu đề Trung, sau đó mở rộng theo video có thể đổi tên trên các vùng đọc được của C/D/E, thư mục người dùng, Downloads/Videos/Desktop, ổ E và metadata Thùng rác. Dùng `rg --files --hidden --no-ignore`; lượt đầu có ignore không được dùng làm kết luận. Các thư mục người dùng bị chặn ở lượt thường được kiểm tra lại bằng quyền đọc mở rộng.

- Không có video trùng mã/UUID/tên trong các vùng đã đọc được.
- Đối chiếu duration bằng FFmpeg trên 596 video ứng viên ngoài một số thư mục fixture đã biết: 132 file đọc được duration, không có file khớp 17.912 s (sai số tìm ±5 s). Những file không đọc được duration và các đường dẫn từ chối truy cập không được coi là đã loại trừ chắc chắn.
- Bốn video lớn hiện có trong outputs thuộc `BV1mdYD6kEjh`, duration khoảng 22.805 hoặc 8.339 s, không khớp nguồn này. Không tự dùng video khác chỉ vì cùng thư mục dự án.
- Kiểm tra 755 metadata Thùng rác đọc được: không có bản trùng BV/UUID; 23 đường dẫn Thùng rác vẫn không đọc được. Vì vậy kết luận là **chưa tìm thấy**, không phải đã chứng minh file bị xóa vĩnh viễn.
- Tra lại URL Bilibili suy ra từ đúng BV không lấy được metadata: yt-dlp báo `Unable to extract initial state`; công cụ web cũng không đọc được trang. Không kết luận video online đã bị gỡ, không tải video khác hoặc gọi provider AI để thay thế.

## Dữ liệu đã giữ lại

Thư mục [khôi phục](/D:/OneFl/data/recovery/c317a3cf-f5ae-41a0-b279-2c2cfd1b29a2-20261022) gồm:

- [subtitles-recovered.srt](/D:/OneFl/data/recovery/c317a3cf-f5ae-41a0-b279-2c2cfd1b29a2-20261022/subtitles-recovered.srt): **6.474/6.474 câu có bản dịch**, xuất theo timing gốc, kiểm tra số hữu hạn/start<end; cue cuối kết thúc tại 17.912 s. Đây là phục hồi nội dung, không phải chấm lại độ đúng nghĩa.
- **16.715 file MP3 cache** và `timeline_master.pcm`: tổng 16.716 file, logical size 1.059.234.268 byte. PCM riêng 859.920.000 byte. Đã tạo NTFS hardlink trong `data/recovery` và xác nhận `samefile` cho từng file; không đọc/ghi lại nội dung audio hoặc nhân đôi toàn bộ dữ liệu.
- Thư mục recovery nằm ngoài OUTPUT_DIR và TEMP_SCRATCH_DIR được retention dọn, giữ được inode nếu đường dẫn cache cũ bị unlink. Hardlink không phải bản sao độc lập chống sửa nội dung trên cùng inode hoặc hỏng ổ đĩa. Không khẳng định từng clip cũ hoàn tất/hợp lệ chỉ từ số lượng file.
- [Legacy SQLite backup](/D:/OneFl/tmp/resume-runtime-recovery/legacy-before.sqlite) và [current SQLite backup](/D:/OneFl/tmp/resume-runtime-recovery/current-before.sqlite), tạo bằng SQLite backup API từ kết nối nguồn read-only. Không merge/overwrite project hoặc sửa cấu hình TTS thiếu bằng giá trị phỏng đoán.

## Xác minh và vận hành

Không thay đổi thêm logic ứng dụng trong lượt runtime này. Bản sửa source trước đó có báo cáo 141 backend tests/6 browser scenarios; lượt này kiểm tra **server thực**, không lặp lại hoặc nhận số test cũ làm bằng chứng runtime.

Artifacts dưới `tmp/resume-runtime-recovery`: `runtime-verification.json`, `frontend-verification.json`, `before-current.json`, `backups.json`, `cache-preservation.json`, `recovered-subtitles.json`, `expanded-search-results.json`, `all-candidate-durations.json`, `source-lookup.json`. Inventory tìm file có thể chứa path người dùng; giữ local, không gửi ra dịch vụ ngoài.

Backend mới PID **26316** tiếp tục phục vụ cổng 8000; frontend cũ PID **20152** giữ cổng 3000. Log [backend](/D:/OneFl/tmp/resume-runtime-recovery/backend-updated-error.log). Lần dừng PID thường bị Windows từ chối; đã dùng quyền được duyệt để dừng đúng tiến trình idle và nạp lại. Lần launcher trước không bind được đã thoát; không để hai backend cùng chiếm cổng.

Sau snapshot xác minh ban đầu, access log ghi nhận các POST trigger và một **DELETE 200** tới project `8434229c-7b01-4737-856f-6d11ef6ded6b` từ client đang dùng ứng dụng. Các request này không do agent gửi trong lượt phục hồi. Database hiện tại sau DELETE có 0 project; không tự hoàn tác thao tác xóa đó. Backup trước restart vẫn giữ record trước xóa, và legacy project c317/các bản khôi phục không bị thay đổi.

**Chưa thể tiếp tục lồng tiếng/xuất video của project legacy:** thiếu video nguồn, chưa có cấu hình dubbing durable đã lưu và project chưa được nhập vào DB hiện tại. Cần tìm lại một bản nguồn đúng hoặc URL lấy lại được rồi mới khôi phục project có kiểm chứng; dữ liệu phụ đề/audio đã được giữ để hỗ trợ bước đó. Không reset active_job_id, khởi tạo job/provider, tải model hoặc xóa media để làm biến mất lỗi.
