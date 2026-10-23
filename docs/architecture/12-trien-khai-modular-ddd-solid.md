# 12 — Triển khai Modular Monolith + DDD + SOLID

Ngày kiểm tra: 22/10/2026. Branch: `chore/research-acceptance-hardening`. Commit nền: `f0c6d9c02342312266f2cfb8f9102833640061c3`. Thay đổi đang ở working tree, chưa commit/push. Tài liệu 11 giữ nguyên kế hoạch khảo sát; tài liệu 01–10 mô tả mã sau triển khai.

## Kết quả triển khai

| Phần | Kết quả |
| --- | --- |
| Bounded contexts | `modules/bim`, `simulation`, `verification`, `reference`; mỗi context công bố `api.py` và `contracts.py` |
| Module kỹ thuật | `modules/geometry`, `fds`, `artifacts`, `jobs`; API công khai, kiểm tra dependency không vòng |
| Domain | Giữ model Pydantic chuẩn tại `domain/`; contracts tham chiếu model hiện có, không tạo bản sao |
| Application / DIP | Ports cho đọc IFC, chuẩn bị model, xuất FDS, workspace, validation; bootstrap nối adapter cho convert/audit |
| Artifacts | Workspace quản lý ghi/đọc lại FDS, manifest và checkpoint; giữ draft, sealing, cleanup |
| HTTP / worker | App factory, routes, configuration, security, worker runner; job manager khởi tạo lười |
| Tương thích | Giữ entry/import cũ qua facade; module alias giữ identity cho cache và monkeypatch |
| Frontend | HTML, CSS, vendor, WASM và JavaScript trong `frontend/`; root HTML là launcher tương thích |
| Component / feature | Tabs, modal, progress; sources, preview, conversion, scope, tree, inspector, audit |
| State / API | Một template session state, inject cùng object vào feature; HTTP/auth tập trung trong `src/api/`; giữ workbench stores theo vai trò |
| Viewer | Giữ API `SceneViewer`; tách camera, walk, clipping, geometry loading, mesh, selection, appearance |
| Engine legacy | Tách helper IFC/FDS, giữ thuật toán; đồng bộ script order giữa HTML, manifest, worker, generators và harness |
| CSS | Tách tokens, nền, layout, component, feature, responsive; manifest kiểm tra hash và thứ tự khai báo gốc |
| Phân phối | Wheel/sdist chứa frontend; server tìm asset khi cài ngoài checkout |
| Hướng dẫn | Cập nhật AGENTS, tài liệu kiến trúc, frontend README và kiểm tra kiến trúc |

DDD được áp dụng ở ranh giới nghiệp vụ và thuật ngữ. SOLID tập trung vào trách nhiệm module, interface nhỏ và dependency injection tại ranh giới kỹ thuật. Không thêm aggregate/repository/event bus cho mọi phép tính hoặc tuyên bố mọi lớp đã được thiết kế lại.

## Lựa chọn cần biết khi review

- Engine chính vẫn là `modules/verification/engine.py`. Runner/checkers chưa thay thế engine vì cần so đầy đủ findings, evidence và gates trước khi chuyển.
- Audit tiếp tục mở lại IFC nguồn và đầu ra đã lưu. Không dùng model/cache đã sửa của converter làm bằng chứng độc lập.
- Quick và Verified Conversion giữ hai đường chạy. Xuất được FDS không tự nâng trạng thái acceptance.
- Digest chứng nhận boundary trỏ đến implementation mới thay vì facade. Chứng nhận cũ cần tạo lại; kiểm tra solver đã tạo chứng nhận mới.
- Geometry download dùng chung transport/auth. Đây là sửa tính nhất quán xác thực khi tải artifact, không thay đổi geometry hoặc mapping.
- Giữ classic scripts/IIFE để hỗ trợ `file://`; không chuyển framework hoặc bắt buộc build server.
- Không thay nội dung IFC nguồn, snapshot/fixture chuẩn hoặc giấy phép vendor để làm kiểm tra xanh.

## Bằng chứng kiểm tra

