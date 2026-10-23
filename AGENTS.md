# Quy tắc phát triển IFCtoFDS

## Nghiệp vụ

Giữ ánh xạ IFC → FDS đúng, truy vết được và kiểm chứng độc lập. Xuất FDS thành công không có nghĩa là đạt nghiệm thu. Không sửa IFC nguồn, tự sinh thiết bị/quan hệ MEP hoặc tự nâng trạng thái VERIFIED. Giữ giấy phép AGPL và notices của vendor.

## Kiến trúc

- Backend là một modular monolith. Bốn context nghiệp vụ: `bim`, `simulation`, `verification`, `reference`. Module kỹ thuật: `geometry`, `fds`, `artifacts`, `jobs`.
- Implementation nằm trong `ifc_to_fds/modules/`, chia application/domain/infrastructure/algorithms/parsing theo trách nhiệm thực tế. Caller ngoài module chỉ import `api.py` hoặc `contracts.py`. Kiểm tra allowed DAG và layer bằng `tests/architecture/` cùng `docs/architecture/dependency-policy.json`.
- `domain/` giữ một định nghĩa cho các model Pydantic. Không sao chép CanonicalModel, MappingPlan hoặc AcceptanceReport. Không đưa HTTP, filesystem, IfcOpenShell hay subprocess vào domain.
- Application điều phối workflow và công bố ports. Adapter được nối tại bootstrap, không tự tạo trong use case. Không tạo lớp/port/event bus cho mọi phép tính thuần.
- Package cũ và `pipeline.py`, `jobs.py`, `server.py` là lớp tương thích; không bổ sung implementation vào facade. Danh sách facade/hash/đích alias nằm trong `docs/architecture/compatibility-imports.json`; không miễn kiểm tra cả package. Bốn bridge tương thích được ghi cụ thể trong policy và ADR 0001.
- MappingPlan giữ ý định; primitive IDs là kết quả serialization. Audit mở lại nguồn và đầu ra đã lưu, không dùng model/cache đã sửa của converter làm bằng chứng độc lập.
- Engine chính vẫn là `modules/verification/application/engine.py`. Chỉ chuyển sang runner/checkers sau khi so đầy đủ findings, evidence, gates và kết quả workflow.
- Workflow xuyên context nằm trong `application/workflows/`; ports workflow nằm trực tiếp trong `application/ports/`. Jobs dùng JobStore/WorkerProcesses/JobRetention và clock; không mở SQLite trong application khi đã inject dependencies.

## Frontend

- Mã giao diện nằm trong `frontend/`. Component hiển thị/phát callback; feature điều phối; API client sở hữu HTTP/auth; viewer sở hữu cảnh và tài nguyên 3D.
- `state/session-state.js` khai báo state phiên. Feature dùng cùng object qua dependency injection, không tạo state phản chiếu. Giữ selection/visibility/scenario stores đúng vai trò.
- Giữ HTTP và `file://`. Không tự đổi framework, ES modules hoặc fetch HTML partials. Root HTML là launcher tương thích.
- Khi thêm dependency engine, cập nhật `frontend/index.html`, `frontend/engine-scripts.json`, worker `importScripts`, generators và harness liên quan.
- Không sửa `frontend/generated/*-inline.js` bằng tay. Chạy hai generator và kiểm tra worker bundle parity.
- `src/app/bootstrap.js` ghép dependencies; feature factory nhận rõ dependencies cần dùng. Dọn listener/subscription/worker/RAF/GPU khi destroy; không nhân listener khi mount lại. Giữ generation/request ID khi đổi nguồn, hủy và nhận phản hồi trễ.

## Kiểm chứng

1. Đọc status/branch/HEAD, giữ công việc có sẵn; đọc tài liệu kiến trúc trước khi sửa.
2. Chạy kiểm tra liên quan. Không sửa fixture/snapshot chuẩn để che sai lệch.
3. Với geometry/serializer: kiểm tra FDS, openings, identity và đối chiếu baseline khi di chuyển thuật toán.
4. Với tài nguyên/frontend: kiểm tra worker thường/inline, WASM, HTTP và mở tệp. Với packaging: chạy wheel ngoài source checkout.
5. Báo riêng PASS/FAIL/BLOCKED/NOT_RUN, ghi cấu hình runtime để tái lập. Không coi kiểm tra bị chặn là PASS.

Không tự commit/push/merge nếu công việc hiện tại chưa yêu cầu. Bản đồ mã: `docs/architecture/README.md`. Hướng dẫn nghiệp vụ bổ sung: `docs/agent-context/AGENTS.md`.
