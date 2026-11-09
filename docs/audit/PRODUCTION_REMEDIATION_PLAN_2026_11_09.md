# IFCtoFDS — Kế hoạch khắc phục và tái nghiệm thu production (09/11/2026)

**Trạng thái:** PROPOSED — kế hoạch triển khai, chưa phải bằng chứng đã sửa hoặc phê duyệt release.  
**Baseline:** `main@4a5029e9040ba15927c25444595126c19e5f6bd9`.  
**Repository:** `fire-digital-twin-lab/IFCtoFDS`.  
**Nguồn đối chiếu:** `compose.production.yml`, `Dockerfile`, `deploy/nginx.conf.template`, `deploy/PRODUCTION_DEPLOYMENT.md`, `scripts/production-smoke.py`, `.github/workflows/{container,quality,verified}.yml`, `docs/operations/*`, `docs/science/SCIENTIFIC_CLAIMS.md` và `reference-cases/basement-b1-b2`.  
**Release verdict hiện tại:** `NOT_PRODUCTION_READY`; overall scientific/application `INCONCLUSIVE`.

## 1. Phạm vi và nguyên tắc

### 1.1 Phân tách hai track phát hành

- **Track A — Production phần mềm:** single-instance Workbench + IFC conversion + Verified Mapping/API, job scheduler, SQLite/artifacts, TLS, authentication, restore, monitoring, rollback. Có thể vận hành với kết luận mô phỏng `INCONCLUSIVE`; tuyệt đối không mô tả là EV-fire simulation đã được kiểm chứng khoa học.
- **Track B — Production khoa học:** IFC/EV geometry, battery/clearance/outlets, solver, grid sensitivity, numerical/solution verification, uncertainty, experimental/application validation và phê duyệt độc lập. `EV-GEO-001` hiện `FAIL`; `MESH-LOCAL-001` `INCONCLUSIVE`; P4c2a scoped `PASS/E2` không chứng minh mesh independence.
- Kết thúc Track A không nâng verdict Track B. Release toàn hệ thống chỉ được chấp thuận theo intended use đã được ký duyệt; không tự phát hành `SIMULATION_VERIFIED`.

### 1.2 Nguyên tắc engineering/V&V bắt buộc

1. `INSPECT → ROOT CAUSE → IMPLEMENT → NEGATIVE TEST → REGRESSION → CI → EVIDENCE → REVIEW → MERGE` cho từng work package.
2. Một PR giải quyết một nhóm nguyên nhân gốc gắn kết; không trộn science refactor với production deployment.
3. Commit message, PR description và tài liệu bằng **tiếng Việt**; tên code/API giữ nguyên theo conventions.
4. Không sửa hoặc tái ghi đè golden/approval/evidence để làm xanh CI; thiếu dữ liệu hoặc phê duyệt phải giữ `INCONCLUSIVE`/`NOT_READY`.
5. Không giảm branch protection, bỏ qua security checks, tắt test, hạ ngưỡng chấp nhận, dùng `curl -k` hoặc xóa volume để qua nghiệm thu.
6. Không chạy lệnh phá hủy dữ liệu thật; backup/restore rehearsal chỉ chạy trên staging cô lập, đích mới, có approval và rollback.
7. Mọi bằng chứng cần gắn repo SHA, image digest, lệnh/phiên bản, hệ điều hành, dataset/hash, outcome, logs và reviewer.
8. Không tự ghi `PASS` cho gate chỉ có unit/container smoke trên GitHub runner. G11–G15 cần runtime/drill/release evidence độc lập.

## 2. Trạng thái đầu vào đã xác minh

