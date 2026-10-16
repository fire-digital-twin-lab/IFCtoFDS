# 05 — Baseline repository / mã nguồn đã có

## Nguồn đã quan sát

- ZIP local `IFCtoFDS-v0.1.0.zip`, SHA-256 `3ea08378a8e29a85d6431961bdaaa3c01a86844d35ffb07b10ba39c7079214bf`.
- Release gốc `ProfRino/IFCtoFDS` v0.1.0; `CITATION.cff` nêu 2026-06-02, AGPL-3.0-or-later.
- Fork GitHub được kiểm tra ngày 2026-10-16: `fire-digital-twin-lab/IFCtoFDS`, default `main`, parent `ProfRino/IFCtoFDS`, `main` SHA `7352195f8892f1ebd963aeb48b3bd739d7859198` tại thời điểm kiểm tra. SHA có thể đổi, hãy fetch lại.
- ZIP có 62 entries, gồm HTML/CSS, JavaScript, tài liệu, ba IFC mẫu và FDS mẫu. Đây là snapshot v0.1.0; nhánh GitHub có thể khác.

## Cấu trúc thực tế v0.1.0 (không dự đoán thêm)

```text
index.html, guide.html
css/app.css, css/guide.css
js/app-controller.js
js/core/{namespace,diagnostics}.js
js/ifc/{ifc-adapter,ifc-meta,web-ifc-display,processed-file}.js
js/fds/{fds-exporter,namelist-parser,fds-geometry-adapter}.js
js/viewer/scene-viewer.js
js/compare/checks.js
js/workers/{ifc-parse-*,fds-export-*,web-ifc-display-worker.js}
js/vendor/earcut.min.js
scripts/{test-ifc-conversion,test-background-export-worker,
         generate-inline-parse-worker,generate-inline-export-worker,...}
examples/{AC20-FZK-Haus,AC20-Institute-Var-2,IfcOpenShell-Duplex}.ifc
README.md, LICENSE, CITATION.cff, CHANGELOG.md
docs/{architecture,conversion-strategies,conversion-test-results}.md
```

## Đặc điểm as-is

- Trang HTML tĩnh, module cổ điển dưới `window.IfcFds`, có khả năng chạy `file://` một phần với inline worker bundles.
- `ifc-adapter.js`: parser STEP/hình học riêng hỗ trợ tập con IFC; đồng thời phân vai geometry/semantic.
- `web-ifc-display.js`: đường xem trước IFC; không mặc nhiên là cùng mesh với exporter.
- `fds-exporter.js`: hỗ trợ OBST+GEOM, all-GEOM, HOLE/voxel strategies; structured `! IFC_SOURCE` comments.
- `namelist-parser.js` và `fds-geometry-adapter.js`: đọc/reopen FDS cho viewer.
- `scene-viewer.js`: overlay IFC/FDS, layer controls/clip/walk.
- `checks.js`: geometric sanity checks tương đối hạn chế, chưa phải independent IFC↔FDS validator.
- Inline bundles cần sinh lại khi source thay đổi: `node scripts/generate-inline-parse-worker.js` và `node scripts/generate-inline-export-worker.js`.

## Kết quả kiểm thử đã ghi từ review ngày 15/10 (KHÔNG là kết quả chạy ở HEAD mới)

| Test | Kết quả lúc audit |
|---|---|
| `node --check` cho JS | Không phát hiện lỗi syntax |
| `node scripts/test-background-export-worker.js` | PASS, FZK: 162 OBST + 5 GEOM; inline worker 162 OBST |
| FZK parse | 44.249 STEP, 47 imported, 22 default exported, ~2.5 s (lần đo trước) |
| Duplex parse | 27.529 STEP, 208 imported, 84 default exported, ~3.0 s |
| FZK một tường có 3 openings | displayMesh 1.532 triangles vs export mesh 12 triangles, nhánh all-GEOM mất lỗ |
| Duplex IFC source | Có 13 IFCCOVERING, 7 IFCFOOTING, allowlist importer đã bỏ qua |
| Full regression | Chưa hoàn tất, không coi PASS |
| FDS official solver run | Chưa xác minh thực hiện |

Số đếm `imported`, `default exported` chỉ mô tả nhánh importer gốc; KHÔNG thể dùng trực tiếp tính correctness/completeness. Thời gian chạy có biến động và máy thử có thể khác.

## Chiến lược tái sử dụng

- **Giữ:** frontend, viewer, namelist parser, file:// legacy compatibility, worker infrastructure, script test nền.
- **Refactor:** exporter theo canonical model và policy, checks sang validator độc lập, app-controller để tách scope/display.
- **Thay/chặn đường authoritative:** parser IFC tự viết không dùng làm nguồn xác thực cho Verified mode; IfcOpenShell giữ vai trò parser/geometry authority.
- **Không làm:** rewrite toàn bộ frontend trong phase 0.
