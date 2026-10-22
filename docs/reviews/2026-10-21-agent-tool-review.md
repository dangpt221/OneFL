# Đánh giá Agent Toolkit — 2026-10-21

**Cập nhật:** các phát hiện bên dưới đã được xử lý ở [lượt hoàn thiện Agent tool](2026-10-21-agent-tool-completion.md). Đây là ghi nhận hiện trạng trước sửa; đọc báo cáo mới để xem 16 tool, skill bổ sung và bằng chứng kiểm thử sau sửa.

**Kết luận: bộ 10 tool đã có registry/API và một số thao tác riêng lẻ hoạt động, nhưng chưa đạt để giao Agent tự động xử lý trọn một project video và bảo đảm đồng bộ với Studio.** Các điểm cần xử lý nằm ở hợp đồng dữ liệu giữa tool, quản lý job/artifact và phản hồi lỗi của Runner. Kết quả 97 test backend và 20 luồng UI trong báo cáo trước không đồng nghĩa chuỗi Agent đã được kiểm chứng đầy đủ.

Phạm vi của lượt này là Agent Toolkit tại [tools](/D:/OneFl/backend/app/agent/tools.py:24), [Runner](/D:/OneFl/backend/app/agent/agent_runner.py:107) và [API](/D:/OneFl/backend/app/api/v1/agent.py:20). Đây là review; không sửa mã nguồn ứng dụng, không thay dữ liệu đang dùng, không gọi AI trả phí hoặc khởi chạy inference/render thật. Các phát hiện dưới đây còn mở.

## Phát hiện ưu tiên

### AT01 — P1: tool nặng chạy ngoài vòng đời job/project

[Execute](/D:/OneFl/backend/app/agent/tools.py:131) kiểm tra schema/quyền đường dẫn rồi gọi trực tiếp handler. [Burn handler](/D:/OneFl/backend/app/agent/tools.py:386) gọi renderer mà không qua atomic admission, durable job, cancellation hoặc cập nhật artifact/revision của project.

**Tái hiện:** tạo project cô lập có `active_job_id='existing-job'`, gọi burn với các đường dẫn thuộc đúng chủ sở hữu. Renderer mock vẫn được gọi, tool trả COMPLETED, trong khi project vẫn giữ job cũ và `burned_video_url=None`. Do đó UI không thể dựa vào snapshot DB để biết output Agent vừa tạo. Đường gọi trực tiếp cũng không có khả năng phục hồi job sau restart như luồng Studio.

ASR có inference lock và burn có semaphore dùng chung **trong một process/event loop**; không kết luận rằng hoàn toàn không có giới hạn tài nguyên. Tuy nhiên các khóa đó không thay thế DB lease/OS worker lock của durable queue giữa process. Đây là khoảng trống đã được lưu ý ở lượt remediation, hiện vẫn tồn tại cho entry point Agent.

**Hướng sửa:** với thao tác trên project, bind project ID và quyền truy cập, submit vào dịch vụ job hiện có, trả job ID, cập nhật artifact/revision qua cùng transaction và cung cấp trạng thái để Agent chờ. Nếu giữ chế độ standalone, cần công bố rõ output độc lập với Studio và có cơ chế admission/cancel phù hợp.

### AT02 — P1: chưa nối được chuỗi video → ASR → export → burn

[Tool transcribe](/D:/OneFl/backend/app/agent/tools.py:183) chỉ nhận `audio_path`, không gọi dịch vụ tách audio. Bộ 10 tool không có thao tác tách audio độc lập. Vì vậy tên `extract_and_transcribe_audio` không thực hiện bước extract trong chuỗi tool hiện tại.

[Export](/D:/OneFl/backend/app/agent/tools.py:349) trả nội dung ASS/SRT/VTT trong JSON, không tạo file hay trả `subtitle_path`; [burn](/D:/OneFl/backend/app/agent/tools.py:72) lại bắt buộc đường dẫn file subtitle. Trong bộ tool cũng không có thao tác ghi artifact từ nội dung export. Agent không thể tự vượt qua hai chỗ đứt này chỉ bằng các tool đang đăng ký.

