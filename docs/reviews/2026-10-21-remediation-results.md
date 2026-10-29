# Kết quả sửa lỗi OneFL — 2026-10-21

**Cập nhật sau remediation:** đã rà soát thêm tính năng, giao diện desktop/mobile và đồng bộ giữa tab; xem [báo cáo kiểm chứng UI/backend](2026-10-21-feature-ui-backend-verification.md) để đọc các lỗi bổ sung đã sửa, 97 test backend và 20 kịch bản browser. Số liệu 92 test và các giới hạn browser trong phần dưới là kết quả tại thời điểm kết thúc lượt remediation trước đó.

Đã sửa các lỗi mã nguồn F01–F28 của [báo cáo audit](2026-10-21-backend-flow-audit.md), bổ sung kiểm thử hồi quy và hướng dẫn vận hành. Phạm vi triển khai hiện tại là một máy có storage bền vững; các giới hạn kiểm chứng bên dưới vẫn áp dụng. Giữ nguyên các chỉnh sửa có sẵn của người dùng, không commit/push, không chạy migration vào database đang sử dụng và không gọi API AI trả phí trong kiểm thử.

## Đối chiếu phát hiện

| Lỗi | Thay đổi thực tế | Bằng chứng kiểm tra |
|---|---|---|
| F01 | Import settings và hoàn thiện luồng burn từ video gốc | [Media integration](/D:/OneFl/tests/test_media_integration.py): tạo source, burn ba chunk, probe kết quả |
| F02 | Worker render chỉ xử lý file; coordinator cập nhật DB tuần tự | [Workflow](/D:/OneFl/backend/app/services/workflow_engine.py), kiểm thử render nhiều chunk đồng thời |
| F03 | ASR lỗi phải raise, không tạo thoại mẫu hoặc nhãn speaker luân phiên | [Reliability](/D:/OneFl/tests/test_reliability.py), [ASR](/D:/OneFl/backend/app/services/asr_service.py) |
| F04 | Provider dịch lỗi làm job FAILED, không dùng source làm bản dịch thành công | Reliability: provider outage; [runtime](/D:/OneFl/tests/test_runtime_integration.py): job thất bại còn hiển thị |
| F05 | Wrap giữ toàn bộ từ; quá dòng/CPS phải sửa hoặc bị chặn | Reliability, [guardrails](/D:/OneFl/tests/test_guardrails.py), fixture tests |
| F06 | Duration lấy từ media; không thay bằng thời điểm hết câu thoại | Reliability và video thật 3 giây có cue kết thúc ở 0,7 giây |
| F07 | Decode clip ra disk, overlap-add trong block PCM cố định, encode ngoài event loop | [PCM/audio tests](/D:/OneFl/tests/test_audio_timeline.py), media integration; không còn cấp array audio toàn video |
| F08 | Upload ID/manifest/checksum, kiểm tra offset và completeness, finalize riêng; upload cũ cũng kiểm tra media và xóa tham chiếu cũ | [Upload tests](/D:/OneFl/tests/test_jobs_upload.py), [hardening](/D:/OneFl/tests/test_final_hardening.py) |
| F09 | FFmpeg/render/mux/concat lỗi phải raise; probe stream/duration trước công bố | Reliability và media integration, không copy source để báo burn thành công |
| F10 | Job bền vững, atomic claim/project, queue cap, lease/OS lock, cancel chờ tài nguyên dừng, phục hồi cấu hình sau restart | [Worker tests](/D:/OneFl/tests/test_job_worker.py), upload/job tests và hardening |
| F11 | Token/session HttpOnly, project ownership cho HTTP/WS/media, origin check, quota request/job/upload; mặc định loopback | [Security tests](/D:/OneFl/tests/test_security.py), runtime hai user, [security implementation](/D:/OneFl/backend/app/security.py) |
| F12 | Đồng bộ dependencies, root container, persistent paths, proxy DNS khi build, dockerignore/public, local storage rõ ràng | Manifest/YAML parse và Next build qua. **Chưa chạy Docker image/Compose** vì Docker CLI không có trong môi trường |
| F13 | Di chuyển hooks ra trước early return trong hai modal | [React rerender regression](/D:/OneFl/frontend/tests/regressions.cjs), TypeScript/build |
| F14 | Poll theo boolean trạng thái đang chạy, không phụ thuộc array response; gom query counts phía backend | React regression và [dashboard](/D:/OneFl/frontend/src/app/page.tsx) |
| F15 | Thu hẹp ignore để source TS/lib và fixture nhỏ được version-control; thêm backend README để package metadata hợp lệ | `git check-ignore`, source/fixture tồn tại, manifests matched, TypeScript/build. File mới còn ở working tree, chưa tạo commit |
| F16 | Import func và không nuốt lỗi auto-extract; lấy sample đầu/giữa/cuối | [API regressions](/D:/OneFl/tests/test_api_regressions.py) |
| F17 | Chuẩn hóa list/dict relationship và glossary; dùng target đã xác định hoặc suy ra khi chỉ có một cặp; hỗ trợ case/word boundaries | Reliability, hardening, [guardrails implementation](/D:/OneFl/backend/app/services/guardrails.py) |
| F18 | Merge repair theo ID kể cả JSON đầu hỏng/thiếu ID; kiểm tra lại toàn batch và fail nếu hết retry | Reliability: invalid JSON, missing ID, unresolved QC, callback failure |
| F19 | Phân biệt resume/force; giữ chỉnh tay, kiểm tra lại bản dịch lưu, truyền model/temperature/path và lưu cảnh báo QC | Reliability, hardening, API retranslation test |
| F20 | Chỉ dùng một DSN; introspect/version migrations, transaction lock, FK, unique cue index và timing constraints/triggers | [Migration test](/D:/OneFl/tests/test_migrations.py): upgrade schema cũ, giữ row và chạy lại; hardening unique-index test |
| F21 | Copy JSON settings; cập nhật settings cùng atomic job admission, request bị 409 không sửa job đang chạy | Hardening: rejected burn giữ nguyên settings; pipeline route |
| F22 | Callback download có await kết quả và throttle; cancellation signal cho download thread; không lấy nhầm file cũ; auto_start=false về CREATED | [Downloader](/D:/OneFl/backend/app/services/video_downloader.py), [ingestion](/D:/OneFl/backend/app/services/ingestion_service.py); chưa tải mạng thật |
| F23 | Agent gọi dịch/TTS/burn thật, trả đủ cues/translation/export/artifact; kiểm tra quyền filesystem; relationship tool suy luận qua provider thay vì matrix giả | API regressions mock provider, [Agent tools](/D:/OneFl/backend/app/agent/tools.py) |
| F24 | Cache synthesis chứa model/voice/text/speed; cache adjustment chứa timing; tempo có giới hạn, đo lại và fail nếu không thể fit | Audio timeline tests và media integration |
| F25 | TTS không đổi voice/provider hoặc tạo silence khi lỗi; cue failure làm job fail; commit errors không bị nuốt; dùng per-speaker speed và saved config | Audio timeline/provider tests, worker config recovery, [TTS route](/D:/OneFl/backend/app/api/v1/tts.py) |
| F26 | Chuẩn hóa sự kiện lỗi, DB snapshot khi reconnect/xuyên API process, send timeout/quota, socket teardown đúng; proxy cùng origin | Runtime/auth tests, frontend regressions/build; chưa chạy browser/network E2E |
| F27 | Reset đọc JSON schema, cancel trước đổi status; resume dùng toàn bộ cấu hình dubbing gốc | Job/worker tests, [projects route](/D:/OneFl/backend/app/api/v1/projects.py) |
| F28 | Create/update/delete sync export và WS; finite timing/end>start, null policy, cue index unique; conflict trả 409 | API regressions, hardening, subtitle schema tests |