- `main@4a5029e`: Source Quality run `42608206539` — SUCCESS (`976 passed, 16 deselected, 121 warnings; 87% coverage`); Conversion run `42608206468` — SUCCESS (Python Linux/Windows 3.10–3.13, browser, JS, pinned Windows FDS); Container run `42608206469` — SUCCESS.
- PR #80 đã merge: triển khai Compose + Dockerfile + NGINX TLS, fail-closed startup, smoke CLI qua HTTPS. CI trên runner **không** thay thế staging acceptance.
- PR #82 đang mở: cập nhật historical acceptance tracker; không sửa code; tránh chồng chéo tệp giữa kế hoạch mới và PR #82.
- `compose.production.yml` có named volume `jobs` cho `/var/lib/ifctofds/jobs`; offline backup runbook đang minh họa host root `/srv/ifctofds/jobs` nhưng chưa có mapping tương ứng.
- Container chạy UID/GID `10001`, API key ở `/run/secrets/api_key`. Cần kiểm chứng host ownership/mode thật: file-backed Compose secrets dùng bind mount, không hỗ trợ remap UID/GID/mode như secret backend khác.
- `deploy/nginx.conf.template` trên HTTP dùng `return 308 https://$host$request_uri`. Theo default-server routing của NGINX, Host không hợp lệ có thể ảnh hưởng đích redirect; cần sửa canonical redirect và negative tests.
- Branch protection đã bật; danh sách required contexts đã đọc chưa chứa `container` và `python-quality`. Thay đổi policy phải qua quyền admin và xác nhận context names ổn định.
- `docs/operations/MONITORING_RUNBOOK.md` mô tả telemetry/alert nhưng thiếu live staging drill. `docs/operations/BACKUP_RESTORE_RUNBOOK.md` xác nhận G12 = NOT_RUN.
- `reference-cases/basement-b1-b2` còn `DRAFT`, schema `0.4.0`, không có approved domain; `mapping_acceptance=INCONCLUSIVE`, `output_complete=false`. Chưa đáp ứng P4c2b readiness.

## 3. Work packages và kế hoạch PR

### R1 / PR-01 — Khóa Host và HTTPS redirect (P1, đầu tiên)

**Nhánh dự kiến:** `fix/nginx-canonical-host-redirect`.  
**Tệp:** `deploy/nginx.conf.template`; `tests/test_production_deployment_artifacts.py`; `.github/workflows/container.yml`; deployment runbook (nếu thay đổi vận hành).

**Thực hiện**
- Bổ sung `default_server` xử lý Host không được phép trên IPv4/IPv6, reject `444`/`421` theo contract được chọn và kiểm thử.
- Chỉ redirect HTTP Host hợp lệ tới hostname canonical được cấu hình, không sử dụng `$host` do client điều khiển trong `Location`.
- Kiểm tra HTTP Host trống/sai, Host có port, IPv6 listener, HTTPS Host/SNI sai và đường dẫn/query; bảo toàn valid 308, TLS 1.2/1.3, headers, auth.
- Không đưa internal port hoặc upstream vào redirect; không làm thay đổi `/api/health` semantics hay API authorization.

**Acceptance:** valid Host trả đúng `308 Location: https://<canonical-host>/...`; invalid Host bị từ chối, không trả redirect tới domain do attacker chỉ định; NGINX config lint + container-level tests PASS.  
**Rollback:** revert chỉ PR, không liên quan dữ liệu; giữ HTTP 80 từ ngoài bị chặn nếu cấu hình mới gặp lỗi.

### R2 / PR-02 — API key file và non-root secret access (P1)

**Nhánh dự kiến:** `fix/production-secret-permissions`.  
**Tệp:** `compose.production.yml`, `deploy/PRODUCTION_DEPLOYMENT.md`, `.github/workflows/container.yml`, security tests.

**Thực hiện**
- Chọn policy file secret phù hợp rootless/non-root UID 10001. Kiểm thử cụ thể owner/mode trên Linux host và mount thực tế (ví dụ group-read hợp lệ được kiểm soát, không mặc định world-readable).
- Thêm positive/negative case: file tồn tại đúng quyền; unreadable; empty; short; missing; rotated; sai allowed-host; khởi động phải fail closed với secret không hợp lệ.
- Không in key trên argv/log, không copy secret vào image layer; kiểm tra worker process không vô tình được cấp key ngoài yêu cầu.
- Kiểm thử thay key/restart và key cũ không còn được chấp nhận; ghi rõ secret rotation runbook.
- Giữ root filesystem read-only, drop capabilities, không chạy app với root chỉ để giải quyết quyền secret.

