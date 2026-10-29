# Sửa vòng đời WebSocket Studio — 2026-10-22

Đã tái hiện đúng lỗi `WebSocket is closed before the connection is established.` bằng hook cũ trên Chromium, rồi xác minh bản sửa với cùng handshake bị trì hoãn. Thông báo React DevTools và Fast Refresh trong console là thông tin của môi trường phát triển; phần cần sửa là thao tác đóng WebSocket quá sớm.

## Nguyên nhân và thay đổi

- [Hook](/D:/OneFl/frontend/src/lib/useWebSocket.ts:1) cũ tạo socket ngay trong effect, cleanup gọi `close()` dù `readyState === CONNECTING`; `onerror` lại gọi `close()`. Khi đổi trang, đổi project hoặc effect được dựng lại, trình duyệt có thể hủy handshake và báo lỗi người dùng gặp.
- Hook mới trì hoãn mở kết nối bằng timer có thể hủy. Cleanup đóng ngay socket OPEN; với CONNECTING, gỡ handler cập nhật dữ liệu và đóng ngay khi handshake hoàn tất. Không gọi `close()` trong `onerror`; lỗi mạng thật vẫn đi qua sự kiện close và cơ chế retry.
- Mỗi effect giữ socket của riêng nó. Handler có kiểm tra effect đã hủy và socket hiện hành; mọi timer được dọn khi unmount. Thông điệp phải khớp project ID. Trạng thái project trước bị che ngay trong render khi ID thay đổi hoặc bị bỏ chọn.
- Giữ same-origin cookie/proxy, heartbeat 15 giây, backoff 1–30 giây, reset backoff khi kết nối thành công và xử lý mã đóng 4401/4403/4404 hiện có. Không thay API, quyền truy cập, schema, worker hay dữ liệu media.

## Bằng chứng

| Kiểm tra | Kết quả thực tế |
| --- | --- |
| Regression trước sửa | 7/9 trường hợp thất bại; xác nhận cleanup CONNECTING, trạng thái/sự kiện sai project và đóng socket trong onerror |
| [Regression hook](/D:/OneFl/frontend/tests/websocket-regressions.cjs:1) sau sửa | 9/9 pass; đã thêm vào `npm.cmd test` |
| Frontend regressions đầy đủ | `npm.cmd test` exit 0 |
| TypeScript | `tsc --noEmit --incremental false` exit 0 |
| [Chromium](/D:/OneFl/frontend/tests/websocket-browser.cjs:1) | 8/8 scenario pass; 0 pageerror, 0 console/CDP WebSocket error ở bản sửa |
| Baseline Chromium | Ghi được native WebSocket error đúng nội dung; mã cũ gọi close ở state 0, sau đó onerror gọi lại ở state 3 |
| Kết nối chậm/StrictMode | Handshake trì hoãn 400 ms; unmount và đổi project đóng sau OPEN, không đóng khi CONNECTING; discarded setup không tạo thêm socket |
| Next.js → FastAPI thật trong fixture | Cookie đăng nhập, hai tab nhận cập nhật phụ đề, reconnect lấy lại bản sửa bị lỡ, rời Studio đóng socket; đều pass |
| Production build trong bản sao | Exit 0, compile/typecheck/prerender hoàn tất; standalone trace-copy có Windows symlink EPERM do node_modules junction, xem giới hạn dưới |
| Runtime người dùng, chỉ đọc | Health 3000/8000 HTTP 200; chunk Studio đang phục vụ chứa logic safe retirement và project-scoped state mới |

Artifacts: [browser JSON](/D:/OneFl/tmp/websocket-lifecycle/browser-results.json), [trace](/D:/OneFl/tmp/websocket-lifecycle/browser-trace.zip), [ảnh Studio sau reconnect](/D:/OneFl/tmp/websocket-lifecycle/studio-reconnected.png), [unit trước sửa](/D:/OneFl/tmp/websocket-lifecycle/unit-before.log), [frontend tests](/D:/OneFl/tmp/websocket-lifecycle/frontend-tests.log), [build log](/D:/OneFl/tmp/websocket-lifecycle/build.log), [runtime chỉ đọc](/D:/OneFl/tmp/websocket-lifecycle/live-readonly.json).