**Tái hiện:** ASR trả đủ cue nhưng số lần gọi extract là 0; export tạo ASS có nội dung dịch đúng nhưng chỉ có `format/lines_count/content/content_preview`. Đây là thiếu khả năng ghép chuỗi, không phải khẳng định generator xuất sai nội dung.

**Hướng sửa:** để handler xử lý trích xuất và ghi subtitle dưới project được cấp quyền; trả artifact ID/path đã kiểm chứng, cho tool tiếp theo nhận cùng contract. Không cho LLM tự chọn đường dẫn ghi tùy ý.

### AT03 — P1: đưa output ASR vào profiler làm mất speaker và thoại

[ASR output](/D:/OneFl/backend/app/services/asr_service.py:150) dùng `speaker_tag`, `original_text`. [Analyze handler](/D:/OneFl/backend/app/agent/tools.py:201) chuyển nguyên danh sách sang profiler, trong khi [profiler](/D:/OneFl/backend/app/services/speaker_profiler.py:21) đọc `speaker`, `text`.

**Tái hiện:** transcript ba cue thuộc A/B/A với nội dung Hello/Goodbye/Again trở thành prompt ba dòng `SPEAKER_00:` rỗng; kết quả chỉ còn hồ sơ SPEAKER_00. Mock chỉ thay phản hồi LLM; phần dựng prompt và xử lý speaker là code thật.

**Hướng sửa:** chuẩn hóa một model cue dùng chung tại biên tool; test ASR → profiler với tối thiểu hai speaker và kiểm tra cả ID lẫn nội dung prompt.

### AT04 — P1: JSON hợp lệ nhưng sai cấu trúc làm Runner lỗi 500

[Runner](/D:/OneFl/backend/app/agent/agent_runner.py:164) chỉ kiểm tra parse JSON, sau đó gọi `.get` và dựng `AgentStep` mà chưa validate cấu trúc quyết định.

**Tái hiện:** response `[]` gây AttributeError và HTTP `/agent/chat` trả **500**. Response có `action_input: []` gây lỗi schema tool; lúc ghi lại bước lỗi, `AgentStep` tiếp tục gây ValidationError vì field yêu cầu dict. Hai trường hợp không đi qua reflection như lỗi JSON syntax.

**Hướng sửa:** model Pydantic cho hai loại quyết định action/final, kiểm tra thought/action_input/final_answer trước dispatch, đưa lỗi cấu trúc vào vòng retry hữu hạn; chỉ lưu các giá trị đã chuẩn hóa vào trajectory.

### AT05 — P2: output relationship không khớp input translation/guardrails

[Relationship handler](/D:/OneFl/backend/app/agent/tools.py:230) và profiler trả `relationships` dạng list; [translation input](/D:/OneFl/backend/app/agent/tools.py:45) và [guardrail input](/D:/OneFl/backend/app/agent/tools.py:52) khai báo `relationship_matrix` chỉ là dict.

**Tái hiện:** truyền `build_relationship_matrix.result.relationships` sang translation gây Pydantic ValidationError trước khi gọi provider. Service bên dưới đã có hỗ trợ chuẩn hóa list/dict; schema tool đang chặn dạng dữ liệu đó.

**Hướng sửa:** dùng cùng model relationship có kiểu rõ ràng hoặc chuẩn hóa một wrapper nhất quán; kiểm thử ghép tool bằng output thực của bước trước.

### AT06 — P2: guardrails gắn nhãn “passed” cho câu không đạt

[Guardrail handler](/D:/OneFl/backend/app/agent/tools.py:270) lấy tổng số translation parse được làm `total_passed` và đưa tất cả vào `passed_translations`, kể cả câu có vi phạm.

**Tái hiện:** một câu đạt 160 CPS, `is_valid=false`, có CPS_TOO_HIGH, nhưng `total_passed=1` và câu đó vẫn nằm trong `passed_translations`. Validator cốt lõi đã phát hiện đúng; adapter tool trả các trường mâu thuẫn.

**Hướng sửa:** phân biệt parsed/accepted/rejected; chỉ tính passed trên cue không có lỗi chặn, hoặc đổi tên trường nếu nó chỉ biểu thị parse thành công. Giữ vi phạm gắn đúng cue ID.

