# Rà soát tính năng và độ khớp lồng tiếng/phụ đề — 2026-10-21

> Cập nhật 2026-10-22: DS01–DS03 và báo cáo timing QC đã được sửa/bổ sung; xem [kết quả nâng cấp](/D:/OneFl/docs/reviews/2026-10-22-dubbing-sync-upgrade.md). Nội dung bên dưới giữ bằng chứng trước sửa. Chất lượng AI thật và các tính năng mở rộng vẫn cần đánh giá riêng.

**Kết luận:** Luồng upload → ASR → dịch → duyệt → TTS → mux/burn/export đã có. Chưa đạt tiêu chí lời lồng tiếng luôn nằm trong khoảng hiển thị subtitle. Đã đo được audio đọc tiếp sau khi chữ biến mất; với câu chồng thời gian, preview cũng khác nội dung ASS xuất ra. Độ đúng của nhận dạng, bản dịch và phát âm thực tế chưa được đánh giá bằng provider thật trong lượt này.

Đây là lượt đánh giá và tạo bằng chứng, không thay đổi logic sản phẩm. Các kết quả kiểm thử luồng trước đây vẫn chỉ chứng minh đúng phạm vi đã ghi trong báo cáo đó.

## Phát hiện cần ưu tiên

### DS01 — Quan trọng: audio có thể vượt thời điểm subtitle kết thúc

[tts_service.py](/D:/OneFl/backend/app/services/tts_service.py:493) tính cửa sổ đọc bằng `min(total_duration, max(end, next_start - 0.08)) - start`. Khi sau một câu có khoảng nghỉ, TTS được dùng cả khoảng nghỉ đó; câu cuối có thể dùng phần thời gian còn lại của video. Trong khi đó [ASS](/D:/OneFl/backend/app/services/subtitle_generator.py:119) và [preview](/D:/OneFl/frontend/src/lib/subtitleTimeline.ts:15) vẫn kết thúc theo `end_time` của cue.

Đo bằng tone thay cho provider TTS, qua chính timeline/tempo/mixer/encoder của ứng dụng, độ phân giải 25 ms:

| Ca | Subtitle (giây) | Audio đo được (giây) | Nhận xét |
| --- | --- | --- | --- |
| Câu ngắn | 0.50–1.50 | 0.50–0.90 | Đặt đúng mốc bắt đầu; phần còn lại im lặng |
| Có khoảng nghỉ trước câu sau ở giây 5 | 1.00–2.00 | 1.00–4.00 | Đọc thêm **2 giây sau khi sub tắt** |
| Cần tăng tốc để vừa cửa sổ 1 giây | 0.50–1.50 | 0.50–1.50 | Nhánh `atempo` hoạt động trên tone |
| Câu cuối, video dài 4 giây | 0.50–1.00 | 0.50–2.50 | Đọc thêm **1,5 giây sau khi sub tắt** |

Ca gap được burn/mux thành [MP4 thật](/D:/OneFl/tmp/dubbing-review/gap_after_cue/dubbed-and-burned.mp4): frame giây 1,5 có 148 pixel sáng của chữ, giây 3 không còn pixel chữ; audio giải mã từ MP4 vẫn có tone đầu từ giây 1 đến 4. MP4 dài đúng 6 giây. Vì vậy kiểm tra đúng tổng thời lượng không phát hiện được lỗi khớp từng câu.

**Đề xuất:** Chốt quy tắc căn thời gian chung cho subtitle/audio. Nếu yêu cầu đọc nằm trong cue thì giới hạn theo `end_time`; nếu cho phép dùng khoảng nghỉ thì phải điều chỉnh subtitle tương ứng trước khi export/burn. Đưa thời lượng TTS thực, hệ số tempo và mức vượt cửa sổ vào QC từng câu; không cắt mất âm cuối để che lỗi.

### DS02 — Quan trọng: câu chồng thời gian chưa có cách thể hiện thống nhất

