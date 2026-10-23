# Giao diện IFCtoFDS

Giao diện dùng JavaScript IIFE và thư viện đóng kèm, không cần npm hoặc bundler.

- Mở root `index.html` hoặc `frontend/index.html` để dùng Quick Preview bằng `file://`.
- Chạy `python -m uvicorn ifc_to_fds.server:app --host 127.0.0.1 --port 8000` và mở `http://127.0.0.1:8000` để dùng backend. Verified Conversion cần HTTP.

| Thư mục | Trách nhiệm |
| --- | --- |
| `src/app` | Khởi tạo, ghép feature và nối sự kiện |
| `src/components` | Tabs, modal, progress overlay |
| `src/features` | Sources, preview, conversion, scope, tree, inspector và audit |
| `src/state` | State phiên và các store tương tác |
| `src/commands`, `src/selection`, `src/events` | Undo/redo, selection và thông báo |
| `src/api` | HTTP và auth dùng chung |
| `src/viewer` | Runtime facade, camera, walk, clipping, mesh, selection, appearance, geometry loading |
| `src/engines/legacy` | Thuật toán Quick Preview chia theo trách nhiệm |
| `src/workers` | Worker entry và factory |
| `styles` | CSS component/feature, giữ thứ tự cascade |
| `vendor`, `generated` | Thư viện/WASM/giấy phép và bundle được sinh |

`src/app/bootstrap.js` tạo một state phiên, viewer và các feature factory với dependencies tường minh. `app-controller.js` là launcher; shell và workbench bindings tách riêng. Không sao chép mesh vào store phản ứng. SceneViewer giữ API cũ; installer nối phương thức trước khi tạo viewer. Engine legacy nối trực tiếp tham chiếu hàm sau khi đăng ký module, tránh wrapper trong vòng lặp tính toán.

Mỗi factory trả teardown handle qua `shared/lifecycle.js`. `IfcFds.app.instance.destroy()` hủy polling/worker, unsubscribe store, gỡ listener và giải phóng viewer; bootstrap có thể mount lại. Viewer nhận geometry client; jobs/artifacts clients sở hữu endpoint/auth, còn feature quyết định hành vi giao diện.

Khi thêm dependency, cập nhật thứ tự script, engine manifest, generators, worker imports và test harness. Không fetch manifest trong đường chạy `file://`.

Chạy từ root repository:

```powershell
node scripts/generate-inline-parse-worker.js
node scripts/generate-inline-export-worker.js
node scripts/test-worker-bundle-parity.js
node scripts/test-modular-frontend.js
node scripts/test-frontend-lifecycle.js
```

Với môi trường đã cài Python Playwright và Chromium, chạy `node scripts/test-layout-browser.js` để kiểm tra HTTP/WASM, Verified, tải FDS và destroy/mount lại. Có thể chọn Chromium có sẵn qua `IFCFDS_BROWSER_EXECUTABLE`.

Wheel đóng frontend vào `ifc_to_fds/_frontend`; bản cài không cần source checkout để tìm HTML/WASM.