**Acceptance:** CI chạy với file mô phỏng quyền host production; UID 10001 đọc được khóa được phép và bị từ chối đúng các ca âm tính; HTTP 401 khi thiếu/sai key, không xuất hiện secret trong log/command.  
**Rollback:** secret rotation có phương án quay lại key trước trong thời gian kiểm soát; không rollback sang anonymous API.

### R3 / PR-03 — Backup/restore khớp Compose named volume (P1)

**Nhánh dự kiến:** `fix/compose-offline-backup-recovery`.  
**Tệp:** `compose.production.yml`, `deploy/PRODUCTION_DEPLOYMENT.md`, `docs/operations/BACKUP_RESTORE_RUNBOOK.md`, `scripts/` hoặc maintenance helper riêng và integration tests.

**Thực hiện**
- Cung cấp lệnh offline backup thực sự mount **đúng named volume** của project Compose và đích backup host độc lập; cấm hard-code `/srv/ifctofds/jobs` nếu path đó không được mount.
- Tách helper chỉ dành cho bảo trì khỏi app đang phục vụ; xác nhận các worker đã thoát và không còn job `QUEUED/RUNNING` trước snapshot.
- Sử dụng existing `ifc_to_fds.operations.offline_backup`; không thay bằng raw `cp` SQLite đang live; bảo toàn WAL-aware snapshot, manifest schema 2, file/directory hash, no-symlink/traversal, no-overwrite.
- Restore vào **named volume mới** + môi trường staging cô lập; xác minh `PRAGMA integrity_check`, job count, absolute paths, artifact SHA-256, file rỗng/thư mục rỗng, CLI/API đọc được evidence.
- Thêm test backup file bị sửa, disk-full/partial backup, corrupted SQLite/manifest, missing dirs, destination exists; fail closed, không xóa source.
- Tài liệu hóa offsite backup, encryption, retention, quyền truy cập, RPO/RTO do operator phê duyệt; staging drill là bằng chứng gate riêng, không tự PASS chỉ từ CI.

**Acceptance:** Compose maintenance invocation được chạy E2E trên data volume test; backup + restore sang volume mới giữ exact manifest/hash; thao tác khi worker đang chạy bị chặn, không bao giờ xóa data gốc.  
**Rollback:** không dùng `down --volumes` trong vận hành; app dùng nguyên volume cũ; restore chỉ ở volume mới sau khi xác minh.

### R4 / PR-04 — End-to-end IFC conversion trên runtime container (P1)

**Nhánh dự kiến:** `test/production-container-e2e`.  
**Tệp:** `.github/workflows/container.yml`, `tests/`, `scripts/production-smoke.py` hoặc một E2E harness riêng; fixture `tests/baseline/fixtures/tiny.ifc`.

**Thực hiện**
- Chạy chính production Compose app+NGINX qua HTTPS, có API key, upload real tiny IFC, tạo job, poll terminal state có timeout, lấy result, tải artifacts và đối chiếu SHA/provenance.
- Xác nhận scoped `MAPPING_VERIFIED` hoặc trạng thái fail-closed theo fixture contract, nhưng `simulation_status` phải giữ `INCONCLUSIVE`.
- Restart app/Compose **không xóa volume**, đọc lại job và chứng cứ đã hoàn thành.
- Negative tests: thiếu API key, Host sai, Origin sai, quá dung lượng, corrupt artifact, client disconnect, worker timeout, storage unavailable; dùng test có giới hạn thời gian/tài nguyên.
- CI stdout không chứa key, path nhạy cảm hay nội dung tài liệu IFC ngoài fixture.
- Tách job test có định danh rõ, không lấy kết quả website root/health thay thế conversion E2E.

