# 14 - Kết quả tổ chức mã theo Modular Monolith, DDD và SOLID

Triển khai 22/10/2026, kiểm tra bổ sung 23/10/2026. Branch `chore/research-acceptance-hardening`, HEAD nền `f0c6d9c02342312266f2cfb8f9102833640061c3`. Phạm vi là working tree có sẵn sau tài liệu 12, không chỉ HEAD. Không commit/push trong phiên này.

## Kết quả triển khai

Đã thực hiện các thay đổi P00–P10 của [kế hoạch 13](13-review-va-ke-hoach-to-chuc-ma.md). 51 implementation files được đặt theo trách nhiệm trong 8 module; import công khai được giữ, alias trỏ tới implementation cuối. Mỗi module có README. [Manifest](module-layout-migration.json) giữ hash nguồn đã review, hash đích và bằng chứng kiểm tra; [ADR 0001](decisions/0001-module-ownership.md) chốt ownership/shared model và các ngoại lệ tương thích.

| Phần | Thay đổi cụ thể |
| --- | --- |
| P00–P01 | Checkpoint bất biến trước thay đổi; policy allowed DAG/layer và registry 131 facade cụ thể; positive/negative import tests |
| P02 Artifacts | Filesystem/workspace về infrastructure; workflow truyền CheckpointPayload thay vì adapter import helper application |
| P03 BIM | IFC/MEP readers và preview về infrastructure; so graph thuần trong domain; native handles không ra contract |
| P04 Geometry | Mesh/boolean/metrics/sealing về algorithms; extraction/cache/payload về infrastructure; package service phụ thuộc payload protocol |
| P05 Simulation/FDS | Policies/application và serializer/manifest/parser tách đúng owner; implementation digest bind code thật, không bind alias |
| P06 Verification/Reference | Engine/rules/checkers về application; solver/bundle/filesystem về infrastructure; workflow audit giao saved evidence cho Verification, inject solver/reference reader |
| P07 Jobs | JobStore/WorkerProcesses/JobRetention và clock thay được; production factory giữ SQLite/RLock/process/retention; tick thực được kiểm tra với dependencies giả |
| P08 Delivery | Workflows xuyên context, ports phẳng, CLI và routes HTTP theo nhóm; adapters về module sở hữu; results/diagnostics/normalization/provenance về đúng trách nhiệm |
| P09 Frontend | Bootstrap/shell/workbench bindings và feature factories; dependency tường minh; jobs/artifacts clients; teardown listener/store/worker/viewer; giữ IIFE và load order |
| P10 | 47 test files nhóm theo owner; helper chung trong tests/support; cập nhật CI, AGENTS, README/module docs; thêm harness trình duyệt và benchmark có baseline root tường minh |

Engine active vẫn là Verification application engine. Không chuyển sang runner/checkers. CanonicalModel, MappingPlan, AcceptanceReport giữ một định nghĩa Pydantic trong domain; chưa tuyên bố context model độc lập hay enforced immutability. Caller ngoài module chỉ dùng api/contracts; bốn bridge tương thích có đường dẫn cụ thể trong policy.

Phát hiện và sửa riêng một lỗi có từ baseline: import inventory đầu tiên trong process mới gây vòng import qua core.__init__. Reproducer subprocess thất bại trước sửa, đạt sau khi các core inventory exports được resolve lười. Không thay extraction, tolerances, output chuẩn hoặc thuật toán để làm test xanh.

## Bằng chứng kiểm tra

Kết quả cục bộ trên Windows, Python 3.12.10, Node 24.13.1, Chromium headless qua Playwright 1.58 và FDS 6.11.1. CI cấu hình Node 22; đọc cấu hình không đồng nghĩa các matrix jobs trên GitHub đã chạy.

