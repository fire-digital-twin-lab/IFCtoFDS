# IFCtoFDS — Sổ theo dõi nghiệm thu production

## Checkpoint kỹ thuật cập nhật — 05/11/2026 (sau tích hợp PR #55)

> **Nguồn dữ liệu:** GitHub API: nhánh chính, chi tiết PR, workflow runs và check-runs; kiểm toán static source. **Không phải** staging evidence, production evidence hoặc scientific V&V. Các mục phía dưới tiêu đề "snapshot lịch sử" giữ nguyên để truy vết, không được dùng như trạng thái hiện tại.

### GitHub baseline và vòng đang mở

- **main HEAD đã đối chiếu:** `283daef1b010bdd41e6548048090c3e17a97163d` (merge [PR #55](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/55), startup retention theo SQLite).
- **CI main HEAD:** [Conversion correctness #42062713877](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42062713877) = SUCCESS và [Source quality #42062713934](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42062713934) = SUCCESS.
- **PR #38, #39, #40** đã merge; **PR #41–#54 và #56** đã merge. Các SHA/công việc này chỉ đại diện cho regression scope, không đóng toàn bộ JobService/security/science.
- **[PR #57](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/57)**: sửa lỗi cleanup làm scheduler chết sau khi SQLite commit; HEAD `ef9604b80324b340b007c3b987c2f85e8c0e056b` sau bổ sung kiểm thử lỗi `glob()`. **IN_PROGRESS**, phải xác minh toàn bộ required checks trên HEAD rồi merge thường.
- **[PR #58](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/58)**: tránh trả lỗi 500 khi hủy đã commit nhưng ghi diagnostic thất bại; **DRAFT / FIXED_PENDING_VERIFICATION**, đang phụ thuộc #57. Đối chiếu HEAD và CI mới nhất trước khi review/merge.
- **CI-DUPLICATE-SHA-01** (P2, OPEN): từng gặp GitHub merge HTTP 405 `9 of 9 required status checks are cancelled` cho #57 HEAD `d5418165` dù workflow PR đã SUCCESS. Một nhánh phụ thuộc từng push cùng commit SHA và có check-runs bị hủy; **chưa kết luận nguyên nhân gốc**. Đã tạo HEAD mới có regression thật, không tắt checks hay bypass protection. GitHub Issues của repository bị tắt (API 410), do đó lưu finding tại tracker này.

### Ma trận 16 gate theo bằng chứng hiện hữu

| Gate | Trạng thái | Căn cứ hoặc thiếu sót |
|---|---|---|
| G01 Git integration | IN_PROGRESS | #55 merged; #57/#58 đang chờ CI/merge |
| G02 Required CI trên release SHA | NOT_RUN | main #55 PASS nhưng chưa có release candidate được nghiệm thu |
| G03 Architecture | INCONCLUSIVE | Application/Interfaces transitional; chưa có strict full parity |
| G04 Functional QA | IN_PROGRESS | Regression CI đa hệ điều hành, thiếu staging E2E |
| G05 Job persistence | IN_PROGRESS | SQLite WAL FULL và durable transitions có; crash-window/diagnostic/retention còn mở |
| G06 Concurrency | INCONCLUSIVE | Một scheduler production bị khóa; chưa có full race/fault tests và stream-download safety |
| G07 Security | IN_PROGRESS | Fail-closed network config có, thiếu deployment threat-model/tenant auth/TLS evidence |
| G08 Performance | NOT_RUN | Chưa đo lại FZK-Haus và benchmark cold/warm cùng hardware |
| G09 IFC geometry | INCONCLUSIVE | Basement approval DRAFT, golden công trình thực chưa được reviewer duyệt |
| G10 FDS integration / CFD V&V | INCONCLUSIVE | Solver fixture PASS không phải independent physics/convergence V&V |
| G11 Staging | NOT_RUN | Chưa có môi trường và báo cáo E2E staging |
| G12 Backup/restore | NOT_RUN | Script backup tồn tại, chưa có staged DR drill xác minh |
| G13 Rollback | NOT_RUN | Chưa có rehearsal/khả năng rollback dữ liệu đã nghiệm thu |
| G14 Observability | IN_PROGRESS | Scheduler readiness có, thiếu metrics/alert/drill đầy đủ |
| G15 Production | NOT_RUN | Chưa deploy và không có production smoke/soak |
| G16 Documentation | IN_PROGRESS | Tracker và audit có, chưa đủ release notes/evidence/sign-off |

**Scientific semantics:** `COMPLETED` không đồng nghĩa `MAPPING_VERIFIED`; `MAPPING_VERIFIED` không đồng nghĩa `SIMULATION_VERIFIED`. `reference-cases/basement-b1-b2/approval.json` còn `DRAFT`, reviewer/evidence rỗng. Không có GitHub Release đã công bố khi đối chiếu.

**Security/license:** `LICENSE` và `pyproject.toml` ghi `AGPL-3.0-or-later`. Trước khi vận hành bản sửa đổi qua mạng phải rà soát nghĩa vụ cung cấp mã nguồn tương ứng, cùng với giấy phép của dependencies.

**Release verdict: NOT_PRODUCTION_READY.** Không thay đổi bằng CI PASS hay tạo tài liệu.

### Hành động an toàn kế tiếp

1. Kiểm tra PR #57 trên HEAD mới, không merge khi required checks còn cancelled/pending; sau merge phải kiểm tra CI main.
2. Đồng bộ PR #58 với main, mở review, chạy lại CI trên HEAD hợp nhất, merge khi branch protection cho phép.
3. Xác minh fault-injection `_terminal_diagnostic()` ở scheduler, SQLite/filesystem crash windows và race download/retention.
4. Bổ sung golden IFC có bản quyền, SHA-256 và phê duyệt người có chuyên môn; FDS/PyroSim V&V độc lập.
5. Chuẩn bị security, benchmark, staging, DR/rollback và release gates; không dùng hạ tầng production khi chưa được cấp phép.

---

## Các checkpoint lịch sử (chỉ để truy vết)



## Snapshot hiện hành bổ sung — 05/11/2026

**Main đã xác minh:** `e6b7ef04296d660d0713a79e813a1207dfa5cc84` (merge #39). CI trên merge SHA mới **chưa kết luận** khi ghi snapshot này. `main` cũ `d04771db` đã PASS hai workflow.

- **PR #40:** MERGED `d04771db` (CI concurrency).
- **PR #39:** MERGED `e6b7ef0` (worker terminal persistence; chỉ đường kết thúc worker đã bảo vệ commit-first).
- **PR #38:** OPEN; cập nhật bảng và đồng bộ `main`; yêu cầu CI HEAD sau đồng bộ trước merge.
- **PR #41:** DRAFT, HEAD `8eb33eb483408377ed0ba3458a51dca07d706a30`; test/CI trên head cũ PASS. Chưa retarget `main` và nghiệm thu lại.
- **Trạng thái các gate:** G01 IN_PROGRESS; G02 NOT_RUN cho release SHA; G05 FAIL; G06 INCONCLUSIVE; G09/G10 INCONCLUSIVE; G11–G13/G15 NOT_RUN. Không đổi kết luận khoa học hoặc production.

**Chú ý:** các mục “PR #39 OPEN” và “main `d04771db`” bên dưới là snapshot tại thời điểm tạo tracker, không phải trạng thái mới nhất. Sau khi PR #38 và #41 merge, tiếp tục bổ sung checkpoint thực tế.


> **Checkpoint kiểm tra GitHub: 05/11/2026 (phiên nghiệm thu đang thực hiện).**
> Mọi SHA/run/status dưới đây là ảnh chụp tại thời điểm ghi, không thay thế truy vấn GitHub mới nhất trước khi merge hoặc release.
> **Release verdict: NOT_PRODUCTION_READY.** Chưa có staging, production smoke, V&V khoa học độc lập hay diễn tập backup/restore/rollback được nghiệm thu trong phiên này.

## 1. Git, phụ thuộc và CI

| Mục | Giá trị / bằng chứng | Kết luận |
|---|---|---|
| `main` lúc tạo tracker | `d04771db4f9f584b98a1bab1d9d03a028cd769ab` | PR #40 đã merge |
| PR #40 | [#40](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/40), merge `d04771db` | MERGED; sửa concurrency giữa push và pull_request |
| CI `main` tại `d04771db` | [Conversion #41979799490](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/41979799490), [Quality #41979799570](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/41979799570) | 2 workflows SUCCESS; không phải CI của release candidate |
| PR #39 | [#39](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/39), HEAD `39caa95749467b11eaff4060bc403c58cdb6f6db` | OPEN; đã đồng bộ #40; PR CI SUCCESS ở các run #41980077859 và #41980077747; cần xác minh required checks sau rerun push #41980652295 |
| PR #38 | [#38](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/38), HEAD cũ `01f2e1fe` trước chỉnh tài liệu | OPEN; ma trận cần đồng bộ trạng thái mới và main |
| PR #41 | [#41](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/41), HEAD `494c75825e3d1c198bc91de7bba6bb1f38178d5f` | DRAFT; phụ thuộc #39; kiểm thử đang chạy |
| Branch protection | `main` protected; 8 required check contexts theo API branch | Không bypass |

**Thứ tự phụ thuộc:** #40 (đã merge) → #39 (terminal) → #38 (ma trận cập nhật) → #41 (startup/queue recovery, sau khi đổi base sang main). Việc đổi thứ tự chỉ được thực hiện sau đối chiếu CI và merge history.

## 2. Ma trận 16 gate

Trạng thái chỉ được nâng khi có bằng chứng đúng SHA, đúng môi trường và đúng phạm vi.

| Gate | Trạng thái | Evidence / blocker còn thiếu |
|---|---|---|
| G01 Git integration | IN_PROGRESS | #39, #38, #41 chưa tích hợp |
| G02 CI release SHA | NOT_RUN | `main` có CI PASS nhưng chưa chọn release candidate |
| G03 Architecture | INCONCLUSIVE | Cần dependency/contract tests toàn module và đánh giá lại finding kiến trúc |
| G04 Functional QA | IN_PROGRESS | PR regression đang chạy; chưa có E2E staging hoàn chỉnh |
| G05 Job persistence | FAIL | Queue/startup/RSS/spawn, power loss và SQLite failure windows chưa nghiệm thu |
| G06 Concurrency | INCONCLUSIVE | Thiếu multi-process, cancel/complete/delete/read race và mô hình single-instance/fencing |
| G07 Security | NOT_RUN | Thiếu threat model production, authN/authZ multi-user, TLS, input/subprocess sandbox evidence |
| G08 Performance | NOT_RUN | Chưa đo cold/warm cùng máy và cùng dataset trên baseline/candidate |
| G09 IFC geometry | INCONCLUSIVE | Chưa có scientific acceptance suite nguồn/golden/solver provenance đầy đủ |
| G10 FDS integration | INCONCLUSIVE | Solver smoke CI không chứng minh CFD V&V hoặc PyroSim thực |
| G11 Staging | NOT_RUN | Chưa có staging acceptance |
| G12 Backup/restore | NOT_RUN | Chưa có bài khôi phục cô lập với checksum |
| G13 Rollback | NOT_RUN | Chưa diễn tập |
| G14 Observability | INCONCLUSIVE | Thiếu metrics/alerting/heartbeat/runbook production có runtime evidence |
| G15 Production | NOT_RUN | Chưa deploy, smoke hoặc soak trên hạ tầng được cho phép |
| G16 Documentation | IN_PROGRESS | Audit lịch sử có; thiếu báo cáo cuối cùng và bộ runbook có bằng chứng |

G05 được đánh dấu FAIL vì đã xác định nhiều đường cập nhật theo kiểu best-effort còn vi phạm commit-first; điều này chỉ áp dụng cho phạm vi durability production, không phải kết luận tất cả chức năng đều hỏng.

## 3. Danh mục finding còn mở

| ID | Mức | Bằng chứng / nguồn | Bước xử lý |
|---|---|---|---|
| P1-CI-CROSS-EVENT | P1 | PR #40, workflow CI push+PR cả hai SUCCESS | Đã sửa và merge; xác nhận `main` CI #41979799490/#41979799570 |
| IO-TERMINAL | P1 | PR #39, `service.py`, `test_job_terminal_durability.py` | Tích hợp khi required checks không bị cancelled |
| IO-STARTUP/QUEUE/MISSING | P1 | PR #41, `service.py`, `test_job_recovery_durability.py` | Đợi CI và cập nhật base sau #39 |
| IO-TIMEOUT/RSS/SPAWN | P1 | `service.py` vẫn có `repository.set()` best-effort | Fix riêng, fault injection và regression |
| IO-CONCURRENCY | P1/P2 | `repository.py`, `service.py` | Ràng buộc single scheduler hoặc durable coordination đa process |
| SEC-PROD | P1 | `server.py`: API key là tùy chọn và không có production fail-closed config | Threat model, test và deployment boundary |
| C-3b, H-3, H-4/H-5, N-1, H-10, M-15 | P1/P2 khoa học | `LOGIC_ARCHITECTURE_REVIEW_2026-11-02.md`, audit R10 | Fixture gốc, hash, solver output, review khoa học độc lập |
| HVAC-REAL | P1 khoa học | Audit HVAC/PyroSim | Network topology thực, fan/damper, runtime, import PyroSim khi công bố |
| PERFORMANCE | P2 | Benchmark lịch sử chỉ là reference | Đo mới và profile |
| PRODUCTION | P1 | Chưa có staging/backup/restore/rollback/monitoring | Chỉ deploy khi gates tiền nhiệm đạt |

## 4. Hành động an toàn tiếp theo

1. Xác minh lại mọi required checks trên HEAD PR #39, không tự coi một workflow success là bảo vệ nhánh đã đạt; merge #39 nếu GitHub cho phép bình thường.
2. Đồng bộ ma trận #38 với `main`, cập nhật trạng thái dựa trên run mới, kiểm tra CI rồi mới merge.
3. Đổi base #41 sang main và đồng bộ theo SHA sau merge; sửa mọi hồi quy từ CI.
4. Tiếp tục sửa deadline/RSS/spawn transition với regression failure injection và kiểm chứng trên GitHub.
5. Phân tách phạm vi nghiên cứu/chuyển đổi khỏi tuyên bố mô phỏng an toàn cháy; không cấp `SIMULATION_VERIFIED` từ solver success.
6. Chỉ chọn release candidate sau khi 16 gate trong phạm vi release có bằng chứng và người phê duyệt phù hợp.

## 5. Giới hạn bằng chứng

- Chưa có checkout cục bộ hoàn chỉnh trong môi trường thực thi; GitHub connector được dùng để kiểm tra commit, tệp, PR và CI. Không ghi local pytest là PASS.
- Chưa có SSH/VPS/domain/staging credentials hoặc quyền triển khai trong phiên này.
- Audit DOCX gốc có trong repo nhưng chưa đọc được nội dung nhị phân qua đường kiểm tra mã GitHub; báo cáo Markdown được xem và đối chiếu riêng.
- Không điều chỉnh tolerance hoặc verdict khoa học, không đổi branch protection, không triển khai production.

**Next safe action:** kiểm tra #39 sau rerun workflow #41980652295, sau đó kiểm tra mergeability và merge bằng API GitHub nếu đủ điều kiện; cập nhật sổ này theo merge SHA thực tế.


## Checkpoint nghiệm thu mới — 05/11/2026, sau PR #38 và #41

**Nguồn trạng thái:** truy vấn GitHub tại phiên hiện hành; đây là snapshot lịch sử, không tự thay cho lần kiểm tra HEAD sau cùng.

| Đối tượng | SHA / run | Quyết định tại checkpoint |
|---|---|---|
| `main` | `4435800147396d31c7e92568be96eb82f0a029f7` | Đã merge #38 và #41. Hai workflow main tại [#41991091356](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/41991091356) và [#41991091625](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/41991091625) vẫn đang thực hiện ở lần kiểm tra |
| PR #38 | merge `82e825978dd51988461c19840ce4f5f1b5785fae` | MERGED, CI HEAD trước merge PASS |
| PR #41 | merge `4435800147396d31c7e92568be96eb82f0a029f7` | MERGED, required checks HEAD trước merge PASS |
| PR #42 | `93a37059b213e2df9e0929fc86802366948abb05` | DRAFT, đã retarget main, CI mới chưa hoàn thành; kiểm tra retry nguyên nhân timeout/RSS khi SQLite lỗi |
| PR #43 | `0c5f81bfcd4450f5bf22916a51cf7b04eed4f023` | DRAFT, đã đồng bộ main, CI mới chưa hoàn thành; bảo vệ staging/production thiếu API key |
| PR #44 | [#44](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/44) | DRAFT, scheduler health probe, CI chưa hoàn thành |

**Vấn đề cần quyết định tiếp:** xử lý và nghiệm thu #42, #43, #44; JobService spawn transition vẫn dùng cập nhật best-effort, nhiều process/replica chưa được chứng minh an toàn. Các gate G05 (FAIL), G06 (INCONCLUSIVE), G07 (IN_PROGRESS), G14 (IN_PROGRESS) chưa đạt. G09/G10 chưa có đủ kiểm định khoa học độc lập; G11–G13/G15 NOT_RUN. Release verdict vẫn là `NOT_PRODUCTION_READY`.

**Next safe action:** kiểm tra `main` CI trên SHA `4435800`, sau đó CI từng PR trên HEAD cuối. Chỉ đánh dấu VERIFIED/merge khi required checks thực sự PASS. Không đổi branch protection, không cấp `SIMULATION_VERIFIED`, không triển khai production hoặc staging khi chưa có gate/hạ tầng hợp lệ.


## Checkpoint 05/11/2026 — Sau PR #42, #43, #44

**Baseline được truy vấn:** `main` HEAD `9f849075ca893db3bd636d4cee01c9ce7213a7da`. Hai workflow trên HEAD main này đang chạy tại lúc ghi (không tự đánh dấu PASS).

| Đối tượng | SHA/bằng chứng | Trạng thái |
|---|---|---|
| PR #42 | [#42](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/42), merge `59c55700d81ae36fefb4551fb4175507f0330493` | MERGED; timeout/RSS terminal persist được xử lý theo commit-first và regression tests; G05 chưa PASS |
| PR #43 | [#43](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/43), merge `62246d99d820b649aa7a6cd2eb4078477dc31eff` | MERGED; staging/production startup fail-closed nếu thiếu API key/Host allowlist; G07 chưa PASS |
| PR #44 | [#44](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/44), merge `9f849075ca893db3bd636d4cee01c9ce7213a7da` | MERGED; /api/scheduler-health có test; G14 chưa PASS |
| PR #45 | [#45](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/45), HEAD `495c24e436a2215bf6d6b2a8586be0b9ba970925` | DRAFT; worker spawn phải ghi RUNNING bền vững trước Popen; CI mới đang chạy |
| PR #46 | [#46](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/46), HEAD sẽ thay đổi khi cập nhật tracker | DRAFT; offline backup/restore, SHA-256 manifest, test khôi phục; CI mới đang chạy |

**Gate decision:** `NOT_PRODUCTION_READY`. G01 IN_PROGRESS (#45/#46 còn mở); G02 NOT_RUN (release candidate chưa chọn); G05 FAIL, G06 INCONCLUSIVE; G07 IN_PROGRESS; G09/G10 INCONCLUSIVE; G11 NOT_RUN; G12 NOT_RUN (chưa có staging restore drill); G13 NOT_RUN; G14 IN_PROGRESS; G15 NOT_RUN; G16 IN_PROGRESS.

**Phạm vi backup:** công cụ mới chỉ dành cho trạng thái API/worker đã dừng, không được gọi là live consistent backup; SQLite snapshot và checksum chưa thay thế offsite encryption, RPO/RTO, signed provenance hay diễn tập DR. Các verdict khoa học vẫn không được nâng trạng thái.

**Next safe action:** nghiệm thu required checks trên HEAD thực tế PR #45/#46, merge tuần tự qua branch protection khi đủ điều kiện; tiếp tục giải quyết multi-process scheduler coordination, durable terminal outbox, retention/touch persistence, resource limits. Chưa deploy staging/production hoặc thực hiện thao tác mất dữ liệu khi chưa được cấp hạ tầng/phê duyệt.


## Checkpoint 05/11/2026 — Sau nghiệm thu logic verdict khoa học và UI

**Truy vấn GitHub tại checkpoint:** `main` = `68474c16d07baafde25868292a4973211e14efa7`. Hai workflow trên main sau merge #50: `42031907686` (Conversion correctness) và `42031907920` (Source quality), **đang chạy khi checkpoint được lập**; không ghi PASS trước khi có conclusion từ GitHub.

| PR | Nội dung / SHA merge | Trạng thái có bằng chứng |
|---|---|---|
| [#45](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/45) | Durable RUNNING trước spawn | MERGED |
| [#46](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/46) | Backup/restore SQLite + artifact **offline** | MERGED; chưa có production DR drill |
| [#47](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/47) | Durable retention touch | MERGED |
| [#48](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/48) | Single-host scheduler lock, merge `f6773f5` | MERGED, CI HEAD PASS |
| [#49](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/49) | 12 mapping gates, cấm waivers cốt lõi, profile & physics evidence, merge `15580acf` | MERGED, 24 checks success/2 skipped trên HEAD PR; CI main sau merge PASS |
| [#50](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/50) | UI phân biệt mapping/CFD, HTTP/worker error = inconclusive, merge `68474c16` | MERGED, 24 checks success/2 skipped trên HEAD PR; main CI chưa kết luận lúc checkpoint |
| Nhánh research verdict hiện hành | `fix/p0-research-verdict-consistency-20261105` | Chờ PR và CI HEAD sau test; không gọi PASS |

### Tổng hợp lại 16 acceptance gates

| Gate | Verdict theo bằng chứng hiện có | Thiếu để có thể nâng verdict |
|---|---|---|
| G01 — Git & integration | IN_PROGRESS | CI/merge research verdict trên HEAD cuối |
| G02 — Release candidate CI | NOT_RUN | Chưa chọn và ký release candidate, chưa có acceptance đầy đủ |
| G03 — Kiến trúc | INCONCLUSIVE | Review boundary & ownership + API contract trên deploy thật |
| G04 — Functional & regression QA | IN_PROGRESS | CI matrix tốt nhưng thiếu scenario end-to-end tại staging |
| G05 — Persistence/durability | IN_PROGRESS | Đã bảo vệ nhiều transition; chưa có crash/power-loss/corruption test đầy đủ |
| G06 — Concurrency | INCONCLUSIVE | Single-host scheduler lock có; multi-instance/leader fencing chưa xác thực |
| G07 — Security | IN_PROGRESS | Production startup fail-closed có; thiếu penetration/threat model và sandbox evidence |
| G08 — Performance | NOT_RUN | Benchmark cold/warm, peak RSS, quy mô IFC thực, latency và throughput |
| G09 — Scientific IFC/Mapping | INCONCLUSIVE | Contract verdict fail-closed có; thiếu golden IFC thực được duyệt và độc lập V&V |
| G10 — FDS/CFD | INCONCLUSIVE | Solver pinned CI chạy setup/boundary; thiếu mesh convergence, calibration, uncertainty, validation thực nghiệm |
| G11 — Staging | NOT_RUN | Chưa có staging environment hoặc smoke evidence được cung cấp |
| G12 — Backup/restore DR | NOT_RUN | CLI offline đã merge nhưng chưa có recovery drill trên staging, RPO/RTO |
| G13 — Rollback | NOT_RUN | Chưa diễn tập rollback sản phẩm và dữ liệu |
| G14 — Observability | INCONCLUSIVE | Scheduler-health có; thiếu metrics, alerting, trace và diễn tập mất worker |
| G15 — Production deploy | NOT_RUN | Không có production authorization, smoke/soak hoặc gate approval |
| G16 — Documentation & sign-off | IN_PROGRESS | Audit có nhưng thiếu independent science sign-off và release dossier |

**Quyết định phát hành:** `NOT_PRODUCTION_READY`. Không đánh đồng `MAPPING_VERIFIED` với kiểm định an toàn cháy; `SIMULATION_VERIFIED` chưa được phát hành. Lệnh/CI setup FDS không chứng minh kết quả CFD có giá trị khoa học. Không tự tạo dữ liệu IFC, phê duyệt golden, kết quả solver hay evidence.

**Hành động ưu tiên:** (1) sửa research acceptance theo verdict đã finalize; (2) full CI trên HEAD thực tế; (3) khóa semantic parity chi tiết giữa validator legacy và modular; (4) chuẩn bị bộ independent golden IFC/FDS/CFD với provenance để nghiệm thu G09/G10; (5) chỉ sau đó mới xem xét staging và production.
