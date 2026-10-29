# Đánh giá khả năng làm video đăng YouTube/Facebook — 2026-10-22

**Kết luận:** OneFL có luồng tạo file hoàn chỉnh để người dùng duyệt và đăng thủ công. Cấu hình/runtime hiện tại còn điểm chặn nên chưa thể xác nhận chạy tự động một mạch ra sản phẩm đạt chất lượng xuất bản. Project Bilibili mới chưa có file đầu ra; không coi việc sửa extractor hoặc các test fixture là một video đã làm xong.

Đánh giá chỉ đọc dữ liệu/code và kiểm tra file có sẵn; không sửa cấu hình, cài dependency/model, gọi ASR/LLM/TTS, tạo job hoặc đăng video.

## Bằng chứng mới

| Phần | Quan sát thực tế |
| --- | --- |
| Project hiện tại | `625506c3-d61d-4159-aae1-058cc108ed70`, FAILED/DOWNLOAD, không có active job, 0 cue, chưa có local video/audio lồng tiếng/video burn. Đây là trạng thái cũ trước khi người dùng chạy lại sau bản sửa Bilibili |
| File burn lịch sử | [output_burned.mp4](/D:/OneFl/data/outputs/ccf2249c-5a6e-4475-828e-9cd5e13b21be/output_burned.mp4): 8.13 GB thập phân, 06:20:05.43, MP4, H.264 Main, yuv420p progressive, 1280×720, 30 fps, video ~2648 kb/s, AAC-LC stereo 44100 Hz ~194 kb/s |
| File dub lịch sử | [dubbed.mp4](/D:/OneFl/data/outputs/ccf2249c-5a6e-4475-828e-9cd5e13b21be_dubbed.mp4): 1.75 GB, 06:20:05.41, AV1 1280×720 30 fps và AAC stereo. Dubbing mux dùng copy video nên không tự đổi codec nguồn |
| Smoke decode file burn | FFmpeg giải mã cả video và audio trong ba đoạn 1 giây, bắt đầu tại giây 10, 11402 và 22802: cả ba exit 0, stderr rỗng |
| Runtime ASR | Whisper `tiny`, CPU; có Faster-Whisper và Edge TTS. Chưa đo chất lượng nhận dạng/nghĩa dịch/phát âm trên nguồn Bilibili hiện tại |
| Điểm chặn cấu hình | `ENABLE_SPEAKER_DIARIZATION=true`, có HF_TOKEN nhưng thiếu package `pyannote.audio`; import trực tiếp trả ModuleNotFoundError: pyannote |

Artifacts: [media-evidence.json](/D:/OneFl/tmp/publishing-readiness/media-evidence.json), [config-readiness.json](/D:/OneFl/tmp/publishing-readiness/config-readiness.json). Chỉ lưu tên cấu hình và boolean có credential; không xuất token/API key.

Smoke decode ở ba vị trí không chứng minh toàn bộ 6 giờ không lỗi, không chấm nội dung, không xác nhận ngôn ngữ/giọng và phụ đề trong file lịch sử. File lịch sử không phải output của project mới, cũng không chứng minh đã áp dụng bản sửa timing mới.

## Luồng và hạn chế

