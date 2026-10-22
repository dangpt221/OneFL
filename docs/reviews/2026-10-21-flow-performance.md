# Kiểm chứng luồng và tối ưu hiệu năng — 2026-10-21

Đã chạy lại các luồng lõi được triển khai, sửa bốn điểm gây lãng phí và đo trước/sau. **124 test backend và 22 kịch bản trình duyệt đạt**. Các con số dưới đây áp dụng cho workload cô lập đã mô tả; không suy ra tốc độ model thật hoặc khả năng xử lý 10 giờ/50 GB từ chúng.

## Những thay đổi đã thực hiện

1. **Worker nhận job tiếp theo ngay khi tác vụ hoàn thành.** Thay sleep cố định bằng chờ task với timeout heartbeat; tiếp tục lấy job kế tiếp ngay khi queue còn việc. Enqueue đánh thức worker cùng process, producer khác vẫn được phát hiện bằng DB polling. Giữ atomic admission, lease, OS worker lock, cancellation và recovery. [Worker](/D:/OneFl/backend/app/services/job_service.py).
2. **Cache metadata media có giới hạn.** Tối đa 512 fingerprint mỗi event loop; fingerprint gồm đường dẫn resolve, size, mtime/ctime ns và inode. File đổi phải probe lại, dữ liệu hỏng/lỗi không được coi là hợp lệ. Yêu cầu audio/video vẫn được kiểm tra riêng. Các probe cùng file đang chờ được gom bằng lock; không hash/đọc toàn bộ video vào RAM. [Media process](/D:/OneFl/backend/app/services/media_process.py).
3. **TTS dùng worker pool có giới hạn.** Không tạo một asyncio Task cho mỗi cue nữa; số task theo số worker, mặc định 8. Giữ thứ tự clip, timing, cache synthesis, lỗi provider, cancellation và PCM mixing. `TTS_MAX_CONCURRENCY` có thể cấu hình 1–32; không tăng mặc định hoặc thay model/giọng để làm đẹp số đo. [TTS](/D:/OneFl/backend/app/services/tts_service.py).
4. **Studio gom các đợt refresh trùng nhau.** Một cửa sổ 75 ms gom mount/socket/status events; khi dữ liệu đổi trong lúc fetch, vẫn có lần tải bù. Invalidate response cũ ngay lúc có yêu cầu mới; cleanup hủy timer khi đổi project/unmount. Không bỏ cơ chế reconnect/offline polling. [Coordinator](/D:/OneFl/frontend/src/lib/refreshCoordinator.ts), [Studio](/D:/OneFl/frontend/src/app/projects/[id]/page.tsx).

Không chạy song song các batch dịch phụ thuộc ngữ cảnh. Không tự đổi Whisper model, beam size, độ chính xác QC, encoder hoặc mức concurrency GPU. Không thêm dependency runtime/dịch vụ ngoài.

## Số đo trước và sau

| Hạng mục | Trước | Sau | Phạm vi diễn giải |
|---|---:|---:|---|
| Khoảng chờ giữa hai job đã hoàn tất, median | 4.996,67 ms | 2,49 ms | Overhead điều phối, không phải thời gian ASR/LLM/render |
| Tổng thời gian 3 job mô phỏng, median | 10.097,25 ms | 108,31 ms | Mỗi job có 25 ms synthetic work; hai lượt đo |
| Số tiến trình FFmpeg khi probe cùng file 10 lần | 10 | 1 | Lần đầu vẫn probe thật; chín lần sau dùng fingerprint cache |
| Probe warm median | 38,29 ms | 0,20 ms | WAV thật 1 giây; không thay kiểm tra stream/file đổi |
| Task TTS được tạo cho 200 cue | 200 | 8 | Đo cấu trúc task với provider/media boundaries mock; không phải benchmark chất lượng/tốc độ giọng |
| GET dữ liệu project lúc mở Studio 1.000 cue | 12 | 4 | Project + subtitles + speakers + glossary; mỗi nhóm còn một lần |
| Response body của nhóm GET trên | 1.430.586 bytes | 476.862 bytes | Giảm 66,7%; đo body đã giải mã, không phải dung lượng truyền có compression |
| Thời gian đến khi điều khiển sửa cue đầu tiên hiện, median | 487,32 ms | 507,35 ms | Ba lượt local; **chưa cho thấy cải thiện latency rõ rệt**, không công bố Studio render nhanh hơn |

Workload backend: 3 job, 2 lượt, synthetic work 25 ms/job, poll 20 ms, lease 45 giây và heartbeat tối đa 5 giây. Khoảng chờ cũ gần 5 giây đến từ monitor ngủ sau khi job đã xong. Cả hai lượt dùng cùng tham số và máy; benchmark không gọi provider/model.

Workload browser: production build, Chromium headless desktop 1440 × 1000, 1.000 cue seed vào một project fixture trống, 3 page navigation; đọc thêm 1,2 giây để đếm đợt fetch trùng. Không có video/model đang xử lý trong bài đo này. Đo thời điểm locator chỉnh sửa hiện ra, không phải Lighthouse/LCP/INP hay RUM. Mẫu nhỏ và timing local không đủ cho kết luận thống kê về latency; lợi ích chắc chắn ở đây là số request/body và tránh xử lý lại dữ liệu.

Bằng chứng: [backend trước](/D:/OneFl/tmp/performance/before.json), [backend sau](/D:/OneFl/tmp/performance/after.json), [browser trước](/D:/OneFl/tmp/performance/browser-before.json), [browser sau](/D:/OneFl/tmp/performance/browser-after.json). Benchmark có thể tái chạy bằng [script backend](/D:/OneFl/scripts/benchmark_flow.py) và [script browser](/D:/OneFl/frontend/tests/performance.cjs).

