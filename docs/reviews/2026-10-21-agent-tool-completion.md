# Kết quả hoàn thiện Agent tools và skills — 2026-10-21

Đã sửa các phát hiện AT01–AT08 của [lượt review](2026-10-21-agent-tool-review.md), bổ sung sáu tool project/job và hai skill local. Toolkit hiện có **16 tool**. Media work dùng durable queue hiện có; không thêm hệ điều phối hay dịch vụ ngoài. Các thay đổi nằm trong working tree, chưa commit/push và chưa chạy migration vào database đang sử dụng.

## Đối chiếu sửa lỗi

| Phát hiện | Thay đổi và kiểm chứng |
|---|---|
| AT01 — bỏ qua job/project | ASR/burn submit AGENT_TOOL vào cùng atomic admission, DB lease và worker lock. Worker lấy user context từ project; lưu Job.result và project artifact/revision. Test duplicate 409, cross-user 404, owner context, cancellation và recovery. Lightweight preview/analysis vẫn là request có giới hạn |
| AT02 — thiếu handoff | ASR tự tách audio từ source; đường dẫn audio được lưu trong payload để dùng lại sau restart. Project export tạo file ASS/SRT/VTT và URL, cập nhật subtitle path; burn lấy ASS đó và công bố output versioned vào project. Integration chạy extraction/burn/probe bằng FFmpeg thật |
| AT03 — mất speaker/text | Cùng normalize_cues xử lý alias cue_index/id, speaker_tag/speaker, original_text/text và timing. Profiler adapter nhận ID/nội dung đúng; test A/B/A kiểm tra prompt không rỗng |
| AT04 — Runner 500 | AgentDecision validate cấu trúc trước dispatch. JSON list/null, thought/action_input sai kiểu được ghi thành lỗi reflection có giới hạn; HTTP không còn 500 cho trường hợp này |
| AT05 — relationship list | Schema tool chấp nhận list hoặc wrapper dict, không chặn output của relationship tool trước khi vào service |
| AT06 — QC passed sai | Chỉ đưa cue không có vi phạm vào passed_translations/total_passed; giữ total_translations và rejected_ids riêng. Kết quả QC không đạt có success=false |
| AT07 — preset không tác dụng | Bỏ preset khỏi input burn ASS, extra fields bị từ chối. Preset áp dụng khi export ASS. HTTP/Studio burn giữ cấu hình riêng hiện có |
| AT08 — success sai nghĩa | Missing-media raise lỗi; wrapper/API tôn trọng outcome. Runner phân biệt PENDING/FAILED/COMPLETED, không tin final_answer khi lỗi tool chưa được xử lý hoặc job chưa xong; artifact mục tiêu phải còn tham chiếu/file hiện hành. Test stale output bị từ chối |

Có thêm kiểm tra stream/duration thật cho inspect, model/speed cho preview, bilingual SRT/VTT, giới hạn input và history, cue context phân trang, output schema cho tool/job. ASR-only có tracker riêng trong Studio để không hiển thị như đã hoàn tất dịch thuật.

## Công cụ và skill bổ sung

- get_project_context: đọc project và cue phân trang.
- start_project_pipeline: xếp pipeline qua cùng admission của HTTP.
- dub_project_video: lưu cấu hình và xếp timed dubbing/mux.
- get_job_status: đọc outcome/result và tính hiện hành của artifact.
- wait_for_job: chờ có giới hạn, không báo hoàn thành giả.
- cancel_project_job: yêu cầu hủy và chờ acknowledgement.

Skill [onefl-agent-tools](/D:/OneFl/.agents/skills/onefl-agent-tools/SKILL.md) và [onefl-media-verification](/D:/OneFl/.agents/skills/onefl-media-verification/SKILL.md) đã được tạo trong repository và qua `skill-creator/quick_validate.py`. Không cài framework/provider hoặc package runtime mới. [Hướng dẫn/API contract](/D:/OneFl/docs/agent-tools.md) mô tả đủ 16 tool, cách ghép chuỗi và thay đổi cho client cũ.

## Bằng chứng