### AT07 — P2: preset burn được trả lại nhưng không được áp dụng

[Burn handler](/D:/OneFl/backend/app/agent/tools.py:390) đọc preset rồi chỉ đưa nó vào JSON kết quả. Lời gọi renderer ở dòng 397 không dùng preset và không tạo lại ASS theo preset. Style thực tế do file ASS đầu vào quyết định.

**Tái hiện:** chọn cinema rồi yellow_highlight tạo hai lời gọi renderer giống hệt nhau, nhưng JSON báo hai preset khác nhau. Không thể coi lựa chọn preset trong tool này là đã có hiệu lực.

**Hướng sửa:** áp preset ở bước tạo ASS và xác định artifact tương ứng, hoặc bỏ tham số preset khỏi burn nếu hợp đồng là burn nguyên file ASS đã tạo. Không trả một cấu hình như thể đã áp dụng khi renderer không sử dụng nó.

### AT08 — P2: cờ success chưa phản ánh kết quả thao tác

[Safe wrapper](/D:/OneFl/backend/app/agent/tools.py:143) và [HTTP execute](/D:/OneFl/backend/app/api/v1/agent.py:51) trả success khi handler không raise. Inspect file không tồn tại lại trả dict `status=ERROR`, nên API trả HTTP 200, `success=true`, bên trong `status=ERROR`.

[Runner](/D:/OneFl/backend/app/agent/agent_runner.py:182) cũng đánh dấu success khi nhận bất kỳ final_answer khác rỗng. Probe cho một tool không tồn tại rồi LLM nói “Finished successfully”: kết quả toàn lượt vẫn success=true, không có artifact. Điều này chứng minh success hiện chỉ phản ánh quyết định kết thúc của model, chưa xác nhận mục tiêu video đã đạt. Một lượt phục hồi thành công sau lỗi vẫn có thể hợp lệ; không nên đơn giản coi mọi lỗi trong history là thất bại toàn lượt.

**Hướng sửa:** chuẩn hóa outcome và mã lỗi của tool; khi mục tiêu yêu cầu artifact, xác nhận artifact/job/DB trước công bố thành công, đồng thời tách “đã trả lời” khỏi “đã hoàn thành xử lý”.

## Ma trận 10 tool

| Tool | Đã xác nhận | Giới hạn/điểm chưa đạt |
|---|---|---|
| inspect_video_media | Kiểm tra tồn tại, dung lượng, extension; chặn đường dẫn file ngoài project được cấp quyền | Chỉ stat file; file giả có đuôi mp4 vẫn OK, không có duration/resolution/audio metadata; wrapper lỗi AT08 |
| extract_and_transcribe_audio | Gọi đúng service ASR, trả toàn bộ cue qua biên provider mock | Không extract audio; không có job durable; output chưa khớp profiler, AT01–03 |
| analyze_speaker_profiles | Gọi profiler và validate output qua service hiện có | ASR → profiler mất dữ liệu, AT03; chưa đánh giá suy luận model thật |
| build_relationship_matrix | Kiểm tra speaker pair không tự trỏ/không trùng/không bịa ID | Output list không khớp input tool kế tiếp, AT05; ngữ nghĩa quan hệ chưa được đánh giá |
| translate_subtitle_chunk | Một batch qua prompt/router/QC thật với response provider mock, trả bản dịch | AT05; cue vẫn là dict tự do; khi bật global visual context, tool không nhận video_path để cung cấp cho service |
| run_subtitle_guardrails | Validator phát hiện lỗi CPS | Trường passed sai nghĩa, AT06 |
| query_master_glossary | Tra cứu latency, lọc ngôn ngữ và limit; test query qua HTTP đạt | Đọc JSON đồng bộ mỗi lần; không phải search engine semantic. Dữ liệu hiện có 290 thuật ngữ đã deduplicate |
| export_subtitles | Tạo ASS/SRT theo test hiện có; ASS nhận được bản dịch output translation | Không tạo artifact file, AT02; bilingual chỉ được áp dụng ở nhánh ASS, SRT/VTT không dùng flag này |
| generate_dubbing_audio | Truyền đúng text/voice/speed vào preview service | Chỉ sinh preview cho một đoạn; không phải timed project dubbing/mux/ducking; không có field chọn model trong schema tool dù preview service hỗ trợ |
| burn_video_subtitles | Gọi renderer với input đã được kiểm tra ownership | AT01/02/07; chưa có job ID/artifact DB/status Studio |