| Trạng thái | Kiểm tra | Kết quả / giới hạn |
| --- | --- | --- |
| PASS | Python ngoài ba nhóm HTTP/lifecycle | **338 passed, 6 deselected**, 96 warnings; `.cache/refactor-release.xml`; cảnh báo số học trimesh chưa xử lý trong refactor |
| PASS | Lifecycle không cần HTTP transport | **6 passed, 3 deselected**; `.cache/refactor-lifecycle-release.xml` |
| PASS | Solver FDS 6.11.1 thật | **2 passed, 2 deselected**; `.cache/refactor-solver-shm.xml`; boundary fixtures, tạo chứng nhận và từ chối đầu ra bị đổi |
| PASS | JavaScript | **13 script**: modular frontend, worker parity, UI recovery, workbench stabilization/feature4, golden workflow, artifact viewer/downloads, verified regressions, background worker, legacy geometry, openings, large opening |
| PASS | Engine legacy trước/sau | Inventory JSON và FDS hybrid/GEOM giống chính xác trên Haus, Institute, Duplex; `scripts/out/refactor-parity/results.json` có source/output hashes |
| PASS | OpenAPI | Toàn bộ schemas, operation IDs và **16 paths** giống commit nền |
| PASS | Chromium thật, `file://` | Legacy inline và web-ifc: import, selection, xuất/tải FDS, lỗi hiển thị vẫn giữ download, đổi nguồn xóa đầu ra cũ; không page error; `.cache/browser-regression.json` |
| PASS | Wheel / sdist | Build, kiểm tra assets, cài target mới; chạy CLI, API schema, convert tiny IFC ngoài checkout: `MAPPING_VERIFIED`, FDS parse không lỗi; `.cache/refactor-dist/smoke.json` |
| FAIL — kiểm tra legacy tồn tại trước refactor | `scripts/test-ifc-conversion.js` | Ba assertion số tam giác: Institute hybrid 2890/2854, Institute GEOM 41371/41335, Duplex GEOM 5214/5212 (kỳ vọng/thực tế); đầu ra trước/sau giống nhau, không sửa thuật toán hoặc snapshot |
| BLOCKED | HTTP TestClient đầy đủ | API server, backend preview và ba case lifecycle HTTP: CPython Windows kẹt ở `socketpair` fallback / `accept` trước dispatch; component tests và OpenAPI đạt nhưng chưa thay thế transport integration |
| NOT_RUN | Hiệu năng IFC lớn và nghiên cứu thực tế | Chưa đo đối chứng cold/warm, peak RAM, độ trễ UI và tài nguyên sau hủy trên dự án lớn |

Các nhóm Python được ghi riêng để tránh đếm case trùng hoặc bị deselect. Browser ở đây kiểm tra Quick Conversion và assets; chưa chứng minh Verified Conversion qua HTTP end-to-end đạt. Không coi kiểm tra bị chặn là pass.

Đã chạy chính script conversion tại commit nền và tại working tree: cùng exit code 1 và cùng ba lỗi đếm tam giác (`.cache/inherited-legacy-failures.json`). Vì vậy đây là lỗi kiểm tra có sẵn, không chỉ là suy luận từ parity trên cấu hình khác. Tám tài nguyên vendor giữ nguyên nội dung khi chuẩn hóa LF/CRLF cho văn bản; WASM giống từng byte. `git diff --check` đạt với cấu hình nhận diện CRLF; baseline fixtures/snapshots không có thay đổi.

## Chạy lại

Trong Windows này, tạo thư mục `.cache/refactor-tmp`, đặt TEMP/TMP và job root về workspace; dùng basetemp riêng cho mỗi lượt. Đây là cấu hình kiểm tra, không thay cấu hình mặc định sản phẩm.

```powershell
$env:TEMP = "$PWD/.cache/refactor-tmp"
$env:TMP = $env:TEMP
$env:IFCFDS_JOB_ROOT = "$PWD/.cache/refactor-check-jobs"
.venv/Scripts/python.exe -m pytest -q `
  --ignore=tests/test_api_server.py `
  --ignore=tests/test_backend_preview.py `
  --ignore=tests/test_job_lifecycle.py `
  --basetemp=.cache/refactor-check
.venv/Scripts/python.exe -m pytest tests/test_job_lifecycle.py -q `
  -k "not early_admission and not body_limit and not api_key" `
  --basetemp=.cache/refactor-check-lifecycle
node scripts/test-modular-frontend.js
node scripts/test-worker-bundle-parity.js
node scripts/test-refactor-parity.js
```

Solver cần `IFCFDS_SOLVER` trỏ tới `.deps/fds-6.11.1/firemodels/FDS6/bin/fds_openmp.exe` và `I_MPI_FABRICS=shm`. Fabric OFI mặc định đã lỗi khởi tạo Intel MPI trước khi chạy mô hình; shared memory chạy đạt. Không suy kết quả solver từ việc parse FDS.

Trên môi trường transport hoạt động, chạy toàn bộ nhóm `python -m pytest -q -m "not solver and not browser"`, sau đó browser và solver riêng theo CI. Build offline bằng `python -m pip wheel --no-index --no-deps --no-build-isolation --wheel-dir .cache/refactor-dist .` với Python có setuptools. Cài wheel vào target mới và đổi cwd ra ngoài checkout để kiểm tra assets của bản phân phối.

## Điều kiện nghiệm thu còn lại

1. Chạy các case HTTP bị chặn và Verified Conversion từ upload đến tải artifact trên môi trường event loop/socket hoạt động.
2. Rà riêng ba assertion đếm tam giác bằng bất biến hình học và bằng chứng loại mặt suy biến; không cập nhật số chỉ để pass.
3. Đo đối chứng hiệu năng/bộ nhớ/hủy/đổi nguồn trên IFC lớn với cùng máy, cấu hình và tiêu chí sai lệch đã thống nhất.
4. Chỉ chuyển validation runner hoặc gỡ facade sau khi có parity đầy đủ và cập nhật caller.

Review theo nhóm frontend, viewer/engine, HTTP/ports, module boundaries và packaging. Chưa tạo commit, PR, phát hành hoặc triển khai dịch vụ.