## Luồng đã kiểm chứng lại

| Luồng | Bằng chứng và kết quả |
|---|---|
| Auth, ownership HTTP/WS/media | Backend regression; browser login/token sai/session; project khác user bị chặn |
| Tạo project, upload, queue/pipeline/review | Upload manifest/retry tests, browser upload thật, durable jobs và trạng thái review |
| URL ingestion | Validation/private-host tests, queue/cancel qua fixture URL provider; chưa tải mạng thật |
| Subtitle edit/retranslate/export | Save/409 giữ draft, selected retranslation, SRT/ASS/VTT; invalidation output cũ và hai tab tự cập nhật |
| Speaker/glossary | CRUD/import/CSV, remote conflict giữ draft, per-speaker speed và đồng bộ count |
| Dubbing | Config/preview cache/timing/provider failures; short real PCM/mux và browser preview/model/speed/matrix |
| Burn/rerender/player | FFmpeg CPU render/probe thật, output có phiên bản, duration đúng, chọn nguồn phát/audio đúng và play/pause/ended |
| Agent project/job | ASR → lưu cue → pipeline dịch → export ASS → burn → DB URL/Studio; pending/stale result không báo hoàn thành |
| Restart/cancel/delete | Worker lease/recovery/actor tests; cancel đợi native task; xóa project tab khác rời Studio |
| WebSocket/offline/mobile | Reconnect lấy dữ liệu mới, polling dự phòng, không có pageerror/requestfailed ngoài dự kiến; viewport desktop/mobile |

ASR/LLM/TTS/URL provider là fixture trong kiểm thử tích hợp; API/auth/SQL/job/WS/export/PCM/FFmpeg/player là code thực. Chất lượng nhận diện/dịch/giọng không được suy ra từ kết quả này.

## Kiểm thử cuối và điều chỉnh môi trường test

- **124 passed**, không fail/skip, một Starlette/AnyIO DeprecationWarning. [JUnit](/D:/OneFl/tmp/performance/pytest-results.xml).
- Bảy regression mới cho completion latency, local wakeup/cross-producer polling, probe reuse/invalidation/strict streams/concurrency/LRU/error, và giới hạn số task TTS. Các test ban đầu tái hiện lỗi trước sửa. Frontend có thêm test burst/trailing refresh/teardown/error.
- Full test phát hiện fixture API + background worker dùng SQLite `:memory:` chung một connection có thể làm transaction chồng nhau. Hai lifecycle integration test đã chuyển sang **SQLite file tạm riêng**, có FK/busy timeout và storage cô lập, để kiểm tra đúng mô hình nhiều connection của runtime. Unit tests vẫn dùng SQLite memory khi phù hợp. Không đổi DSN của ứng dụng hoặc né một lỗi DB thật bằng fallback.
- Frontend regression, TypeScript và production build exit 0. Lượt browser production cuối **22/22 đạt**, zero pageerrors/unexpected requestfailed. [Browser JSON](/D:/OneFl/tmp/feature-audit/browser-results.json), [trace](/D:/OneFl/tmp/feature-audit/browser-trace.zip). Snapshot/ảnh nằm trong cùng thư mục tmp.
- Log cuối chỉ có `Fixture provider unavailable` do fault injection có chủ đích; không có pool-reset hoặc queue-poll error. Node util._extend/Next standalone notice và cảnh báo dependency test không được ghi là đã xử lý. Ruff không có trong môi trường.
- Không chạy migration vào DB đang dùng, không thay `.env`, không gọi AI trả phí, không commit/push. `.env.example` có thêm `TTS_MAX_CONCURRENCY=8`; phiên bản này không thêm schema DB mới ngoài các thay đổi metadata ở lượt trước.
- Đã dừng các helper fixture do lượt kiểm thử tạo; kiểm tra không còn listener tại 8000/8100/3100. Build production cuối giữ backend URL thông thường 127.0.0.1:8000.

## Cách tái chạy

```powershell
backend/.venv/Scripts/python.exe scripts/benchmark_flow.py --label after
$env:DATABASE_URL='sqlite+aiosqlite:///:memory:'
backend/.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp=tmp/performance-check
npm.cmd --prefix frontend test
frontend/node_modules/.bin/tsc.cmd --project frontend/tsconfig.json --noEmit --incremental false
```

Sau khi khởi động fixture/backend và frontend production như README, chạy `node frontend/tests/performance.cjs after` với NODE_PATH/ONEFL_E2E/ONEFL_FIXTURE_URL tương ứng. Script chỉ gọi fixture seeding đã giới hạn 1–10.000 cue; không dùng endpoint này ở production. Giữ JSON before khi so sánh; chạy nhãn after trên code mới không tái tạo baseline cũ.

## Phần chưa thể xác nhận

Chưa benchmark ASR/LLM/TTS provider thật, NVENC/GPU residency, media 10 giờ/50 GB, A/V drift dài hạn, tải nhiều người dùng, PostgreSQL/Docker/HTTPS hoặc môi trường phân tán. Đây là phần còn thiếu bằng chứng để kết luận toàn hệ thống đạt mọi mục tiêu production. Pipeline hỗ trợ hiện tại vẫn là một máy, persistent local storage và durable DB queue.

Các luồng đã kiểm thử hoạt động sau tối ưu và các điểm nghẽn đo được đã được giảm. Không có cơ sở để tuyên bố mọi tính năng đã được tối ưu tuyệt đối hoặc tốc độ video thực tăng bằng tỷ lệ của microbenchmark.