Với cue A 1–3 giây và cue B 2–4 giây, đo được A đọc 1–2,95 và B đọc 2–3,5: cả hai âm cùng tồn tại từ 2 đến 2,95. [PCM mixer](/D:/OneFl/backend/app/services/pcm_mixer.py:18) cộng các đoạn chồng lên nhau. Đây có thể là hội thoại đồng thời hợp lệ, nhưng cũng có thể làm lời khó nghe nếu ASR chia sai.

Chạy trực tiếp [hàm index của frontend](/D:/OneFl/frontend/src/lib/subtitleTimeline.ts:3) ở giây 2,5 trả về riêng B, dù A và B cùng active. [ASS generator](/D:/OneFl/backend/app/services/subtitle_generator.py:135) giữ cả hai event. Preview hiện không phản ánh đầy đủ các câu sẽ được đưa vào ASS/burn. Kết quả riêng ở [preview-overlap.json](/D:/OneFl/tmp/dubbing-review/preview-overlap.json); lượt này không đo hình học xếp chữ của hai event trên mọi font/viewport.

**Đề xuất:** Cùng một quy tắc nhiều người nói cho preview và export, hiển thị/cảnh báo overlap và cho người duyệt sửa các mốc sai. Không tự loại hội thoại đồng thời hợp lệ chỉ để làm timeline không overlap.

### DS03 — Quan trọng: thiếu công cụ chỉnh timing trực tiếp trong Studio

[Editor](/D:/OneFl/frontend/src/components/SubtitleEditor.tsx:77) lưu bản dịch và cho đổi speaker; timestamp hiện là nút seek tại mốc bắt đầu. Chưa có input sửa start/end, waveform hay thao tác tách/gộp câu trong editor này. Backend [schema](/D:/OneFl/backend/app/schemas/subtitle.py:26) và [route](/D:/OneFl/backend/app/api/v1/subtitles.py:194) đã nhận sửa timing, nhưng chưa được nối thành thao tác UI. Khi TTS yêu cầu rút ngắn lời hoặc sửa mốc, người dùng có thể sửa lời trên UI nhưng không thể sửa timing tại đây.

**Đề xuất:** Nối chức năng sửa mốc sẵn có ở backend vào Studio, có kiểm tra khoảng thời gian, giữ draft khi lỗi và invalidate audio/burn như các thay đổi cue khác. Waveform và tách/gộp là phần mở rộng hữu ích sau đó.

## Khả năng đã có và phần còn thiếu

| Nhóm | Hiện trạng |
| --- | --- |
| Pipeline cơ bản | Có upload chia chunk/resume, URL ingestion, ASR chia chunk/checkpoint, dịch theo batch/context/glossary, duyệt, chọn giọng/người nói, dubbing, burn, ASS/SRT/VTT, job/recovery/cancel và cập nhật Studio |
| Căn thời gian audio | Có đặt offset, resample, tempo và mixer có giới hạn RAM; chưa bảo đảm speech kết thúc trước `end_time`, chưa có báo cáo đo onset/end từng câu cho người dùng |
| Nhận dạng theo từ | [ASR](/D:/OneFl/backend/app/services/asr_service.py:129) yêu cầu `word_timestamps=True` nhưng chỉ lưu start/end/text của segment. Chưa lưu timestamp từng từ hoặc có bước forced alignment riêng phục vụ đối chiếu TTS/sub |
| Nhận diện nhiều người nói | Có adapter diarization tùy chọn; [mặc định trong code](/D:/OneFl/backend/app/config.py:83) tắt. Khi tắt, mặc định SPEAKER_00; đổi giọng theo speaker không tự chứng minh nhận diện đúng người |
| Giữ nhạc nền, bỏ lời gốc | Chưa có tách vocal/BGM. [mix_original](/D:/OneFl/backend/app/services/tts_service.py:575) giảm âm lượng toàn bộ audio gốc rồi trộn TTS, nên vẫn giữ lời gốc nhỏ; tắt mix bỏ cả lời, nhạc và hiệu ứng gốc |
| Giọng đặc thù/khẩu hình | Các ID `vieneu-*` là profile Edge có rate/pitch/EQ, không phải server VieNeu độc lập. Chưa có pipeline nhân bản giọng từ mẫu hoặc lip-sync khẩu hình; đây là tính năng mở rộng nếu sản phẩm cần |
| Kiểm định chất lượng thật | Có guardrails ID/schema, glossary, đại từ, CPS và độ dài dòng. Chưa có bằng chứng WER/CER trên video chuẩn, chấm bản dịch theo nghĩa, nghe phát âm/đúng speaker hoặc đo A/V drift dài hạn bằng model thật |
| Mở rộng hạ tầng | S3/R2/MinIO, Tus/S3 direct upload, Temporal, Redis Pub/Sub và nhiều GPU host vẫn là kiến trúc đích. Hiện hỗ trợ local storage/hàng đợi một host; các phần này không phải điều kiện để thử video ngắn trên một máy |