- Có tải/upload → ASR → dịch → duyệt/sửa text/timing → lồng tiếng → burn → tải MP4/SRT/ASS/VTT. [Burn pipeline](/D:/OneFl/backend/app/services/workflow_engine.py:393) ưu tiên video đã lồng tiếng khi có, sau đó in phụ đề và ghép chunk; [Studio](/D:/OneFl/frontend/src/app/projects/[id]/page.tsx:361) ưu tiên tải video burned. Muốn có cả giọng dịch và sub, cần lồng tiếng trước rồi burn.
- [Diarization](/D:/OneFl/backend/app/services/diarization_service.py:46) import pyannote khi bật nhận diện người nói. Với môi trường hiện tại, bước này không chạy được nếu không cài optional dependency; phương án khác là người dùng chủ động chọn cấu hình không tách người nói. Lượt đánh giá không tự đổi cấu hình/tải model.
- Tải nguồn ưu tiên chiều cao <=1080; burn giữ kích thước nguồn. Không có bảo đảm mọi video xuất 1920×1080, và file kiểm tra thực tế là 720p. Nguồn BV1MHh66uEFH được liệt kê tối đa 1078 pixel chiều cao trong lượt sửa trước.
- [Dubbing mixer](/D:/OneFl/backend/app/services/tts_service.py:591) giảm âm lượng toàn bộ track gốc rồi trộn TTS nếu mix_original bật; chưa tách riêng vocal khỏi nhạc/hiệu ứng. Tắt mix bỏ cả nhạc/hiệu ứng gốc, không chỉ bỏ giọng gốc.
- Bản sửa timing có giới hạn speech theo cue và báo cáo thời lượng; chưa chứng nhận độ đúng lời/nghĩa, phát âm hay drift nhiều giờ trên video thật. Cần duyệt trước khi xuất bản. Voice cloning/lip-sync không phải điều kiện bắt buộc để đăng một video có sub/lời đọc.
- Không thấy tích hợp đăng/schedule YouTube/Facebook trong backend/frontend hiện hành; thành phẩm được tải xuống để đăng thủ công. Không coi thiếu auto-publish là lỗi của luồng xuất file.

## Đối chiếu nền tảng

[YouTube](https://support.google.com/youtube/answer/1722171?hl=en) khuyến nghị MP4, H.264, AAC-LC và 4:2:0; tài liệu còn khuyến nghị Fast Start, audio 48 kHz và H.264 High Profile. File lịch sử có container/codec phổ biến, nhưng Main Profile/audio 44.1 kHz và pipeline chưa ép đầy đủ preset trên; đây là khác biệt với khuyến nghị, không tự chứng minh bị nền tảng từ chối.

[Meta](https://about.fb.com/news/2025/06/making-it-easier-create-videos-facebook/) công bố hợp nhất đăng video thành Reels và thay đổi giới hạn thời lượng/hình thức; không áp dụng máy móc giới hạn 90 giây cũ cho mọi video. Help Center định dạng Facebook yêu cầu đăng nhập trong lượt tra cứu, nên không chứng nhận toàn bộ thông số upload Facebook hiện tại. Chưa đăng thử lên tài khoản YouTube/Facebook nào; không cam kết khả năng xử lý của tài khoản/đường đăng chỉ từ codec.

## Việc cần hoàn thành cho video hiện tại

1. Xử lý cấu hình diarization: cài dependency/model có quyền truy cập nếu cần nhiều người nói, hoặc chọn chạy không tách người nói nếu phù hợp sản phẩm.
2. Thử lại nguồn Bilibili để thực sự tải file; chạy ASR/dịch và duyệt bản dịch/timing trên nguồn thật.
3. Tạo lồng tiếng, nghe/kiểm tra báo cáo timing, rồi burn video. Thay cue sau lồng tiếng cần tạo lại các output bị invalidate.
4. Kiểm tra hình/tiếng/sub ở đầu, giữa, cuối và chỗ chuyển chunk; kiểm tra resolution/codec/duration của đúng file cuối. Nếu cần 1080p, chọn nguồn và cấu hình xuất tương ứng trước khi nghiệm thu.
5. Tải thành phẩm và đăng kiểm tra ở chế độ phù hợp trên tài khoản đích trước khi công khai. Không thể thay kiểm tra nghe/xem bằng số lượng unit test.

Các lượt kiểm chứng trước: backend 161 pass, browser lỗi Bilibili 6/6, browser pipeline/timing 25/25 trên provider fixture. Đây là bằng chứng cơ chế; không tính thành benchmark chất lượng AI của video thật. Lượt này không thay mã sản phẩm nên không chạy lại toàn bộ suite; bằng chứng mới là DB/config inventory, import dependency và probe/decode media có sẵn.
