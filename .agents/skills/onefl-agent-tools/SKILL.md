---
name: onefl-agent-tools
description: Extend or repair OneFL Agent tools, project job adapters and Runner contracts. Use for Agent tool integration and tool-to-tool data flow in this repository.
---

# OneFL Agent tools

Read [the maintained tool contract guide](../../../docs/agent-tools.md) before changing a tool. Inspect the relevant handler, request model, project adapter and regression; preserve existing public fields unless documenting a deliberate migration.

Use `backend/app/agent/contracts.py` for cue aliases and bounded decisions. ASR emits `speaker_tag/original_text`; the profiler service consumes `speaker/text`. Normalize at that boundary rather than discarding observed speaker IDs. Relationship lists must remain accepted by translation/QC adapters.

Media mutations use `agent_project_service` and the durable queue. Keep project ownership, atomic admission, saved input configuration and worker owner-context restoration. A QUEUED response acknowledges admission; completion requires terminal job status and a current DB-referenced artifact. Never bypass the queue by calling a renderer/ASR handler from an HTTP tool to make a test pass.

Export style belongs to ASS generation. Burn consumes that ASS and writes a new output path. When changing cue/source data, invalidate derived outputs and advance the project revision in the same transaction. Keep the Studio snapshot and job result coherent. Use paginated project context instead of placing a long transcript into the Runner history.

Add a regression for the user-visible failure, then run it against isolated storage/SQLite. For media handoff changes, use the real short FFmpeg chain in `tests/test_agent_completion.py`; mock external ASR/LLM/TTS boundaries only. Preserve ownership, cancellation, recovery and false-completion tests when adding tools. Run the full suite and frontend tracker checks when contracts affect status display.

Report what ran, where the evidence is, and remaining provider/load limits. Tool registry/schema presence alone does not establish end-to-end behavior.
