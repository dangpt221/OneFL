# WebSocket lifecycle repair implementation plan

**Goal:** Eliminate client-induced CONNECTING socket aborts during Studio navigation/Fast Refresh, preserving live updates and reconnects.

**Architecture & Constraints:** Keep the same-origin Next.js WebSocket proxy, signed cookies, backend owner checks and existing close-code routing. Repair the client hook only; no media processing, database, provider, RAM/VRAM or job changes. Backend logs show accepted connections for both reported project IDs. Pending handshakes cannot be silently aborted with the browser WebSocket API: retire them by detaching application handlers and closing on open; browser network failure still closes them normally.

**Skills:** systematic-debugging, writing-plans, executing-plans, test-driven-development, nextjs-best-practices, onefl-media-verification, verification-before-completion.

## File impact matrix

| Action | File | Purpose |
| --- | --- | --- |
| Modify | [useWebSocket.ts](/D:/OneFl/frontend/src/lib/useWebSocket.ts:1) | Connection ownership, deferred setup, safe cleanup, project-scoped state/events |
| Create | [websocket-regressions.cjs](/D:/OneFl/frontend/tests/websocket-regressions.cjs:1) | Deterministic hook lifecycle and timer tests |
| Modify | [package.json](/D:/OneFl/frontend/package.json:10) | Include focused regression in standard test command |
| Create | [websocket-browser.cjs](/D:/OneFl/frontend/tests/websocket-browser.cjs:1) | Real Chromium handshake teardown, reconnect and navigation |
| Create | [review](/D:/OneFl/docs/reviews/2026-10-22-websocket-lifecycle.md:1) | Evidence and limits |
| Modify | [session state](/D:/OneFl/.agents/SESSION_STATE.md:1) | Task progress |

## Atomic tasks

1. Write hook regression harness with fake React effects/timers/socket in `frontend/tests/websocket-regressions.cjs:1-220`. Assert no `close()` while CONNECTING, no connection for discarded setup, immediate state reset across IDs, stale events ignored, ping/backoff/terminal-code behavior. Run `node frontend/tests/websocket-regressions.cjs`; expect failures on existing code, captured under `tmp/websocket-lifecycle`.
2. Repair `useProjectWebSocket(projectId?: string)` in `frontend/src/lib/useWebSocket.ts:1-45`: cancellable initial zero-delay connect; effect-local socket ownership; disposed/current-socket checks; project-scoped state; retire CONNECTING via onopen close; allow native error->close to drive retries. Preserve `{isConnected,lastMessage}` return contract and 1..30s retry/15s heartbeat. Run the same command; expect all cases passed and no timers after cleanup.
3. Add regression to `frontend/package.json:10`. Run `npm.cmd test` in frontend and `node frontend/node_modules/typescript/bin/tsc --noEmit --incremental false --project frontend/tsconfig.json`; expect exit 0.
4. Write `frontend/tests/websocket-browser.cjs` using a disposable fixture and a local browser probe rendering the actual hook with development React and StrictMode. Hold a real Node WebSocket upgrade on 3101 to reproduce cleanup during CONNECTING; also test production Next proxy/Studio on 3100 with fixture backend 8100, reconnect and live cue synchronization. Record browser console and CDP Network.webSocketFrameError events, plus socket states. Run with `ONEFL_E2E=1`, artifacts under `tmp/websocket-lifecycle`; expect zero lifecycle warning, successful reconnect and no cross-project events. Do not alter user servers 3000/8000 or their data.
5. Compile/build isolated frontend copy, inspect test output/logs, stop owned helpers, write review and mark state complete. Build under `tmp/websocket-lifecycle/frontend`; preserve live `.next`. Report any unrelated packaging limitation precisely.

## Review checkpoint & fallback

User has authorized debugging and fixes; proceed through reversible local edits and isolated verification. If proxy/authentication failures appear, investigate them separately without weakening owner/origin checks. Keep existing uncommitted resume fixes and recovery media untouched. No deployment/commit or live project mutations.
