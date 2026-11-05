# IFCtoFDS — Ma trận cổng nghiệm thu và trạng thái sẵn sàng production

**Thời điểm chốt bản kiểm tra:** 05/11/2026. **Baseline tích hợp khi khởi tạo:** `2e4115ee752ff843db4ef67854f2f6db89f95cf4`.
**HEAD đã xác minh tiếp:** `cf2e185d779f48b098d48de6879b8a00ea6de13a` (PR #37 đã merge).
**Kết luận:** `NOT_PRODUCTION_READY`. Đây là sổ kiểm soát phát hành, không
phải chứng chỉ kiểm định hình học hoặc xác nhận thiết kế PCCC.

## 1. Chuỗi Git và CI

| Đối tượng | Evidence | Kết luận |
|---|---|---|
| PR #22–#35, #36 | GitHub PR merged, merge commit `2e4115ee` cho #35; #36 `0d774d58` | Tích hợp thành công |
| PR #33 | `d6de83b3`, hai workflow PASS; merge `e8ea5cd5` | Bảo vệ admission, không bảo vệ toàn bộ update |
| PR #34 | `1e04b8e1`, hai workflow PASS; merge `1d5aaf4b` | Bảo vệ xóa metadata trước artifact |
| PR #35 | `ec9abbf6`, hai workflow PASS; merge `2e4115ee` | Không đọc localStorage để lấy API key |
| `main` sau PR #35 | [Conversion correctness #41972049690](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/41972049690) và [Source quality #41972049611](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/41972049611) | **PASS** trên `2e4115ee` |
| P1 cập nhật trạng thái khi hủy | [PR #37](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/37), commit `3bbb3cfb`; CI [41972399887](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/41972399887) và [41972400046](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/41972400046) PASS | **MERGED** ở `cf2e185d`; cần kiểm tra lại trên merge HEAD |

Cần cập nhật bảng khi workflow *thực sự kết thúc*, với SHA, run ID và
kết luận riêng. Không thay thế kết luận của `main` bằng kết quả CI của
HEAD PR hoặc tự động coi `research=SKIPPED` là PASS.

## 2. Ma trận finding và các bước kiểm tra

| ID | Mức | Mã nguồn / bằng chứng cần đối chiếu | Tiêu chí nghiệm thu | Trạng thái |
|---|---|---|---|---|
| P1-SCHEDULER | P1 | `adapters/jobs/service.py`; `tests/test_job_missing_worker.py`; CI #41884937668 | `proc=None` không chết thread, báo FAILED và lưu diagnostic | `VERIFIED` cho đường lỗi đã kiểm thử, concurrency rộng hơn chưa đóng |
| IO-ADMISSION | P1/P2 | `adapters/jobs/repository.py`; `tests/test_job_admission_persistence.py` | SQLite commit trước publish, ID trùng bị từ chối | `VERIFIED` cho admission |
| IO-DELETE | P1/P2 | `adapters/jobs/repository.py`; `tests/test_job_deletion_persistence.py` | Không xóa artifact trước khi metadata được xóa | `VERIFIED` cho các ca kiểm thử hiện có |
| IO-CANCEL | P1 | `adapters/jobs/service.py`; PR #37; CI 41972399887/41972400046 | Khi SQLite lỗi, không tự công bố CANCELLED, HTTP 503 | `VERIFIED` cho đường lỗi đã kiểm thử |
| IO-UPDATE | P1/P2 | `JobRepository.set()` cập nhật RAM trước khi kiểm tra SQLite; [PR #39](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/39) | Update terminal, timeout và recovery phải bền vững; thử disk-full/restart | `IN_PROGRESS`, không đóng toàn bộ |
| IO-CONCURRENCY | P2 | Scheduler, cleanup, artifact download và SQLite | Multi-thread/process, race, crash/restart, idempotency | `OPEN` |
| C-3b | P1 khoa học | `fire/scenario_verdict.py`, energy budget, HRRPUA/RAMP, solver | Đối soát 9.015,5 MJ so với 144 MJ và xác minh độc lập | `OPEN`, chưa được tái xác minh trong bản audit này |
| H-3 | P1 khoa học | HF species và FDS chemistry | Nguồn HF định lượng có căn cứ; nếu chưa có phải `NOT_MODELED` | `OPEN` |
| H-4/H-5 | P1 khoa học | Door `DEVC/CTRL/CTRL_ID`, solver 6.11.1 | Cửa tác động thực đến đúng OBST và trường dòng | `OPEN` |
| N-1 | P1 khoa học | Opening grid alignment, multi-mesh | Chứng minh thông thủy thực tế theo mesh/solver | `OPEN` |
| H-10 | P1 khoa học | Effective OBST/GEOM/HOLE/VENT | Nếu không hỗ trợ, `INCONCLUSIVE` chứ không PASS | `OPEN` |
| M-15 | P2 khoa học | `validation/checkers/mesh_resolution.py` | D*/dx tại HRR bất lợi có tiêu chí và độ nhạy lưới | `OPEN` |
| M-6b | P2 bảo mật | `js/verified-workflow.js`, `scripts/test-ephemeral-api-key.js` | Không đọc/ghi browser storage | `VERIFIED` cho bộ phận localStorage, không đóng security tổng thể |
| SEC-PROD | P1/P2 | `server.py`, auth, CSP, TLS, upload, sandbox | Threat model + các test phân quyền, secret rotation, HTTPS | `OPEN` |
| PERF | P2 | FZK-Haus và benchmark script | Cùng máy/commit/dữ liệu, cold/warm, median và RSS | `OPEN`, không lấy số lịch sử làm kết quả mới |
| HVAC-REAL | P1 khoa học | `docs/audit/LOGIC_ARCHITECTURE_REVIEW_2026-11-02.md`, fixture công trình | Topology/terminal/flow solver/PyroSim đối chiếu độc lập | `OPEN` cho phạm vi công trình thực |

**Lưu ý:** `VERIFIED` ở một hàng chỉ xác nhận đúng ca và phạm vi
hồi quy được liệt kê, không hàm ý mọi kịch bản production hoặc khoa học.

## 3. Production readiness gates — không cho release trước khi đạt

| Gate | Bằng chứng chấp nhận được | Trạng thái |
|---|---|---|
| P0/P1 | Danh sách finding, fix commit, test/CI không còn blocker | BLOCKED |
| CI trên release HEAD | Hai workflow và required checks đồng thuận PASS; `main` `2e4115ee` đã PASS, HEAD `cf2e185d` cần CI riêng | IN_PROGRESS |
| Kiểm định IFC/FDS | Provenance SHA256, output, golden fixtures, solver log, verdict độc lập | INCONCLUSIVE |
| Bảo mật | AuthN/AuthZ, CSP/TLS, secrets, sandbox, injection/rate-limit tests | NOT_RUN |
| Benchmark | Có baseline/candidate cùng hệ thống, median và biến thiên | NOT_RUN |
| Staging | Environment/smoke E2E/negative tests với dữ liệu đại diện | NOT_RUN |
| Backup/restore | Diễn tập khôi phục SQLite và artifact, xác minh checksum | NOT_RUN |
| Rollback | Thực hành quay lại phiên bản trước, không phá dữ liệu | NOT_RUN |
| Observability | Logging, correlation ID, metrics/alert, runbook | INCONCLUSIVE |
| Production smoke | Deploy trong hạ tầng đã cho phép; test cuối | NOT_RUN |

## 4. Quy tắc diễn giải khoa học và triển khai

- Sinh được FDS không tương đương `MAPPING_VERIFIED`.
- `COMPLETED` không tương đương `SIMULATION_VERIFIED`.
- Solver chạy xong không chứng minh độ chính xác mô phỏng hoặc thiết kế PCCC.
- Giữ nguyên `REJECTED`, `NOT_RUN`, `INCONCLUSIVE` cho đến khi xuất
  hiện bằng chứng đủ mạnh, có provenance và được đánh giá độc lập.
- Có thể xét sản phẩm **nghiên cứu/chuyển đổi giới hạn** nếu cô lập rõ
  tính năng chưa được thẩm định, sau khi security/operational gates đạt;
  không cấp chứng nhận thiết kế cháy thực tế từ CI.

## 5. Thứ tự kỹ thuật tiếp theo

1. Nghiệm thu `main` tại `cf2e185d` sau khi PR #37 đã merge; xử lý PR #39 và xác minh trên HEAD mới.
2. Sửa các cập nhật SQLite `set()` ở terminal/timeout/restart, không chỉ admission/cancel.
3. Kiểm thử concurrency, fault injection và atomicity filesystem/SQLite.
4. Tái hiện khoa học C-3b, H-3, H-4/H-5, N-1, H-10, M-15 với fixture
   có hash, dữ liệu FDS/solver và chuyên gia phụ trách.
5. Hoàn thiện threat model, staging deployment, backup/restore/rollback,
   benchmark và release checklist trước khi cân nhắc sản phẩm có giới hạn.

**Chưa triển khai production. Không có bằng chứng đủ để phát hành
`FULLY_VERIFIED`.**
