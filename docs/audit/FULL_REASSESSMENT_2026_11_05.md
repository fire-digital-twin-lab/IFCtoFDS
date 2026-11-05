# IFCtoFDS — AUDIT TỔNG THỂ TRƯỚC KHI TIẾP TỤC MASTER PROMPT

**Ngày:** 05/11/2026 — **Bản audit:** A-20261105-R1  
**Repository:** [fire-digital-twin-lab/IFCtoFDS](https://github.com/fire-digital-twin-lab/IFCtoFDS)  
**Baseline được đọc:** `main@74ec6b7e84f7a9d6c9507ea45ae8f62344b0f7dd` (sau PR #51, trước PR #52).  
**Kết luận độc lập:** **NOT_PRODUCTION_READY; G09/G10 = INCONCLUSIVE**. Không có bằng chứng để cấp `SIMULATION_VERIFIED` hoặc chứng nhận tuân thủ thiết kế PCCC.

> Đây là audit tĩnh trên các tệp đã truy vấn bằng GitHub connector, cây repository đệ quy, hợp đồng và bộ test trọng yếu, cộng với CI GitHub trên SHA tương ứng. Không giả định đã clone/running toàn bộ IFC thật trên máy riêng; không coi GitHub CI PASS là kết quả kiểm định thực nghiệm. Những finding được phân loại CONFIRMED BY SOURCE, chưa được coi là exploit/run reproduced nếu chưa có fault-injection riêng.

## 1. Tóm tắt định lượng và trạng thái Git

- Git tree `main`: **662 entries**, trong đó **571 blobs**, gồm **259 tệp .py**, **70 tệp .js**, **128 tệp .md** và 75 module `tests/test_*.py`. Đếm tệp chứ không phải số test case.
- Hai workflow `main` ở baseline `74ec6b7e...` đều **SUCCESS**: [Conversion correctness #42033659752](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42033659752), [Source quality and regression evidence #42033659753](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42033659753). Branch protection đang bật, các required contexts gồm Python Ubuntu/Windows 3.10–3.12, JavaScript, browser và solver.
- PR #40–#51 đã merge theo lịch sử; [PR #52](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/52) đang Draft tại HEAD `798de1414d1a0ddc83bdcb3a61952563fce415d1`; **24 check success, 2 skipped** tại lần kiểm tra trong phiên, cần xem lại trạng thái trước merge. Không có GitHub Release đã phát hành.
- Code có CLI/HTTP/worker cho Python verified, browser JS workbench và worker bundles, independent validation, golden reference, SQLite job scheduling, evidence index, staging config fail-closed, single-host scheduler lock, offline backup/restore và bộ kiểm thử đa nền tảng.

## 2. Bản đồ kiến trúc đã kiểm tra

| Khối | Mã hiện tại | Đánh giá |
|---|---|---|
| Source/IFC | `core/inventory.py`, `core/federation.py`, `geometry/` | Có inventory, model nguồn, nguồn ghép nhiều file, transforms, source hashes; phạm vi thực nghiệm còn hạn chế |
| Mapping/FDS | `domain/mapping`, `mapping/exporter.py`, `mapping/manifest.py` | MappingPlan → serialization → manifest, có phân biệt vai trò nguồn và vật cản |
| Validation | `validation/engine.py` (711 dòng), `validation/runner.py`, `domain/validation/model.py`, `validation/golden/` | **Hai implementation cùng tồn tại**: engine hiện authoritative; modular runner chưa được chứng minh parity chi tiết toàn diện |
| Use cases | `application/use_cases/convert_verified.py`, `audit_conversion.py`, `application/services/` | Tách orchestration; audit đọc nguồn độc lập; golden gate được finalize cuối sau PR #51 |
| Job/infra | `adapters/jobs/{service,repository,runner,evidence_index,result_contract}.py`, `operations/offline_backup.py` | Durable transitions, SQLite WAL, evidence integrity và khóa scheduler một host; còn các failure window filesystem/SQLite |
| HTTP/UI | `server.py`, `js/app-controller.js`, `js/workbench/panels/ev-scenario-panel.js` | UI đã phân biệt verdict mapping/CFD; vẫn tồn tại đường JS quick/legacy cần đánh dấu rõ chưa nghiệm thu khoa học |
| CI/test | `.github/workflows/{verified,quality}.yml`, `tests/`, `scripts/test-*.js` | Linux/Windows Python matrix, solver pinned, browser/JS, quality budget, pytest coverage evidence; chưa phải staging E2E |

**Kiến trúc:** Modular Monolith + Hexagonal migration **đang chuyển tiếp**, không phải Hexagonal hoàn chỉnh. `docs/architecture/03-dependency-rules.md` và AST architecture tests đã bảo vệ Domain/Application import directions. `validation/engine.py` vẫn là thủ tục lớn, `js/app-controller.js` (~1.824 dòng), `js/ifc/ifc-adapter.js` (~2.049 dòng), `server.py` (~616 dòng), `adapters/jobs/service.py` (~780 dòng) còn độ phức tạp đáng kể. Không refactor mô hình khoa học mà không có parity proof.

## 3. Findings cần xử lý

| ID | Mức | Đã chứng minh bằng mã | Hậu quả / sửa cần thiết |
|---|---|---|---|
| **SCI-BASE-01** | **P1** | `application/services/scenario_base.py::load_verified_base` đọc manifest/report/FDS/package nhưng **không gọi `verify_evidence_index`** cho bộ artifact nền. Trong khi `adapters/jobs/repository.py::read_result` bắt buộc xác minh index và cross-file consistency. | Một report đã thay đổi nội dung nhưng còn hợp lệ về JSON và verdict có thể vượt qua kiểm tra base trực tiếp, trong khi published evidence index không còn khớp. Thêm result-contract + complete evidence-index + sealed audit checkpoint check trước khi phát hành scenario; regression giả mạo report, artifact thiếu/index thiếu, good base. **Chưa tái hiện trực tiếp trong CI tại checkpoint.** |
| **IO-RETENTION-01** | **P1** | `JobService.touch()` commit `last_accessed` vào SQLite; nhưng `cleanup_orphaned_directories()` dòng ~214 dùng **`entry.stat().st_mtime`** để quyết định xóa registered job khi boot. `touch` không cập nhật mtime thư mục. | Restart có thể xóa artifact mới được truy cập vì dùng clock filesystem cũ thay vì timestamp DB. Sửa startup sweep theo `max(finished,last_accessed)`, giữ điều kiện `durable`, chỉ delete row trước khi xóa file; regression restart + clock cũ và mới. |
| **SCI-REAL-01** | **P1 / release blocker** | `reference-cases/basement-b1-b2/approval.json` có `status=DRAFT`, reviewer/rationale rỗng; `docs/golden-remediation-status.md` ghi IFC nguồn thực ở ngoài repo, có hash nhưng chưa nghiệm thu. | Chưa đủ căn cứ độc lập cho G09/G10, golden basement và fire design. Không tự nâng DRAFT/INCONCLUSIVE. Cần IFC thực với quyền, approval người có trách nhiệm, source inventory/openings/MEP, FDS V&V. |
| **SCI-PARITY-01** | **P1 / blocker nếu thay engine** | `validation/engine.py` và `validation/runner.py` đều triển khai gate; `tests/test_validation_engine_parity.py` có mẫu đặc trưng nhưng không phủ toàn bộ reports/evidence. `docs/architecture/14-r10-04-audit-validation-parity.md` xác nhận chưa đủ strict parity. | Không thay engine authoritative hoặc tự nâng verdict từ modular runner; bổ sung strict `compare_details=True` với IFC thực và mutation corpora, kiểm tra findings/metrics/payload. |
| **SCI-EV-01** | **P1 / independent science** | `fire/physics_assessment.py` phân biệt energy budget PASS với `physics.status=INCONCLUSIVE` (nếu không FAIL); `runner.py` đặt `simulation_status=NOT_RUN`. `validation/solver.py` chủ yếu xác minh solver initialization/effective geometry. | Không có independent CFD validation, convergence, sensitivity, thực nghiệm, HF/source chemistry. CI PASS **không** cho phép `SIMULATION_VERIFIED`. Đây là **khoảng trống bằng chứng**, không khẳng định thuật toán hiện tại cho kết quả sai. |
| **SEC-DEPLOY-01** | **P1 release blocker** | `deployment_config.py` bắt buộc API key/Host allowlist cho staging/production, `server.py` kiểm tra API key chung, Host/Origin và giới hạn upload; nhưng chưa có per-user role/authorization, isolation worker, TLS/rate-limiter thực nghiệm và threat-model production. | Khả năng chạy trên internet với dữ liệu nhạy cảm chưa nghiệm thu. API key chung không thay thế phân quyền job/tenant; triển khai cần reverse proxy TLS, sandbox/ulimits, threat model, vulnerability scanning, test negative và secret rotation. |
| **OPS-STAGING-01** | **P1 release blocker** | Trong cây `main` không thấy `Dockerfile`, Compose, Helm, Terraform hay thư mục k8s; không có GitHub Release. | Không có pipeline triển khai/rollback staging đã được repo tự chứng minh. Phải định nghĩa vận hành single-host, immutable artifact, restart, health, secrets, disk quota và rollback trước G11/G13/G15. |
| **OPS-DR-01** | **P1 release blocker** | `operations/offline_backup.py` có snapshot/manifest v2 SHA-256 và restore thư mục mới, nhưng yêu cầu dừng toàn bộ API/worker. Unit tests đã có, **chưa có staging DR drill/RPO-RTO**. | Chưa đóng G12. Thiết kế offsite/encryption/retention, diễn tập checksum/restoration trên dữ liệu đại diện và so sánh evidence. |
| **OPS-DOWNLOAD-01** | **P2 / test gap** | `server.py` kiểm tra `touch()` trước `FileResponse`/StreamingResponse; scheduler retention có thể xóa artifact sau đó ở luồng khác; `touch` không pin file descriptor. | Cần race/stress test download song song sweep/delete và retry boundary; không khẳng định có lỗi hiện hữu nếu chưa tái hiện. |
| **CI-REPRO-01** | **P2** | `pyproject.toml` cho dependency ranges; CI dùng `pip install -e ".[test]"` không sử dụng `uv.lock`; actions chủ yếu ghim tag `@v4/@v5`, quality chỉ ruff một phần mã và coverage report **không có minimum gate**. | CI chưa fully reproducible/supply-chain-hardened. Cần lockfile installation, action SHA pinning, SBOM/dependency scanning, chuẩn coverage có baseline, full lint theo phạm vi đã duyệt. |
| **DOC-TRUTH-01** | **P2** | `docs/AUDIT_GATE_STATUS.md` ghi Gate Result **PASS** cho một audit milestone lịch sử; `docs/risk-register.md` vẫn để trạng thái “In Progress Phase 1–6”; `docs/audit/PRODUCTION_READINESS_2026_11_05.md` chứa PR #38/#41 ở trạng thái OPEN lịch sử. | Người đọc có thể nhầm audit PASS với production ready. Thống nhất `PRODUCTION_ACCEPTANCE_MASTER_TRACKER.md` + snapshot mới có ngày/SHA; đóng/đánh dấu historical các bảng cũ, không xóa forensic logs. |

### Những thứ **đã có** — không mở finding trùng

- `AcceptanceReport.finalize` đã ràng buộc 12 mapping gates và các gate cốt lõi không được miễn; không phát hành `SIMULATION_VERIFIED` từ mapping. PR #49 đã merge.
- PR #50 đã sửa giao diện phân biệt `MAPPING_VERIFIED` với CFD và không chuyển lỗi HTTP/timeout thành `REJECTED` khoa học.
- PR #51 đã chuyển `research_context` sau `finalize` cuối. PR #52 (Draft tại checkpoint) mở rộng kiểm tra nested research/parity claims trong public result; CI phải được đối chiếu HEAD rồi mới merge.
- `scenario_base.py` **đã** kiểm tra SHA FDS/manifest và geometry package; finding SCI-BASE-01 **chỉ** về bước thiếu cross-file evidence-index/sealed-result verification, không phủ nhận các check đã có.
- `JobService` đã có durable admission, terminal, timeout, cancel, spawn, retention touch; khóa process trong staging/production. Không đánh dấu lại các regression được bảo vệ thành lỗi chưa sửa.
- `validation/engine.py` có `StructuralCompletenessChecker` và `AirPathTopologyChecker`. Không có bằng chứng để kết luận hai gate này luôn PASS giả.

## 4. Scientific acceptance — ma trận ý nghĩa

| Claim | Bằng chứng hiện có | Quyết định |
|---|---|---|
| IFC source provenance | Source IDs/hashes, independent reread, geometry package và mapping manifest trong pipeline; reference basement thực chưa được approve | `INCONCLUSIVE` ở real-building scope |
| Mapping trong tập fixture được kiểm thử | 12 required gates, parser, traceability, openings/MEP/source integrity, regression mutations và golden governance | Có thể `MAPPING_VERIFIED` **chỉ theo scope, model và evidence cụ thể** |
| Reference basement B1/B2 | `approval.json=DRAFT`; IFC nguồn thực không được phát hành như approved golden | **NOT_APPROVED** |
| Solver input/initialization | Windows CI cài pinned FDS 6.11.1 và chạy `pytest -m solver` | Đúng mức **solver readiness/fixture**, không chứng minh CFD physical validation |
| Physics EV | HRR energy budget plausibility; `HF=NOT_MODELED`; `simulation_status=NOT_RUN` | **INCONCLUSIVE / NOT_RUN** |
| Safety/design claim | Chưa có measured baseline, uncertainty, mesh convergence, fan/door/sprinkler validated physics hay sign-off | **Không phát hành SIMULATION_VERIFIED** |

## 5. Ma trận 16 production gates (tại baseline)

| Gate | Verdict | Điều kiện thiếu tối thiểu |
|---|---|---|
| G01 Git & integration | IN_PROGRESS | PR #52 và finding P1 mới cần được xử lý qua CI |
| G02 Release candidate | NOT_RUN | Chưa có release/tag, candidate SHA và sign-off |
| G03 Architecture | INCONCLUSIVE | Migration Hexagonal transitional; strict parity đầy đủ chưa có |
| G04 QA | IN_PROGRESS | CI PASS trên main; thiếu staging E2E negative tests ở dữ liệu thực |
| G05 Durability | IN_PROGRESS | Retention restart, crash/OS failure and durable file semantics |
| G06 Concurrency | INCONCLUSIVE | Local file lock có; chưa chứng minh multi-process/distributed/stream download |
| G07 Security | IN_PROGRESS | Baseline fail-closed có; thiếu deployment threat model và end-to-end security evidence |
| G08 Performance | NOT_RUN | Cold/warm cùng IFC thực, peak RSS, throughput |
| G09 IFC scientific mapping | INCONCLUSIVE | Golden real IFC được duyệt và source-vs-FDS V&V độc lập |
| G10 FDS/CFD | INCONCLUSIVE | Validated physics/solver convergence/experimental references |
| G11 Staging | NOT_RUN | Staging environment, HTTPS, secrets, E2E deployment |
| G12 Backup/restore | NOT_RUN | DR drill và RPO/RTO/restore hash/runtime trên staging |
| G13 Rollback | NOT_RUN | Rollback rehearsal + schema/data compatibility |
| G14 Observability | IN_PROGRESS | Scheduler endpoint có; thiếu metrics, alerting, drill |
| G15 Production | NOT_RUN | Chưa được phép triển khai hoặc có smoke/soak |
| G16 Documentation/sign-off | IN_PROGRESS | Cần chuẩn hóa current vs historical, evidence và independent approvals |

## 6. Quy trình master prompt tiếp theo, không vượt gate

**Vòng A — P1 đúng đắn dữ liệu (trước deploy):**
1. Xác minh/merge #52 chỉ khi 24 success/2 skipped và cả workflow thực sự kết thúc SUCCESS trên HEAD.
2. Sửa SCI-BASE-01 ở scenario foundation: dùng persisted result contract, evidence index và sealed audit; test altered report/index, missing evidence, valid accepted source.
3. Sửa IO-RETENTION-01 ở startup cleanup dùng SQLite last_accessed; test restart sau download, short retention, durable/excluded rows.
4. Thêm negative tests API/worker cho filename, link, concurrent deletion và status.

**Vòng B — Scientific V&V:**
1. Tạo source evidence register IFC theo quyền sở hữu: phiên bản/hash, hệ đơn vị, tọa độ, storey, openings, MEP, approved scope.
2. Tái hiện các finding lịch sử C-3b, H-3, H-4/H-5, N-1, H-10, M-15 bằng fixture source/solver có kiểm chứng; không tự cấp verdict khi thiếu source.
3. Strict parity `ValidationRunner` với authoritative engine ở detailed evidence và exception/fault paths.
4. Thiết lập pin solver binary/hash, FDS boundary case, mesh convergence, independent references và uncertainty report; có người đánh giá chuyên môn.

**Vòng C — Staging/Production:**
1. Threat model, TLS, API authZ/sandbox, quotas/secrets, dependency/SBOM.
2. Immutable release image + signed provenance + deployment runbook, staging CI/E2E.
3. Offline backup/restore drill, chaos/fault injection, rollback rehearsal, metrics/alerts, performance benchmark.
4. Chỉ đóng từng gate có môi trường, timestamp, exact SHA, test logs, artifacts, owner và approval; release verdict mặc định **NOT_PRODUCTION_READY**.

## 7. Audit evidence provenance / giới hạn

Truy vấn hiện hành đã xem toàn bộ **danh sách tệp** của repo (không bị truncated), các tệp code critical path, workflows, test modules trọng yếu, ADR/architecture, reference DRAFT và audit lịch sử. Đây **không phải** xác nhận đã đọc chi tiết từng dòng của tất cả 571 blobs, chạy toàn bộ E2E trên máy thật, hay chứng minh tất cả dữ liệu IFC. Mọi kết luận về tính đúng thực nghiệm đều phải được xác minh độc lập; P0/P1 chỉ được đóng bằng regression hoặc accepted evidence cụ thể. Các chứng cứ công bố phải có hash, SHA và review thực tế, không dùng fixtures tự sinh làm empirical validation.

**Chốt:** `NOT_PRODUCTION_READY`. Không điều chỉnh tolerance, không tạo artificial golden evidence, không đổi branch protection và không triển khai production khi chưa đáp ứng các gate liên quan.