## Rủi ro bổ sung đã xử lý

- Render seek/reencode chính xác từ source thay stream-copy theo keyframe; checkpoint theo fingerprint source/cues/settings, đòi đủ chunk và kiểm tra duration cuối. Các mode mask 0%, blur crop nhỏ và cinema zoom đã được chạy bằng FFmpeg thật.
- Invalidate audio/burn khi thay nguồn/subtitle/cấu hình; tạo output theo phiên bản. Delete dừng job rồi xóa media trong thư mục project. Retention giữ artifact hiện còn tham chiếu và lock files, xóa cache/scratch/output không còn dùng sau thời hạn khi queue rảnh.
- ASR có model admission lock, cache từng chunk, VAD và điểm chia ưu tiên khoảng lặng. Force ASR yêu cầu tường minh và xóa hồ sơ speaker cũ khi thay transcript. Diarization tùy chọn dùng embedding registry qua chunk; mặc định CPU cho pyannote để không tự nạp thêm GPU model cùng Whisper.
- Speaker profiler lấy mẫu trải transcript, kiểm tra đủ speaker và quan hệ hợp lệ; lỗi provider không biến thành hồ sơ thành công. Vision tùy chọn lấy JPEG thật có giới hạn. Hai tích hợp này có contract/unit tests; chưa đo chất lượng model thực.
- Player xử lý cue chưa sắp xếp/chồng thời gian, CSV đọc quoted/multiline, UI hiện lỗi API và bỏ số ETA/cue giả. Settings trong Burn dialog quyết định xuất video; màu/mask player là preview.
- Key test dùng router riêng, API key không nằm trong URL; giới hạn concurrency LLM/burn dùng chung giữa các entry point trong một API process. Queue và OS lock giới hạn các job media chuẩn giữa process trên cùng máy. Không suy ra đây là scheduler GPU phân tán hoặc cách ly tài nguyên toàn cụm cho Agent tool trực tiếp.
- Script thủ công gọi API/job thay đường xử lý riêng hardcode project/DB. Mẫu môi trường và kiến trúc/spec ghi rõ local storage, DB queue và các tính năng còn là thiết kế đích.
- Glossary còn **290 mục deduplicate**, loại bỏ hậu tố số sinh để tăng số lượng. Dataset còn **15 thoại độc lập/30 cues**, phân bố EN 5, ZH 4, JA 3, KO 3. Có 10 reference hợp lệ và 5 reference phải bị chặn `CPS_TOO_HIGH`; cả **15/15 kết quả rule đúng kỳ vọng**. Đây không phải điểm semantic translation hay kết quả chạy 1.000 video.

