# OneFL Agent tools

Toolkit hiện có **16 tool**, qua `GET /api/v1/agent/tools`, `POST /api/v1/agent/execute-tool` và `POST /api/v1/agent/chat`. Discovery trả input function schema và `output_schema`. API dùng cùng token/session của ứng dụng; tool tra cứu project/job còn kiểm tra quyền sở hữu trong service, kể cả khi gọi từ Runner.

## Danh mục

| Tool | Dữ liệu vào chính | Kết quả/hành vi |
|---|---|---|
| inspect_video_media | video_path thuộc project được cấp quyền | Kiểm tra stream video thật, duration_seconds, dung lượng và extension; không chỉ kiểm tra đuôi file |
| extract_and_transcribe_audio | project_id hoặc audio_path/video_path; force_reprocess | Xếp AGENT_TOOL job; tự tách audio khi cần, lưu transcript; trả QUEUED/job_id |
| analyze_speaker_profiles | cues, source_language | Phân tích mẫu tối đa 300 cue; chuẩn hóa speaker_tag/original_text sang dữ liệu profiler |
| build_relationship_matrix | speaker_profiles, dialogue_context | Danh sách relationships đã kiểm tra speaker pair |
| translate_subtitle_chunk | cues tối đa 60, source_lang/target_lang, relationships/glossary | Bản dịch qua QC; phân tích độc lập không ghi cue DB. Dùng project pipeline để dịch và lưu project |
| run_subtitle_guardrails | requested_cues, llm_raw_response | is_valid, accepted/rejected IDs và vi phạm; total_passed chỉ tính câu đạt |
| query_master_glossary | query, source_lang/category, limit 1–50 | Tra thuật ngữ từ dữ liệu local |
| export_subtitles | project_id **hoặc** cues; format/preset/bilingual | Project mode tạo file có phiên bản, trả subtitle_path/artifact_url; standalone mode trả nội dung |
| generate_dubbing_audio | text ≤1000 ký tự, voice/model/speed | Preview cho một đoạn; không phải lồng tiếng/mux project |
| burn_video_subtitles | project_id, subtitle_path/video_path tùy chọn, clean_chinese_mode | Xếp job burn ASS; path mặc định lấy từ project, output MP4 mới; trả QUEUED/job_id |
| **get_project_context** | project_id, offset, limit 1–100 | Status/revision/URLs và cue phân trang; không nhét toàn transcript vào prompt |
| **start_project_pipeline** | project_id, stage, force_reprocess | Gọi cùng pipeline admission như HTTP/Studio, lưu job bền vững |
| **dub_project_video** | project_id, voice/model/speed/ducking/matrix | Cùng request schema, lưu config và queue lồng tiếng/mux như Studio |
| **get_job_status** | project_id, job_id | Status, error, result đã lưu và artifact_current |
| **wait_for_job** | project_id, job_id, timeout_seconds 0–30 | Chờ có giới hạn; hết thời gian vẫn trả trạng thái hiện tại, không giả thành công |
| **cancel_project_job** | project_id | Dùng cơ chế cancellation/acknowledgement hiện có; không mở khóa khi native task chưa dừng |

## Ví dụ gọi

Sau khi tạo project và upload qua API/Studio, gửi JSON đến `/api/v1/agent/execute-tool`:

```json
{"tool_name":"extract_and_transcribe_audio","arguments":{"project_id":"PROJECT_ID"}}
```

Phản hồi có `result.status="QUEUED"` và `result.job_id`. Theo dõi bằng:

```json
{"tool_name":"wait_for_job","arguments":{"project_id":"PROJECT_ID","job_id":"JOB_ID","timeout_seconds":10}}
```

Chỉ dùng kết quả khi status là SUCCEEDED. ASR lưu cue vào project và hiện trạng thái ASR_COMPLETE; chưa tuyên bố đã dịch. Khi đã có transcript:

```json
{"tool_name":"start_project_pipeline","arguments":{"project_id":"PROJECT_ID","stage":"TRANSLATING"}}
```

Đợi job dịch, kiểm duyệt cue rồi xuất và burn:

```json
{"tool_name":"export_subtitles","arguments":{"project_id":"PROJECT_ID","format":"ass","preset":"cinema","bilingual":true}}
```

```json
{"tool_name":"burn_video_subtitles","arguments":{"project_id":"PROJECT_ID","clean_chinese_mode":"none"}}
```

ASS export được lưu vào project, nên burn có thể dùng mặc định. `output_path` nếu truyền phải là MP4 mới trong output directory của project; không ghi đè file hiện hữu. Khi project bận, thao tác xung đột trả 409; project/job không thuộc người dùng trả 404. Project export sử dụng cue đã lưu, không đồng thời nhận danh sách cue tùy ý.