**Acceptance:** same-image HTTPS E2E PASS trên CI Linux; saved result/manifest/geometry bytes ổn định qua restart; negative outcomes reject/inconclusive đúng semantics; không cấp scientific PASS.

### R5 / PR-05 — Release guard, image provenance, supply chain (P1/P2)

**Nhánh dự kiến:** `ci/release-security-gates`.  
**Tệp:** `.github/workflows/container.yml`, new release workflow/scripts, docs.

**Thực hiện**
- Giữ job check names ổn định, duy nhất; đề xuất branch admin yêu cầu `container`, `python-quality`, `types-and-javascript` cùng các required contexts hiện có. Cấu hình ruleset là **thao tác admin riêng**, không coi PR yaml đã tự đổi protection.
- Build once, promote same SHA/digest từ staging tới production (đăng ký image GHCR hoặc registry được phê duyệt); không rebuild từ branch tùy ý tại production.
- Pin/verify base images và actions có chính sách cập nhật; phát hành SBOM, dependency/image vulnerability scan, provenance attestation và kiểm tra tồn tại artifacts.
- Định nghĩa fail policy cho critical/high CVEs dựa trên exploitability/risk, expiry của exception, người phê duyệt; không bỏ chặn mặc định bằng waiver trống.
- Chỉ cho deployment workflow chạy sau protected environment approvals và successful release checks. Không tự deploy.
- Release dossier khóa source SHA, image digest, versions, reference hashes, config hashes, CI links và rollback version.

**Acceptance:** kiểm tra negative policy bằng PR cố ý làm fail container/security, chứng minh không thể merge/release; staging và production dùng cùng digest.

### R6 / PR-06 — Observability, performance, staging/rollback drills (P1/P2)

**Nhánh dự kiến:** `ops/staging-acceptance-drills`.  
**Tệp:** `docs/operations/MONITORING_RUNBOOK.md`, new staging acceptance scripts, operational tests, runbook, alert configuration.

**Thực hiện**
- Theo dõi `/api/health`, `/api/scheduler-health` và `/api/operational-status` qua TLS có key; theo dõi HTTP 5xx, queue/RSS/disk, worker exits, SQLite errors và backup freshness.
- Không hiểu `disk_usage` đọc thành công đồng nghĩa disk còn đủ. Đặt disk/RSS/queue thresholds dựa trên đo capacity staging và policy được chủ sở hữu chấp thuận.
- Diễn tập kill app/scheduler, áp lực disk/cgroup/worker timeout có kiểm soát; chứng minh alert phát ra, logs được lưu, supervisor/operational recovery hoạt động.
- Benchmark cold/warm IFC conversion, memory peak, latency, throughput/queue, artifact download và multi-client ở cấu hình host mục tiêu; giữ test dataset, hardware specs và hashes.
- Diễn tập offline restore, restart, rollback image/schema vào root/volume **mới**; ghi RPO/RTO thực đo, failure containment, recovery validation.
- Giữ single-instance/single-scheduler deployment; multi-host/leader election không được coi là hỗ trợ trước khi có thiết kế và tests độc lập.

**Acceptance:** G11/G12/G13/G14 chỉ nâng trạng thái khi evidence trên staging host, có timestamp, SHA/digest, logs, alert timeline, restore hashes và reviewer.  
**Rollback:** không đổi dữ liệu production khi diễn tập; giữ named volume/backup và phiên bản image trước.

### R7 / SCI-01 — Scientific V&V và reference B1/B2 (track riêng, P1 khoa học)

**Nhánh dự kiến:** `science/p4c2b-approved-application-study`, chỉ mở khi prerequisites hợp lệ.