Ngưỡng đồng bộ khi phát audio rời của [VideoPlayer](/D:/OneFl/frontend/src/components/VideoPlayer.tsx:91) là 0,3 giây trước khi seek lại. Lượt này chưa đo độ lệch audio/video trên trình duyệt với video dài, tốc độ phát khác nhau hoặc thiết bị thật; không coi ngưỡng trong code là độ chính xác đã đo.

## Kiểm chứng mới trong lượt này

- `pytest tests/test_audio_timeline.py tests/test_media_integration.py tests/test_diarization.py -q -p no:cacheprovider --basetemp=tmp/dubbing-review/pytest` với DSN in-memory: **12 passed**, 6,17 giây. Diarization tests dùng embedding/turn fixture, không chạy model thật.
- [Probe tái chạy được](/D:/OneFl/docs/reviews/2026-10-21-dubbing-sync-probes.py): 6 ca quan sát; tone vượt cửa sổ cần tempo trên 2,5 lần bị từ chối rõ ràng. 5 ca tạo audio qua FFmpeg thật; một ca từ chối có chủ đích. Kết quả ở [timing-results.json](/D:/OneFl/tmp/dubbing-review/timing-results.json). Các phát hiện lệch là kết quả audit, không được tính thành test nghiệm thu độ khớp.
- `npm.cmd test`: modal/CSV/timeline/playback/workflow/refresh regressions đạt. Test timeline hiện xác nhận lựa chọn latest-start, không khẳng định preview/export giống nhau khi overlap. Không chạy lại browser/build vì không đổi code frontend.
- `scripts/eval_golden_dataset.py`: **15/15 kết quả rule đúng kỳ vọng** — 10 thoại được chấp nhận, 5 thoại cố ý vượt CPS bị chặn. Tỷ lệ chấp nhận 66,67% của fixture không phải điểm chất lượng dịch.
- Probe Python compile hợp lệ. Không gọi ASR/LLM/TTS thật, không tải model, không ghi database/project đang dùng.

## Thứ tự hoàn thiện đề nghị

1. Căn kết thúc TTS/sub theo một quy tắc và thêm QC timing từng câu (DS01).
2. Thống nhất preview/export cho câu overlap, bổ sung chỉnh start/end trên Studio (DS02–DS03).
3. Đánh giá bằng video có transcript, bản dịch và speaker đã được người duyệt xác nhận; đo đúng lời, nghĩa, phát âm và độ lệch từng câu. Sau đó kiểm tra video dài và tài nguyên 10h/50GB.
4. Thêm vocal/BGM separation nếu cần giữ nhạc/hiệu ứng và bỏ lời gốc; voice cloning/lip-sync hoặc hạ tầng phân tán theo nhu cầu sản phẩm.
