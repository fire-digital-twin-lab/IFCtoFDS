# IFCtoFDS — Tái kiểm toán mã nguồn và kế hoạch remediation theo Master Prompt (10/11/2026)

**Baseline kiểm chứng:** `main@77f047f392fc4ac7fc3d4414df4cbc9087151ebb`.  
**Repository:** `fire-digital-twin-lab/IFCtoFDS`.  
**Loại tài liệu:** audit + work-package plan (không phải sign-off, không thay đổi claim ledger).  
**Baseline CI trên chính SHA:** Source Quality #42660170454, Conversion #42660170338, Container #42660170349 và Release Image Security #42660170520 — đều **SUCCESS**.  
**Open PR tại baseline:** #82 tracker, #83 production remediation plan, #91 CVE triage. PR #92 là work package P4-NUM-001 khởi tạo trong vòng audit này, **chưa được ghi là merged/PASS**.  
**Science overall:** `INCONCLUSIVE`; **Release:** `NOT_PRODUCTION_READY`.

## 1. Phạm vi kiểm tra và nguồn dữ liệu

Đối chiếu:
- Master Prompt *Continuous Scientific Engineering, V&V, Remediation & Evidence Loop* do chủ dự án cung cấp;
- báo cáo nghiên cứu *Báo cáo Phân tích Kỹ thuật & Kiến trúc Mở rộng IFCtoFDS cho kịch bản cháy xe điện* (baseline 07/11, mô tả tình trạng tại commit cũ `dbc37cd`);
- `docs/adr/ADR-001`, `002`, `003`, `004`, `008`;
- `docs/science/SCIENTIFIC_CLAIMS.md`, `docs/audit/PRODUCTION_ACCEPTANCE_MASTER_TRACKER.md`;
- `ifc_to_fds/fire/grid_sensitivity_*.py`, `vehicle_geometry.py`, `vehicle_collision.py`, `scenario_emitter.py`;
- `ifc_to_fds/adapters/jobs/repository.py`, `service.py`, `ifc_to_fds/validation/parser.py`;
- `reference-cases/basement-b1-b2/approval.json`, `acceptance-profile.json`;
- `Dockerfile`, `compose.production.yml`, security/quality/conversion/container workflows, các runbook.

Repository hiện có 759 Git tree entries tại baseline (666 file blobs, còn lại là thư mục). **Giới hạn kiểm toán:** đây là đối soát cấu trúc và trọng điểm correctness; **chưa** có bằng chứng đọc từng dòng toàn bộ 666 file, chạy local solver hoặc staging. Báo cáo 07/11 phải dùng như finding lịch sử: không tái khai báo các lỗi P1/P3 đã sửa bằng PR mới nếu chưa chạy regression xác nhận trạng thái hiện hành.

Kiến trúc tuân theo ADR đã duyệt: Modular Monolith + Hexagonal, Python Verified Core là scientific source of truth; JS là Quick/Legacy/Preview. Không tạo nhánh tính toán vật lý song song trong JS.

## 2. Ma trận claim và cổng khoa học

| Claim/gate | Trạng thái được ghi nhận | Không được suy luận |
|---|---|---|
| `FDS-PARSER-001` | PASS/E2, FDS 6.11.1 supported subset | Không phải full FDS parser hoặc CFD validation |
| `SOLVER-REG-001` | PASS/E2, pinned integration fixtures | Không phải solution verification E3 |
| `MESH-SENS-P4C2A-001` | PASS/E2 trong executed 3-case minimal DEVC provenance | Không chứng minh application grid independence |
| `MESH-LOCAL-001` | INCONCLUSIVE (broad) | Không được gán PASS từ D*/dx hoặc 0.1s DEVC |
| `MATL-THERM-001` | INCONCLUSIVE/E0 | Không tự bịa MATL/SURF dữ liệu |
| `EV-PHYS-001` | INCONCLUSIVE/E1 | Không gán HF/CO/soot yield thành vật lý được validation |
| `DET-SUP-001` | INCONCLUSIVE/E0 | Không coi parser chấp nhận PROP/DEVC là sprinkler model validation |
| `ASET-001` | INCONCLUSIVE/E0 | Không hardcode ngưỡng tenability |
| `B1B2-APP-001` | INCONCLUSIVE/E1 | Không coi DRAFT reference là golden |
| Overall EV-fire application | INCONCLUSIVE | Không cấp SIMULATION_VERIFIED |

