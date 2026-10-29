# Agent Tool Review Plan

**Goal:** Assess the ten Agent tools, their composition, Runner/API behavior and synchronization with the supported backend workflow. Report confirmed defects and verification limits; do not infer readiness from registry/schema smoke tests.

**Architecture & constraints:** Reuse current services and security context. All probes use disposable SQLite/storage and mocked external provider/media boundaries; no live project mutation, paid calls or GPU inference. Inspect whether direct tools obey durable queue ownership and expose usable outputs for the next step. This is a review, not a redesign of Agent orchestration.

**File impact matrix:**

| Action | File |
|---|---|
| Read | [tools](/D:/OneFl/backend/app/agent/tools.py:1), [runner](/D:/OneFl/backend/app/agent/agent_runner.py:1), [API](/D:/OneFl/backend/app/api/v1/agent.py:1), linked services/security/tests |
| Create | `docs/reviews/2026-10-21-agent-tool-probes.py`, `docs/reviews/2026-10-21-agent-tool-review.md` |
| Update | [session ledger](/D:/OneFl/.agents/SESSION_STATE.md:1) |

## Atomic tasks

1. Read registry/models/handlers at `tools.py:24–415`; map inputs, outputs and service calls for all ten tools. Expected: exact inventory and contract gaps with line references.
2. Read Runner parsing/dispatch at `agent_runner.py:107–256` and API/auth at `agent.py:20–85`; trace project access, resource admission and failure semantics. Expected: identify real control points, not just `async def` declarations.
3. Run existing acceptance checks safely: `$env:DATABASE_URL='sqlite+aiosqlite:///:memory:'; backend/.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp=tmp/agent-review-tests`. Expected: record actual pass/fail count and warning; no live DSN.
4. Add a standalone audit probe with controlled mocks to reproduce malformed Runner JSON, tool output/error wrapping, speaker/relationship composition and heavy-tool admission/preset behavior. Run `backend/.venv/Scripts/python.exe docs/reviews/2026-10-21-agent-tool-probes.py`. Expected: machine-readable observations in `tmp/agent-review/probe-results.json`; distinguish defect reproductions from acceptance tests.
5. Write the tool-by-tool matrix and prioritized findings with exact file/line evidence; update ledger. Run `git -c core.safecrlf=false diff --check`. Expected: an actionable readiness assessment with provider/load/deployment limits.

**Review checkpoint & fallback:** Continue within the user's request to inspect readiness, without an approval pause. Keep application code unchanged for this review; if tools cannot run safely, report the missing evidence instead of invoking real providers. Existing dirty working-tree changes are preserved.

## Execution record

- [x] Read all ten tool handlers, Runner/API and linked service/security contracts.
- [x] Run fresh backend acceptance suite: 97 passed, one dependency warning.
- [x] Run isolated audit probe: 18 observations, including concrete defects and working/authentication controls; JSON artifact saved under tmp/agent-review.
- [x] Publish [prioritized review and tool matrix](/D:/OneFl/docs/reviews/2026-10-21-agent-tool-review.md), update ledger; preserve application source unchanged.