## Kết quả kiểm chứng

Lệnh backend dùng `DATABASE_URL=sqlite+aiosqlite:///:memory:` trước khi import ứng dụng, output/temp nằm trong thư mục verification. Các provider trong test được mock, media smoke dùng video/tone tổng hợp vài giây.

| Kiểm tra | Kết quả |
|---|---|
| `pytest tests -q -p no:cacheprovider --basetemp=tmp/fixes/acceptance-complete --junitxml=tmp/fixes/acceptance-results.xml` | **92 passed, 0 failed, 0 skipped**, 1 cảnh báo deprecation, 11,67 giây; [JUnit output](/D:/OneFl/tmp/fixes/acceptance-results.xml) |
| `npm test` | 2 component rerenders, CSV quoted/multiline, overlapping/unsorted timeline: pass |
| `npx tsc --noEmit --incremental false` | Exit 0 |
| `npm run build` | Exit 0; compile, lint/type checking, static generation và traces hoàn tất |
| Compile Python trong memory | 82 tệp hợp lệ |
| Requirements so với pyproject | Trùng bộ runtime dependencies |
| Parse Compose và CI YAML | Pass |
| Fixture rule evaluation | 15/15 kết quả đúng kỳ vọng; 10/15 reference chấp nhận, 5/15 bị chặn CPS |
| `git diff --check` | Không lỗi whitespace; có cảnh báo chuyển CRLF → LF của Git trên Windows |

Còn một cảnh báo deprecation từ Starlette TestClient/AnyIO trong môi trường test hiện có. Ruff không có trong môi trường; không tuyên bố đã chạy Python lint bằng Ruff. Đã thêm [CI verification](/D:/OneFl/.github/workflows/verify.yml) để kiểm tra dependencies/test/build ở checkout sạch, nhưng chưa kích hoạt workflow trên GitHub.

## Thay đổi cấu hình và giới hạn

`.env` đang dùng đã đổi **riêng `STORAGE_DRIVER=s3` sang `local`**, đúng storage thực sự được triển khai; không sửa credentials/DSN hiện có. File này không đưa vào Git. Production yêu cầu token dài ít nhất 24 ký tự và HTTPS để browser gửi Secure session cookie. Với nhiều API process phải dùng chung DB và cùng đường dẫn local media/scratch trên một host.

Chưa kiểm chứng Docker build/Compose, migration trên PostgreSQL thật, URL download thật, provider AI/TTS thật, GPU NVENC/Whisper/pyannote, browser E2E sau reverse proxy, VFR/A-V drift dài hạn hoặc video 10 giờ/50 GB. Chưa đo chất lượng semantic/speaker identity trên media đại diện. Cần chạy các phép đo đó trên môi trường triển khai trước khi kết luận đạt production hoặc đúng toàn bộ yêu cầu quy mô; các test nhỏ hiện tại không thay thế được chúng.

S3/R2, Temporal, Redis Pub/Sub và cụm GPU nhiều máy chưa được triển khai. Startup từ chối storage chưa hỗ trợ thay vì báo thành công giả. Xem [hướng dẫn vận hành](/D:/OneFl/README.md).

Tài liệu provider đối chiếu cho các adapter: [Gemini models](https://ai.google.dev/gemini-api/docs/models), [Gemini thinking](https://ai.google.dev/gemini-api/docs/thinking), [OpenAI image inputs](https://developers.openai.com/api/docs/guides/images-vision), [pyannote community model](https://huggingface.co/pyannote/speaker-diarization-community-1). Không dùng các tài liệu này làm bằng chứng ứng dụng đã gọi provider thật.