Theo tracker, `EV-GEO-001=FAIL` vẫn là unresolved broad issue; các P3 partial software gates/vehicle geometry hiện đã được thêm trong mã, nên phải tái đánh giá issue theo scope cũ và mới trước khi chỉnh logic.

## 3. Findings đã xác minh từ mã (không phải phỏng đoán physics)

### F-P4-NUM-001 — Product underflow làm sai loại xu hướng grid

- **File:** `ifc_to_fds/fire/grid_sensitivity_analysis.py::_trend`.
- **Root cause:** dùng `(medium-coarse) * (fine-medium)` để phân loại dấu; hai delta khác zero nhưng tích dưới ngưỡng biểu diễn `binary64` thành ±0.0.
- **Reproducer:** dãy `0 → 1e-200 → 2e-200` trả `PLATEAU_OR_UNRESOLVED` mặc dù MONOTONIC; `0 → 2e-200 → 1e-200` trả false plateau mặc dù OSCILLATORY.
- **Impact:** phát biểu mô tả về `GridSensitivityStudyEvidence.metrics[].trend` có thể sai; scale/unit invariance bị phá. Không thay đổi convergence verdict (`INCONCLUSIVE`).
- **Action:** PR #92, tách riêng; sửa so sánh dấu, reject non-finite derived metrics, targeted/negative/metamorphic regression. **Target level E2**, pending CI cuối + review.

### F-P4-WINDOW-002 — Phạm vi ý nghĩa FINAL tại cửa sổ không trùng mốc CSV cần đặc tả

- **File:** `ifc_to_fds/fire/grid_sensitivity_observables.py::_aggregate`.
- **Evidence code:** nếu time window `(start, stop)` được bao phủ bởi first/last timestamps, hàm chỉ lấy *các sample nằm bên trong*; `FINAL` trả sample cuối còn lại, có thể **trước `stop`** nếu stop nằm giữa hai timestamps.
- **Risk:** kết quả được gắn `time_window_s` có thể làm người dùng hiểu là giá trị tại `stop`, trong khi code dùng last included sample. Không kết luận ngay đây là lỗi nếu contract định nghĩa FINAL là last sampled value.
- **Action:** trước sửa phải khóa policy: `FINAL_AT_SAMPLE` hay nội suy có loại interpolation được duyệt; với MAX/MIN không thể mặc định nội suy nắm hết peak. Thêm negative tests `stop` nằm giữa timestamps, empty interior, duplicates và unit/aggregation provenance. **Không tự nội suy physics**; nếu chưa có policy, fail closed.

### F-P4C2B-003 — Không đủ external reference cho application study

- **Files:** `grid_sensitivity_application.py`, `reference-cases/basement-b1-b2/*`.
- **Evidence:** approval status DRAFT, schema `0.4.0` so current `0.5.0`, `simulation_domain=null`, mapping acceptance `INCONCLUSIVE`, output incomplete; external IFC/source hashes chưa xác nhận theo readiness contract.
- **Action:** giữ `NOT_READY`, chờ approved geometry/model domain, source SHA, accepted mapping, solver-input/experimental observables và independent review. **External blocker; không code để giả lập approval**.
- **Required evidence:** E3 cho numerical solution verification; E4/E5 cho experimental/application validation; E6 nếu tuyên bố independent replication.

### F-OPS-004 — Software CI vẫn chưa tương đương staging/production acceptance

