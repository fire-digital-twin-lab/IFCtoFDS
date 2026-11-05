# IFCtoFDS — Sổ theo dõi nghiệm thu production


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