- Test trước sửa: **11 regression thất bại** ở các hợp đồng đã nêu; sau sửa có **20 test Agent completion đạt**, gồm media thật, actor/ownership, cancellation/recovery, migration, pending/stale completion, HTTP error handling và session cleanup.
- Lượt full suite cuối: **117 passed**, không fail/skip; một Starlette/AnyIO DeprecationWarning. [JUnit](/D:/OneFl/tmp/agent-completion/pytest-results.xml).
- Frontend: regression gồm 5 modal, CSV/timeline/playback/workflow và ASR-only tracker; TypeScript và production build exit 0. **84 file Python app/test** compile trong memory; `git diff --check` đạt. Ruff không có trong môi trường nên không ghi nhận đã chạy Ruff.
- Integration tạo video 3 giây, tách WAV thật, dùng ASR/LLM fixtures, lưu transcript, dịch qua service/QC, xuất ASS có preset/bilingual, burn/probe duration và kiểm tra DB URL/result. Runner cũng submit burn, đọc terminal job và chỉ chốt sau xác minh artifact. Không dùng mock renderer trong kịch bản này.
- Browser dùng production build và fixture API: giữ các kịch bản UI đã có, bổ sung Agent ASR-only và Agent pipeline/export/burn để kiểm tra Studio nhận output từ tool. Kết quả và ảnh nằm ở [browser JSON](/D:/OneFl/tmp/feature-audit/browser-results.json), [trace](/D:/OneFl/tmp/feature-audit/browser-trace.zip), [ASR Studio](/D:/OneFl/tmp/feature-audit/agent-asr.png), [Agent output Studio](/D:/OneFl/tmp/feature-audit/agent-studio-completed.png). Số lượng/kết quả lượt browser cuối được ghi trong execution record bên dưới sau khi chạy xong.

Script audit cũ trong docs/reviews cố tình assert hành vi lỗi trước sửa, nay không phải acceptance. Không dùng việc script đó thất bại sau sửa để kết luận sản phẩm bị hồi quy. Các báo cáo trước giữ số liệu lịch sử; artifact tmp có thể được thay bằng lượt chạy mới nhất.

## Giới hạn vận hành

Các job/fixture dùng SQLite và storage riêng; không sửa project thật, không gọi AI trả phí hoặc tải model. Chưa đánh giá ngữ nghĩa dịch, speaker identity hay giọng thật; chưa đo video 10 giờ/50 GB, RAM/VRAM/A-V drift, NVENC, PostgreSQL/Docker/HTTPS production hoặc thiết bị/browser khác. Runner vẫn chọn tool bằng JSON trong prompt, không có bằng chứng live native SDK function calling. Triển khai vẫn là single-host local storage.

Client cũ cần đổi ASR/burn sang theo dõi job_id và chọn preset tại export. Có migration metadata mới; sao lưu database/media trước lần khởi động bản nâng cấp. Giữ giới hạn provider/load trên khi đánh giá mức sẵn sàng sản xuất.

## Execution record cuối

- Đủ **22/22 browser scenario đạt** sau bản sửa cuối, trên production frontend và API fixture qua proxy cùng origin; zero JavaScript pageerror/unexpected requestfailed. Hai scenario Agent xác nhận cả ASR-only và pipeline/export/burn đồng bộ vào Studio.
- Log review phát hiện thêm cancellation có thể cắt ngang việc trả connection DB về pool khi socket đóng. Regression đã fail trước sửa; session close/rollback nay chạy trong cleanup task được shield và được chờ xong trước khi truyền cancellation. Full suite và 22 browser scenario được chạy lại sau sửa; không còn `Exception during reset` hoặc `Durable queue poll failed` trong log lượt cuối. Lỗi `Fixture provider unavailable` duy nhất là fault injection có chủ đích.
- Frontend server test có thông báo Next khuyến nghị standalone entry point và Node util._extend deprecation. Không dùng kiểm thử này làm bằng chứng đóng gói container/standalone deployment.
- Đã dừng các server fixture do lượt kiểm thử tạo; kiểm tra lại không còn listener ở 8000/8100/3100. Build cuối trỏ backend mặc định 127.0.0.1:8000.