## Runner và bằng chứng hoàn thành

Ví dụ `/api/v1/agent/chat`:

```json
{"goal":"Burn phụ đề của project và kiểm tra kết quả","context":{"project_id":"PROJECT_ID","expected_artifact":"burned_video"},"max_iterations":10}
```

`expected_artifact` hỗ trợ burned_video, dubbed_video, subtitles, transcript, translated_cues. Runner bind các hành động có project_id vào project trong context, validate quyết định trước dispatch, và kiểm tra job/artifact trước khi success. Response có `state=COMPLETED|PENDING|FAILED`, `success`, `jobs` và trajectory. QUEUED/RUNNING hoặc hết ngân sách chưa được xác minh là PENDING/FAILED, không phải COMPLETED. Một lỗi tool chưa được xử lý cũng không trở thành thành công chỉ vì LLM trả final_answer.

Giới hạn: tối đa 10 vòng, ngân sách Runner 120 giây, mỗi LLM call tối đa 60 giây, mỗi tool call tối đa 45 giây; chờ job tối đa 30 giây/lần. Job media tiếp tục trong queue khi Runner hết thời gian; client đọc lại bằng job_id. Goal tối đa 4000 ký tự, context 8000 ký tự, tool input 256000 ký tự; history/observation được rút gọn. Quyết định hiện dùng JSON trong prompt; chưa triển khai hoặc kiểm chứng live native SDK function calling.

## Thay đổi hợp đồng và dữ liệu

- ASR/burn trước đây trả kết quả trực tiếp; nay trả job ID. Client cần theo dõi job thay vì đọc ngay cues/output. `Job.result` được lưu vào database và có trong API đọc job. Worker khôi phục owner context từ project khi dispatch.
- Không truyền `preset` cho burn file ASS: field này bị từ chối thay vì báo đã áp dụng. Chọn preset ở export, hoặc dùng cấu hình burn của HTTP/Studio.
- Kiểu theo ảnh: export ASS với `preset="comic"`, sau đó burn với `clean_chinese_mode="white_bars"`. Chữ render trắng đậm nghiêng, in hoa và viền đen; hai dải che nền trắng được vẽ trước ASS. Default của Agent hiện có giữ nguyên. Muốn chỉnh riêng phần trăm chiều cao dải, dùng cấu hình Burn của Studio/HTTP.
- Kiểu theo ảnh: export ASS với `preset="comic"`, sau đó burn với `clean_chinese_mode="white_bars"`. Chữ render trắng đậm nghiêng, in hoa và viền đen; hai dải che nền trắng được vẽ trước ASS. Default của Agent hiện có giữ nguyên. Muốn chỉnh riêng phần trăm chiều cao dải, dùng cấu hình Burn của Studio/HTTP.
- ASR có cue cũ yêu cầu force_reprocess=true; transcript/profiles/relationships cũ chỉ được thay sau khi ASR có kết quả hợp lệ. Các artifact phụ thuộc bị invalidate, revision/status/URLs được snapshot WebSocket đồng bộ.
- Export ASS/SRT của project cập nhật đường dẫn subtitle. File output có phiên bản; `artifact_current=false` cho biết result cũ không còn khớp revision hiện tại. SUCCEEDED là lịch sử thực thi; không bảo đảm output cũ vẫn là phiên bản hiện hành.
- Startup migration version 3 bổ sung JSON `jobs.result` vào DSN đang cấu hình. Sao lưu database/media trước khi khởi động bản nâng cấp; không đổi DSN để né lỗi migration.

## Skills và kiểm thử

Hai skill local mới: [onefl-agent-tools](../.agents/skills/onefl-agent-tools/SKILL.md) và [onefl-media-verification](../.agents/skills/onefl-media-verification/SKILL.md). Skill đầu hướng dẫn hợp đồng tool/job/artifact; skill sau hướng dẫn kiểm thử media và UI đồng bộ trên fixture cô lập.

Acceptance: [Agent completion tests](../tests/test_agent_completion.py), [tool/API tests](../tests/test_agent_tools.py), [worker tests](../tests/test_job_worker.py) và [browser flow](../frontend/tests/browser-flow.cjs). Cách chạy xem [README](../README.md). ASR/LLM/TTS trong kiểm thử dùng provider fixtures; FFmpeg extraction/burn/probe và SQL/job/artifact ở luồng media ngắn là thật. Chưa suy ra chất lượng model, video 10 giờ/50 GB hoặc khả năng triển khai phân tán từ các test này.