**Prerequisites:** external IFC source `ALL_FDS_2027.ifc` (hoặc approved replacement), checksum chính xác, reviewer và rationale độc lập, schema hiện hành, domain/geometry package/mapping `MAPPING_VERIFIED`, output hoàn chỉnh và `P4c2b readiness=READY`. Không được tự sửa `approval.json` sang APPROVED hoặc tự tạo “golden”.
- Đối chiếu real geometry, EV identity/clearance/collision và bounded source scope; broad `EV-GEO-001` hiện `FAIL` và phải được khắc phục bằng evidence thật.
- Xây dựng observables, quantity/units, locations, durations, boundary assumptions và engineering decision cho 3-grid application study; giữ scenario invariants/hashes.
- Chạy pinned FDS có provenance, kiểm tra mesh sensitivity, điều kiện dùng Richardson/GCI và numerical uncertainty; không gắn threshold 4–16 hoặc universal tolerance tùy tiện.
- So sánh với experimental/reference measurements khi có; mô tả model bias, uncertainty, applicability domain và independent review.
- Cập nhật claim ledger theo từng scoped claim; không nâng toàn bộ `SIMULATION_VERIFIED` khi vẫn có blocker.

**Acceptance:** evidence E3/E4/E5 tương ứng domain được thẩm định; tất cả claim độc lập được review và provenance tái lập. Nếu thiếu reference hoặc assumption, kết luận vẫn `INCONCLUSIVE`.

### R8 / REL-01 — Final acceptance và release approval

- Xác định intended-use của release; nếu chỉ Track A, mọi tính năng scientific chưa verified phải có UI/API warning/fail-closed rõ.
- Tổng hợp G01–G16 theo release SHA; mỗi gate có evidence, owner/reviewer, conclusion và exception policy.
- Xác minh security, functional staging, DR, rollback, monitoring, performance và release digest. Không “PASS” bằng lời mô tả hoặc screenshot không có provenance.
- Chỉ sau khi chủ sở hữu phê duyệt mới tạo GitHub release và thực hiện production deployment. Kiểm tra sau deploy: TLS, traffic, job conversion thật, telemetry, backup và rollback readiness.
- Gate nào `FAIL`/`INCONCLUSIVE` ảnh hưởng intended-use thì **NO-GO**; phát hành một subset chỉ khi được xác định và ghi nhận rõ giới hạn.

## 4. Ma trận ưu tiên/điều kiện phụ thuộc

| Thứ tự | Work package | Phụ thuộc | Trạng thái lúc lập kế hoạch |
|---|---|---|---|
| 1 | R1 NGINX Host/redirect | Baseline main | TO_DO |
| 2 | R2 Secret permissions | R1 test harness (có thể làm song song code) | TO_DO |
| 3 | R3 Backup volume | Baseline existing backup engine | TO_DO |
| 4 | R4 Container E2E | R1, R2, stable Compose | TO_DO |
| 5 | R5 Release/security gates | R4 check names và CI ổn định | TO_DO |
| 6 | R6 Staging drill | R1–R5 + hạ tầng/credentials/approval | BLOCKED_EXTERNAL |
| 7 | R7 Scientific V&V | Approved B1/B2 external data và independent reviewer | BLOCKED_SCIENTIFIC |
| 8 | R8 Release acceptance | G01–G16 theo intended-use | BLOCKED |

PR #82 là thay đổi tracker riêng; không merge gộp với các PR sửa code này. Khi PR #82 merge, rebase/sync tài liệu nếu cần.

## 5. Test matrix và bằng chứng bắt buộc

