# 03 - Quy tắc dependency

1. Interfaces gọi application/public API; route không quyết định mapping hay acceptance.
2. Application dùng domain, public APIs và ports; bootstrap/module factory chọn adapters. Bốn bridge tương thích cụ thể được ghi trong policy, không mở ngoại lệ cho toàn bộ layer.
3. Import HTTP app không mở job database hoặc chạy worker. Job manager mặc định khởi tạo lười; app sở hữu shutdown.
4. Domain không import application/infrastructure/interfaces/bootstrap, IfcOpenShell, HTTP hoặc subprocess. Giữ model Pydantic và helper thuần.
5. Caller ngoài module dùng `api.py`/`contracts.py`. Kiểm tra cả cạnh được phép, cycle, đích lazy export và layer.
6. Worker runner thuộc delivery. Jobs không import conversion workflow. JobStore, WorkerProcesses, JobRetention và clock thay được độc lập.
7. Geometry không phụ thuộc BIM/Verification. Preview phối hợp nguồn/hình học thuộc BIM; boundary acceptance thuộc Verification.

| Module | Module phụ thuộc runtime |
| --- | --- |
| Geometry | Không |
| BIM | Geometry |
| Simulation | Geometry |
| FDS | Geometry, Simulation |
| Reference | FDS, Geometry |
| Verification | BIM, FDS, Geometry, Simulation |
| Artifacts | Geometry |
| Jobs | Không |

Cạnh Verification → BIM phục vụ đối chiếu graph MEP qua public API, được ghi trong [ADR 0001](decisions/0001-module-ownership.md). Shared model contracts không cho phép import implementation context khác.

[dependency-policy.json](dependency-policy.json) là policy máy đọc. [compatibility-imports.json](compatibility-imports.json) ghi từng facade được review và hash; alias trỏ thẳng tới implementation cuối. Bốn bridge: constructor Jobs cũ → factory; engine Verification cũ → solver default; Reference parity cũ → bundle reader default; Simulation boundary re-export digest.

Chạy `python -m pytest -q tests/architecture`. AST helpers trong `tests/support/` kiểm tra import tương đối/tuyệt đối và lazy exports. Negative cases chứng minh phát hiện private import, undeclared edge, legacy bypass, domain I/O và application concrete adapter. AST không phân tích được mọi import động của Python.