| Kiểm tra | Kết quả / bằng chứng cục bộ |
| --- | --- |
| Baseline trước sửa cold import | 363 passed, 1 failed, 7 deselected; `.cache/layout-p00/baseline.xml` |
| Python sau tổ chức tests | 376 passed, 7 deselected; `.cache/layout-final2.xml` |
| Tổng hợp Python chính và bổ sung | 377 test cases khác nhau đạt, không cộng lặp các lượt chạy; `.cache/layout-final-summary.json` |
| Contract cuối, cold imports, parser độc lập và Jobs ports | 60 passed; `.cache/layout-final-contract.xml`; gồm test FDS parser mới thêm sau lượt full suite |
| Sau khi chuyển helper dùng chung về tests/support | 117 passed; `.cache/layout-helper-final.xml`; giữ nguyên assertions của Reference/workflows/architecture |
| HTTP + Jobs sau tách tick | 33 passed; `.cache/layout-http-final.xml` |
| Public HTTP contract | OpenAPI giống hệt baseline: 16 paths, đầy đủ schemas và operation IDs; `.cache/http-schema-before.json`, `.cache/http-schema-after.json` |
| Các phase backend | P02: 54; P03: 29; P04: 31; P05: 49; P06: 55 passed, 2 deselected; `.cache/layout-p0*/tests.xml` |
| JavaScript | 14 harness đạt, gồm lifecycle, worker parity, UI recovery, workflows/artifacts, openings và workbench; `.cache/layout-final-*.log` |
| Legacy output | Inventory JSON và FDS hybrid/geom giống hệt trên 3 IFC công khai; `scripts/out/refactor-parity/results.json` |
| Python workflow evidence trước/sau | Tiny/opening/MEP đều FULL_EVIDENCE_IDENTICAL: toàn bộ report/findings/evidence/coverage/gates, manifest, inventory, MEP graph và FDS; `scripts/out/layout-python-parity-final/results.json` |
| FDS thật | 2 passed, 2 deselected; `.cache/layout-solver.xml`; tái chứng nhận boundary và phát hiện output đã sửa; `I_MPI_FABRICS=shm` |
| Trình duyệt HTTP/WASM/Verified | `scripts/test-layout-browser.js` đạt: nạp IFC bằng web-ifc thật, audit MAPPING_VERIFIED, tải FDS; `scripts/out/layout-browser/results.json` |
| Toàn bộ test đánh dấu browser, lượt sạch | 5 passed, 379 deselected; `.cache/layout-browser-clean.xml`; gồm workbench và large preview |
| Teardown/mount lại | Store listener counts 2/2 → 0/0 → 2/2; canvas sau destroy = 0; bằng chứng cùng browser harness |
| File trực tiếp | Legacy inline import/selection/export/reset và giữ download khi lỗi display đạt; `.cache/browser-regression.json`. Lượt web-ifc qua file URL timeout; không tính PASS cho nhánh này |
| Wheel/sdist | Build đạt; wheel cài vào target mới, toàn bộ public symbols của 8 module resolve; CLI/static/WASM/API 16 paths và tiny conversion MAPPING_VERIFIED chạy ngoài checkout; `.cache/layout-dist/smoke-final.json`, `.cache/layout-package.log` |
| Integrity | 8 vendor files giữ nội dung (WASM byte exact, text normalize CRLF); fixtures/snapshots không đổi; diff whitespace check đạt |
| Hủy native worker thật | Institute 10.786.515 bytes, lời gọi backend cancel tại IFC_GEOMETRY trả về sau 0,0658 s; cả 3 owned processes dừng, supervisor đóng, source hash giữ nguyên; `scripts/out/layout-job-cancel/results.json`. Số đo không bao gồm HTTP/UI latency |

Các lượt chạy browser đầu từng lỗi khởi chạy Edge và chờ viewer chưa sẵn sàng. Harness hiện hỗ trợ executable Chromium tường minh và đợi UI ready; lượt sạch cuối đã đạt cả 5 test. Large preview dùng IFC thực 17 walls có padding 33 MiB để kiểm tra transport/chunking và cấm whole-file browser decode; không đại diện dự án hình học lớn.

14 JavaScript harness: test-frontend-lifecycle, test-modular-frontend, test-worker-bundle-parity, test-ui-recovery, test-workbench-stabilization, test-workbench-feature4, test-golden-workflow, test-artifact-viewer, test-verified-regressions, test-background-export-worker, test-artifact-downloads, test-legacy-geom-compatibility, test-geom-opening-regression, test-large-opening.

## Tái lập

```powershell
python -m pytest -q
python -m pytest -q tests/architecture tests/compatibility tests/modules/jobs
node scripts/test-frontend-lifecycle.js
node scripts/test-worker-bundle-parity.js
node scripts/test-refactor-parity.js
python -m playwright install chromium
python -m pytest -q -m browser
node scripts/test-layout-browser.js
$env:IFCFDS_SOLVER = (Resolve-Path '.deps/fds-6.11.1/firemodels/FDS6/bin/fds_openmp.exe').Path
$env:I_MPI_FABRICS = 'shm'
python -m pytest -q -m solver
```

Trong môi trường này dùng `.venv/Scripts/python.exe` và Chromium có sẵn qua `IFCFDS_BROWSER_EXECUTABLE`. `scripts/test-layout-evidence.py` nhận baseline/current roots cùng danh sách source để so đầy đủ evidence. Các trường được chuẩn hóa là dictionary timings ở cấp đầu của mỗi kết quả, report.metrics.solver_s, report.metrics.stage_timings và prefix thư mục chạy; không bỏ findings, evidence, coverage hay gate nào.

`scripts/benchmark-layout.py` nhận `--baseline-root`, `--current-root`, các `--source` và `--output`; baseline phải là package source trước thay đổi, không dùng working tree hiện tại làm cả hai phía. Warm sample chỉ dùng cache converter, audit vẫn mở lại IFC.

## Giới hạn còn lại

- Ba assertion tam giác của harness legacy cũ đã thất bại tương đương trước/sau, được giữ riêng trong `.cache/inherited-legacy-failures.json`; chưa sửa trong đợt tổ chức mã. Exact parity không biến các assertion đó thành PASS.
- NOT_RUN cho nghiệm thu IFC/reference nghiên cứu riêng vì chưa có dữ liệu dự án. Thiếu dữ liệu phải giữ trạng thái chưa nghiệm thu; IFC công khai hoặc padding không thay thế dữ liệu này.
- Chưa đặt ngưỡng hiệu năng được phê duyệt. Số đo một máy, một lượt cold/warm chỉ là quan sát; không dùng để chứng nhận cải thiện RAM/tốc độ hoặc độ đúng hình học của mọi IFC.
- Import checks là phân tích AST và kiểm tra runtime exports/identity; không chứng minh mọi hành vi Python động hay SOLID tuyệt đối.
- Chưa bỏ facade, đổi framework, schema model, thuật toán geometry hoặc chuyển engine. Đây là những thay đổi cần phạm vi và bằng chứng riêng.