Chromium báo lỗi handshake gốc qua CDP `Network.webSocketFrameError`, không qua `page.on('console')` trên bản cài hiện tại. Runner đã thu cả hai kênh; các lần đầu chỉ nghe console không được dùng làm bằng chứng hoàn thành.

## Chạy lại

```powershell
# Từ thư mục dự án:
node frontend/tests/websocket-regressions.cjs
node frontend/node_modules/typescript/bin/tsc --noEmit --incremental false --project frontend/tsconfig.json

# Trong frontend:
npm.cmd test
```

Browser runner yêu cầu fixture riêng theo [README](/D:/OneFl/README.md:71), frontend build trỏ backend 8100 chạy tại 3100, và cổng 3101 trống. Dùng work directory riêng để tránh ghi dữ liệu runtime đang dùng:

```powershell
$env:ONEFL_E2E='1'
$env:ONEFL_E2E_WORK_DIR='D:/OneFl/tmp/websocket-lifecycle/runtime'
$env:ONEFL_E2E_PORT='8100'
$env:NODE_PATH='D:/OneFl/tmp/feature-audit/tools/node_modules'
$env:ONEFL_TEST_ARTIFACTS='D:/OneFl/tmp/websocket-lifecycle'
# Chỉ bật để so sánh khi có bản hook cũ đã lưu:
$env:ONEFL_WS_BASELINE_SOURCE='D:/OneFl/tmp/websocket-lifecycle/useWebSocket-before.ts'
node frontend/tests/websocket-browser.cjs
```

Không đặt biến baseline nếu chỉ chạy acceptance cho mã hiện tại; khi đó có 7 scenario. Không chạy fixture vào cổng/data đang có người sử dụng.

Sau kiểm tra đã dừng đúng PID fixture sở hữu trên 3100/8100; probe 3101 tự đóng. Kiểm tra socket xác nhận cả ba cổng trống, trong khi server người dùng 3000/8000 tiếp tục trả health HTTP 200. [Bằng chứng dừng fixture](/D:/OneFl/tmp/websocket-lifecycle/fixture-shutdown.json).

Kiểm tra cuối từng phát hiện frontend cũ PID 20856 đã thoát và cổng 3000 không còn lắng nghe. Đã khởi động lại frontend development ở 3000 (launcher 26840, child 21736); giữ nguyên backend PID 26316. Homepage, trang Studio và health trả HTTP 200; chunk mới có bản sửa. [Bằng chứng sau khởi động](/D:/OneFl/tmp/websocket-lifecycle/live-restored.json). Log frontend mới có EACCES khi Next cố lấy thông tin phiên bản qua mạng hạn chế và cảnh báo Node util._extend; ứng dụng đạt Ready và phục vụ trang bình thường. Không coi các log khởi động này là hoàn toàn không lỗi.

## Giới hạn và bàn giao

Build source được sao vào `tmp/websocket-lifecycle/frontend` để giữ nguyên `.next` của server người dùng. Junction node_modules gây cảnh báo quyền tạo symlink khi Next sao chép standalone; build exit 0 và production bundle phục vụ được qua `next start`, nhưng không chứng nhận đóng gói standalone. Fixture có thêm cảnh báo Next standalone và Node util._extend đã có từ trước; không có backend ERROR/Traceback trong lượt kiểm tra.

Đây là kiểm tra vòng đời React development/StrictMode, browser WebSocket và Studio production proxy. Không tự động hóa thao tác sửa file để kích hoạt toàn bộ giao thức Fast Refresh của Next, không chứng nhận mọi lỗi mạng/proxy/phiên hết hạn và không ẩn lỗi mạng thật. Không thay đổi backend đang chạy, project người dùng, DB, `.env`, media recovery, provider/model hay commit/push. Frontend development hiện đã phục vụ mã mới; tải lại tab Studio để bỏ log cũ và kiểm tra phiên mới.