- **Files:** `compose.production.yml`, `docs/operations/BACKUP_RESTORE_RUNBOOK.md`, `MONITORING_RUNBOOK.md`, acceptance tracker.
- **Evidence:** R1–R4 đã có CI cho HTTPS/Host/API key, jobs/backup/restore/IFC E2E; nhưng G11 staging, G12 DR rehearsal, G13 rollback, G14 live alert, G15 production sign-off chưa có evidence.
- **Action:** chạy staging trong môi trường được cấp, backup offline trên named volume mới, đo RPO/RTO, rollback image digest, alert drills; không chạy thao tác destructive trên dữ liệu production.

### F-SEC-005 — Chưa đóng security release gate

- **Evidence:** PR #90 vá CVE apt/zlib; Trivy image còn **47 HIGH findings / 11 unique CVE IDs** ở lần quét PR; `Release image security evidence` normal workflow là EVIDENCE_ONLY, không strict HIGH/CRITICAL enforcement.
- **Action:** hoàn tất PR #91 và human review CVE (owner, impact, mitigation, expiry), chốt strict policy, build-once GHCR promotion bằng OCI digest/attestation và branch/environment protection. Không tự waiver hay giảm severity.

## 4. Kế hoạch triển khai theo dependency, một work package/PR

| Thứ tự | WP / phase | Implement/test cụ thể | Gate và stop condition |
|---|---|---|---|
| 1 | **P4-NUM-001** (PR #92) | `grid_sensitivity_analysis.py`, `tests/test_grid_sensitivity.py`; sign oracle/scale metamorphic/overflow | 4 workflow success final HEAD; scoped software E2, science broad unchanged |
| 2 | **P4-WINDOW-002** | Khóa nghĩa `FINAL` tại off-grid time, gap policy, provenance; unit/boundary/metamorphic + fake solver integration | Không tự nội suy/chỉnh thời gian nếu chưa có review contract |
| 3 | **P0/P1 acceptance sync** | Nghiệm thu #82, #83, #91; reconcile tracker, triage ledger và open findings; test CI release SHA | Không merge pending/failed; không sửa historical evidence để làm xanh |
| 4 | **P3 EV geometry closure** | Kiểm tra `EV-GEO-001` so với body/clearance/battery/IFC_BOUND/parametric/collision; reference geometry regression | Chỉ PASS theo domain + E2; thiếu real IFC thì broad INCONCLUSIVE/FAIL tùy finding |
| 5 | **P4c2b application study** | COARSE/MEDIUM/FINE cùng physics, aligned DEVC, independent measured output/uncertainty, FDS 6.11.1 hashes | BLOCKED đến khi reference & external experiment hợp lệ; không cherry-pick |
| 6 | **P2/P5 material mapping** | IFC material layer semantics, unit/temperature dependence/provenance, FDS MATL/SURF parser + pinned solver | Data absent => INCONCLUSIVE; không tạo default physical constants |
| 7 | **P6/P7/P8** EV physics, detector/sprinkler, HVAC smoke control | Separate PR per model; references DEVC→PROP→PART, HRR/species/fan-flow source ledger; solver integration | Kiểm chứng conservation/units + pin FDS, không self-certification |
| 8 | **P9/P10/P11/P12** instrumentation/tenability, uncertainty, experimental/independent V&V, B1/B2 final | Metrics, first crossing, documented criteria, datasets uncertainties and E4–E6 review | Chỉ kết luận model/application khi approved independent evidence |
| song song | **R5/R6 operational** | CVE remediation, strict security release, GHCR immutable digest, staging TLS/E2E, DR, rollback, alert/load | G07/G11–G15 chỉ PASS khi có host log/artifacts + operator approval |

**Quy tắc:** priority theo Master Prompt: scientific correctness → data corruption → geometry → solver → regression → architecture debt → performance → UI. Các work package dùng Python Verified Core, không tự sửa khoa học qua JS legacy. Giai đoạn sau chỉ được bắt đầu khi dependency đã đủ hoặc độc lập rõ ràng.

## 5. Template vòng lặp bắt buộc áp dụng cho mỗi WP

1. **SYNC:** ghi exact `CURRENT_MAIN_SHA`, PR HEAD, tracked modified files, branch protection, four CI conclusions, research claim status.
2. **ISSUE:** Finding, root cause, input→model→transform→output→consumer, claim/evidence level, scope/non-goals, review policy và failure/risk.
3. **TEST FIRST:** positive, negative, boundary, metamorphic, oracle (analytical/independent implementation/solver), provenance snapshot. Nếu thiếu oracle thì ghi `INCONCLUSIVE`.
4. **IMPLEMENT:** SOLID, typed data, deterministic output, explicit SI units; không im lặng fallback/epsilon/tolerance; comment/docstrings tiếng Việt cho code mới.
5. **VERIFY:** targeted pytest, Ruff/typing, full Python, JS regression, existing golden, pinned solver CI khi phù hợp. So sánh exact source hashes và report before/after.
6. **AUDIT:** diff không lẫn unrelated changes, không chứa secrets hoặc generated output, không chỉnh thresholds/golden; review scientific impact.
7. **PR:** commit/PR tiếng Việt; đầy đủ Problem/Root Cause/Scope/Implementation/Tests/Scientific Impact/Evidence/Limitations/Verdict/Rollback.
8. **MERGE:** chỉ khi final HEAD mọi required checks SUCCESS, review phù hợp; không bypass branch protection. Verify workflow sau merge trên chính main SHA.
9. **LEDGER:** cập nhật claim/evidence/tracker sau bằng chứng, không thay PASS scoped thành application PASS.
10. **REPEAT:** chọn WP cao nhất tiếp theo hoặc báo blocker có chứng cứ.

## 5.1. Checkpoint sau PR #91 — 10/11/2026

- PR #91 đã được merge bằng squash vào `main@50a40d0b351eaedaea26cf2aaf00287577079ed0` sau khi đủ bốn workflow PASS trên PR HEAD. `cve-triage.json` được sản xuất từ scanner, nhưng `UNREVIEWED/NO_GO` không được nâng thành release approval.
- PR #92 triển khai P4-NUM-001 và có T1 code review + reproduction độc lập; không đánh dấu E2/PASS đến khi toàn bộ CI trên cuối HEAD hoàn tất.
- PR #82/#83 và planning PR #93 còn là tài liệu cần nghiệm thu; không được dùng trạng thái trước merge của một SHA cũ như PASS cho HEAD mới.
- Mọi staging/DR/rollback và B1/B2 external scientific approval tiếp tục không đủ evidence.

## 6. No-go và nguồn tham khảo

- `SIMULATION_VERIFIED` không cấp vì P4c2b/B1B2/reference, thermal/EV physics và uncertainty E3–E6 chưa đủ.
- G07/production security không PASS khi strict CVE risk acceptance và immutable release chưa đóng.
- G11–G15 không PASS nếu chưa có staging execution, DR/rollback drills và monitoring alert evidence.
- Không bịa EV HRR/CO/HF/sprinkler/fan/ASET thresholds; yêu cầu provenance theo ISO 16739 / ISO 16730 / ISO 23932, ASTM E1355, ASME V&V 20 và NIST FDS official manuals khi các PR tương ứng bắt đầu.
- **File tham chiếu:** `docs/science/P4C2A_EXECUTED_GRID_STUDY_CONTRACT.md`, `docs/adr/ADR-003-python-verified-core-is-authoritative.md`, `docs/adr/ADR-008-real-building-acceptance-protocol.md`, `docs/science/SCIENTIFIC_CLAIMS.md`.

**Kết luận:** có thể tiếp tục remediation có chứng cứ; **không** có đủ điều kiện để nâng overall scientific verdict hoặc công bố production-ready.