Ngoài tám phát hiện trên, input nhiều chỗ còn là `List[Dict[str, Any]]`/dict tự do, không có output model chung. Schema được xuất theo dạng function nhưng Runner đang chọn tool bằng JSON trong prompt, chưa có bằng chứng live native function calling với OpenAI/Gemini. Toàn bộ cue/export/observation được nối vào history, chưa có giới hạn kích thước context; đây là rủi ro cần đo trước trường hợp video dài.

Không tìm thấy lời gọi endpoint `/agent` trong frontend source hiện tại; Studio gọi các API workflow riêng. Có API toolkit không đồng nghĩa đã có giao diện điều khiển Agent hoặc toàn bộ thao tác Agent tự đồng bộ sang Studio.

## Kiểm chứng mới của lượt review

- Chạy lại **97 test backend: 97 passed, không fail/skip**, một DeprecationWarning Starlette/AnyIO. [JUnit](/D:/OneFl/tmp/agent-review/pytest-results.xml). Trong đó có 8 test cũ của [Agent](/D:/OneFl/tests/test_agent_tools.py:1); chúng chủ yếu kiểm tra registry/schema, query/QC/export và một Runner happy path.
- Chạy [probe cô lập](/D:/OneFl/docs/reviews/2026-10-21-agent-tool-probes.py:1), exit 0, tạo **18 quan sát**, gồm đường đúng, xác thực và tái hiện lỗi. [JSON kết quả](/D:/OneFl/tmp/agent-review/probe-results.json). **18 quan sát không phải 18 lỗi và không phải 18 acceptance test đã đạt.** Các assertion trong script ghi nhận hành vi lỗi hiện tại, phải đổi khi sửa lỗi.
- Gọi HTTP thật bằng TestClient nhưng không chạy lifespan/worker: discovery trả đủ 10 tool; bật token thì anonymous 401, đúng Bearer 200; missing-media trả success sai nghĩa; malformed JSON từ provider làm chat 500.
- Database SQLite in-memory, storage riêng dưới tmp/agent-review. Mock ASR/LLM/TTS/renderer tại biên; không render thật, không tải model, không gọi provider thật. Auth/schema/prompt/normalization/service translation/QC/export và HTTP adapter dùng code thật.

```powershell
$env:DATABASE_URL='sqlite+aiosqlite:///:memory:'
backend/.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp=tmp/agent-review-tests --junitxml=tmp/agent-review/pytest-results.xml
backend/.venv/Scripts/python.exe docs/reviews/2026-10-21-agent-tool-probes.py
git -c core.safecrlf=false diff --check
```

Không chạy lại frontend build vì lượt này không sửa source frontend/backend. Kết quả UI/build của lượt trước nằm ở [báo cáo tính năng](/D:/OneFl/docs/reviews/2026-10-21-feature-ui-backend-verification.md); không sử dụng nó thay cho kiểm tra Agent ở đây.

## Thứ tự xử lý đề xuất

1. Chuẩn hóa cue/relationship và quyết định Runner; bổ sung test ghép output → input và JSON sai cấu trúc, AT03–05.
2. Gắn tool nặng vào project/job/artifact hiện có, hoàn thiện extract/ghi export và trạng thái để Studio/Agent theo dõi, AT01–02.
3. Chuẩn hóa outcome/QC và bỏ hoặc áp đúng preset, AT06–08.
4. Sau khi các regression đạt, chạy một chuỗi Agent từ video mẫu đến output được DB/Studio nhận biết; sau đó mới đánh giá provider thật, chất lượng thoại/giọng và video dài 10 giờ/50 GB.

Các mục P1 là điều kiện trước khi coi Agent là luồng tự động cho project sản xuất. Tool tra thuật ngữ hoặc export nội dung riêng lẻ vẫn có giá trị trong phạm vi đã kiểm chứng; chưa thể gọi toàn bộ toolkit là ổn định end-to-end.