| Nhóm | Positive | Negative | Nơi chạy | Bằng chứng |
|---|---|---|---|---|
| Host/TLS | valid Host→canonical 308, HTTPS 200, HSTS | wrong Host/SNI, redirect poisoning, invalid cert | Container CI + staging | response headers, NGINX config digest |
| API credentials | UID 10001 đọc đúng file, auth 200 | unreadable/empty/missing/wrong key, key rotation | Container CI + staging | owner/mode, response codes, masked logs |
| Job E2E | upload→terminal→artifact SHA→restart | failure injection, corrupt artifacts, timeout | Container CI + staging | job ID, result/manifest hashes |
| Persistence | backup→new-volume restore→same hashes | active worker, partial/corrupt, traversal, disk-full | Integration CI + staging drill | backup manifest, SQLite integrity, restore log |
| Monitoring | health/operational-status/alerts trigger | dead supervisor, storage pressure, queue backpressure | Staging | alert timeline, recovery |
| Supply chain | pinned image digest, SBOM, signed provenance | tampered image, failed CVE gate | CI/release environment | immutable digest, attestation |
| Physics/mesh | approved application grid/observables | incomplete source, mismatched solver/input, invalid assumptions | Scientific runner | FDS/CSV/log hashes, independent review |

## 6. Định nghĩa Done cho mọi PR

1. Root-cause report, impacted files/contracts và risk assessment.
2. Có regression test tái hiện lỗi trước sửa hoặc chứng minh baseline failed behavior; positive+negative tests sau sửa.
3. Unit/integration/browser/solver tests liên quan PASS; Source Quality và Conversion CI PASS trên final PR head; Container CI PASS nếu chạm deployment.
4. Không làm yếu deterministic gates, evidence manifest, safety controls, path validation hoặc confidence/claim semantics.
5. Commit/PR bằng tiếng Việt; mô tả before/after, lệnh test, expected results, logs, code SHA, risks, rollback.
6. Đồng bộ tài liệu và checkpoint; CI/staging/release evidence không trộn nhầm; không ghi “deployed” nếu chưa thực tế deploy.
7. Chỉ merge qua branch protection, không force-push main, không bỏ review và không merge khi required check còn pending/failure.

## 7. Acceptance gates và no-go

**G01:** Git/CI reproducibility; **G02:** immutable release artifact; **G03:** architecture/API contract; **G04:** functional E2E; **G05:** durable job state; **G06:** concurrency isolation; **G07:** security; **G08:** performance; **G09:** IFC/geometry verification; **G10:** FDS/CFD V&V; **G11:** staging; **G12:** backup/restore; **G13:** rollback; **G14:** observability; **G15:** production deployment; **G16:** docs/sign-off.

- **NO-GO Track A:** security Host/secret unresolved; no container E2E; backup/restore/rollback/monitoring staging drills incomplete; no approved image digest/release evidence; no owner sign-off.
- **NO-GO Track B:** `EV-GEO-001=FAIL`; `MESH-LOCAL-001=INCONCLUSIVE`; no P4c2b approved reference; no validated numerical uncertainty/experimental application evidence or independent reviewer.
- Quy tắc: `PASS` phải có đúng domain, evidence level, test corpus, traceable immutable artifacts và reviewer. Nếu không, giữ `INCONCLUSIVE`/`NOT_RUN`.

## 8. Nguồn chuẩn và hợp đồng tham chiếu

- NGINX name-based virtual servers/default server: https://nginx.org/en/docs/http/request_processing.html
- Docker Compose file-backed secrets và permissions: https://compose-spec.github.io/compose-spec/container_spec.html
- Docker Compose secrets operations: https://docs.docker.com/compose/how-tos/use-secrets/
- GitHub protected branch & required checks: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- FDS official manuals: https://pages.nist.gov/fds/manuals.html
- Dự án: `docs/operations/BACKUP_RESTORE_RUNBOOK.md`, `docs/operations/MONITORING_RUNBOOK.md`, `docs/science/SCIENTIFIC_CLAIMS.md`, `docs/science/P4C2A_EXECUTED_GRID_STUDY_CONTRACT.md`.

## 9. Bước thực hiện kế tiếp

**Bắt đầu R1** trên nhánh riêng: tái hiện wrong-Host redirect bằng production NGINX image; sửa canonical redirect và default-server; bổ sung positive/negative HTTP+HTTPS regression; chạy Container + Source Quality + Conversion; tạo PR tiếng Việt để review. Không chỉnh sửa dữ liệu production trong vòng R1.
