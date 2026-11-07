# IFCtoFDS — Sổ theo dõi nghiệm thu production

## Checkpoint P3a vehicle identity / ground-clearance contract — 07/11/2026

**PR:** #69  
**Code candidate đã nghiệm thu:** `6169b55321d6c7404d7b1a39d3633f3aef2733a9`  
**Roadmap:** P3 đang `IN_PROGRESS`; scoped `EV-GEO-P3A-001 = PASS / E2`, broad `EV-GEO-001 = FAIL`.

- Thêm typed `VehicleGeometry` / `BatteryPack` và ba mode `LEGACY | PARAMETRIC | IFC_BOUND`.
- `LEGACY` tiếp tục là default và giữ serialization lịch sử; không tự cấp scientific claim.
- `PARAMETRIC` bắt buộc `floor_z_m` + positive `ground_clearance_m`; source đặt ở underbody plane.
- `IFC_BOUND` bắt buộc canonical `entity_key`, reviewed `semantic_role=VEHICLE`, `PASSIVE_OBSTACLE` authorization và verified OBST bounds; không emit duplicate vehicle body.
- Battery binding bắt buộc reviewed `semantic_role=BATTERY_PACK` hoặc explicit parametric geometry; bounds phải nằm trong vehicle envelope.
- Scenario evidence lưu resolved vehicle geometry; composer kiểm domain bằng resolved bounds thay vì suy lại legacy dimensions.
- Mixed LEGACY/scientific vehicle modes bị reject fail-closed.
- P3a phát hiện parser drift từ P2: `SURF.FUEL_ID` từng được parser chấp nhận nhưng pinned FDS 6.11.1 từ chối. Scientific parser mặc định nay reject field này; compatibility chỉ được bật tường minh cho LEGACY.
- Source quality #42380373024: **SUCCESS**, `879 passed, 14 deselected`, coverage **87%**; artifact `13577831468`, digest `sha256:37b0be1cc4c529a94cb5eaf2b96ff09727798c654598d3651c099b114eec23a9`.
- Conversion #42380373058: **SUCCESS** cho Linux/Windows Python 3.10–3.13, JavaScript, browser và pinned FDS.
- Solver P3a: **9 passed, 884 deselected**; artifact `13577781396`, digest `sha256:686ada474718c4261eeac039d4548c1ce75453b50cdf5a3aa042c44701861c9c`.
- Solver fixture chạy FDS 6.11.1 thực trong 0.1 s với `dz=0.05 m`: 0.15 m parametric clearance = 3 cells; 0.20 m IFC-bound clearance = 4 cells. Đây **không** phải P4 grid-sensitivity evidence.
- FDS vẫn cảnh báo nên dùng SPEC cho REAC fuel chemistry và OFFGAS generated species không nằm trong built-in table. Hai warning này được giữ như finding P6; không nâng solver syntax/geometry evidence thành physics validation.

**P3 chưa đạt exit criteria** vì còn thiếu: automatic/native IFC vehicle semantic binding, orientation cho rotated/non-axis-aligned vehicle, vehicle↔wall/column acceptance, jet outlets, post-snap/local-mesh clearance và real IFC application evidence.

**Scientific verdict:** scoped P3a `PASS / E2`; full `EV-GEO-001 = FAIL`; overall scientific/application verdict `INCONCLUSIVE`.  
**Release verdict:** `NOT_PRODUCTION_READY`. Không cấp `SIMULATION_VERIFIED`.

---

## Checkpoint P2 parser/physics contract hoàn tất — 07/11/2026

**Candidate đã nghiệm thu:** `125d3175066a4b12e96d23b06a99801293dcf5e5` trên PR #68.

- Parser Verified Core hỗ trợ reviewed subset `MATL`, `PART`, `PROP`, `SLCF`, `BNDF`, `ISOF` và các field P2 cần thiết của `SURF`, `DEVC`, `REAC`, `HVAC`.
- Indexed Fortran keys như `MATL_ID(1,:)` được tokenize đúng; unknown field, missing required field, nonfinite numeric và dangling supported reference tiếp tục fail-closed.
- P2 làm lộ và sửa hai lỗi verifier phụ trợ: solver fatal matcher từng bắt nhầm `Maximum Velocity/Pressure Error:` của run thành công; `parse_value()` từng che mất nguyên nhân nonfinite.
- Conversion correctness #42349141483: **SUCCESS** cho Linux/Windows Python 3.10–3.13, JavaScript, browser và pinned FDS solver; research đúng thiết kế là skipped.
- Source quality and regression evidence #42349141425: **SUCCESS**; full quality **862 passed, 13 deselected, 108 warnings**, coverage **87%**.
- Pinned FDS 6.11.1 solver evidence artifact `13564483853`, digest `sha256:463110d3e78cb6d91c3c611232a7a06841fbcae3832929df86d96b805e2846fa`.
- `FDS-PARSER-001` đạt **PASS / E2** cho parser + solver-integration contract. Không nâng thành solution verification/model validation/application validation.

**Kết luận:** P2 scoped verdict = **PASS (E2)**. Overall scientific/application verdict vẫn **INCONCLUSIVE**; release vẫn **NOT_PRODUCTION_READY**.

---


## Checkpoint P0 governance hoàn tất, bắt đầu P2 parser contract — 07/11/2026

**Main SHA đã nghiệm thu:** c5fe1ae1a883459c1f7d961df600c187e20cbc8d (squash merge PR #67).

- PR #67 bổ sung docs/science/SCIENTIFIC_CLAIMS.md, scientific evidence-manifest schema và fail-closed governance tests.
- Main c5fe1ae1: Conversion correctness #42347938814 **SUCCESS**; Source quality and regression evidence #42347938815 **SUCCESS**.
- P0 governance scope = **PASS (E2 software/governance verification)**; không nâng bất kỳ physics/application claim nào.
- Re-audit P2 xác nhận parser tại baseline chưa nhận MATL, PROP, PART, SLCF, BNDF, ISOF; do đó các record khoa học tương lai sẽ bị syntax gate hạ xuống INCONCLUSIVE.
- Work package P2 hiện tại chỉ sửa parser/schema/tests; không thêm EV physics, vật liệu giả định, sprinkler behavior hay threshold.

**Kết luận:** overall scientific/application verdict vẫn **INCONCLUSIVE**; release vẫn **NOT_PRODUCTION_READY**.

---


## Checkpoint P1 regression và scientific governance — 07/11/2026

**Main SHA đã nghiệm thu:** `cb5424f3886d8269ff8fd45b07f7b57c4ff3f67d` (squash merge PR #66).

- PR #66 đóng finding P1 về số đếm tam giác GEOM: serializer, strategy summary và regression cùng dùng semantic “tam giác không suy biến”; mesh all-degenerate tiếp tục fail-closed.
- Main `cb5424f3`: Conversion correctness #42347061448 **SUCCESS**; Source quality and regression evidence #42347061455 **SUCCESS**.
- PR #66: `node scripts/test-ifc-conversion.js` **PASS** trên ba IFC example thật và regression tổng hợp; pinned FDS 6.11.1 solver **PASS**; browser **PASS**; Python Linux/Windows 3.10–3.13 **PASS**.
- Full quality trên PR HEAD: **848 passed, 12 deselected**, coverage **87%**. Bằng chứng này chỉ cấp **E2 — software verification** cho phạm vi regression tương ứng.
- Controlled rerun của `main@dbc37cd3` sau một native exit-139 đã PASS mà không đổi source; root cause của native crash vẫn **INCONCLUSIVE**, không được coi là đã sửa chỉ vì rerun xanh.
- P0 governance còn thiếu formal claim ledger và scientific evidence-manifest schema; work package kế tiếp phải bổ sung fail-closed governance trước khi mở rộng physics/parser.
- G09 IFC Geometry và G10 FDS/CFD vẫn **INCONCLUSIVE** ở mức application/scientific acceptance; B1/B2 vẫn chưa có experimental/application V&V và independent review đầy đủ.

**Kết luận:** P1 regression scope = **PASS (E2)**. Overall scientific/application verdict = **INCONCLUSIVE**. Release verdict = **NOT_PRODUCTION_READY**.

---


## Checkpoint sau các PR #61–#64 — 07/11/2026

**Main SHA tại thời điểm ghi checkpoint:** `3640d99d49017b93dd8ebf47417c0279aad82648` (merge [PR #64](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/64)). Mục này **thay thế thông tin trạng thái hiện hành** của các snapshot bên dưới; không xóa lịch sử để truy vết.

- [PR #60](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/60) MERGED `e00624b1`; [main Conversion #42271306054](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42271306054) và [main Quality #42271306050](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42271306050) **SUCCESS**.
- [PR #61](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/61) MERGED `a2428569`, chống purge/retention trong lượt tải artifact bằng lease; [main Conversion #42330708717](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42330708717) và [main Quality #42330708649](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42330708649) **SUCCESS**. PR HEAD `9c91ac03` đạt 9/9 contexts, full quality **840 passed, 12 deselected**. Root cause CI ban đầu: fake ASGI receive loop và expectation CancelledError phụ thuộc phiên bản Starlette; đã sửa bằng regression thật, không bỏ qua test.
- [PR #62](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/62) MERGED `2404e3a2`, chờ verified UI idle trong stale-worker E2E; [main Conversion #42291965464](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42291965464) và [main Quality #42291965457](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42291965457) **SUCCESS**. Browser E2E flakiness chưa có repeated soak evidence.
- [PR #63](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/63) MERGED `9faabc64`, bảo toàn stopped-worker terminal reason qua diagnostic/SQLite lỗi; [main Conversion #42331377851](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42331377851) và [main Quality #42331377866](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42331377866) **SUCCESS**; PR quality **844 passed, 12 deselected**.
- [PR #64](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/64) MERGED `3640d99d`, atomic create-if-absent publication cho `diagnostics.json` (temp + flush/fsync + hard link), không ghi đè worker diagnostic. PR HEAD `342bb042` [Quality #42331440065](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42331440065) / [Conversion #42331440045](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42331440045) / [push #42331436353](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42331436353) **SUCCESS**, 9/9 required contexts, **848 passed, 12 deselected**. **Main merge SHA #3640d99 CI #42331896749/#42331896741 IN_PROGRESS khi ghi checkpoint; KHÔNG gán PASS**.
- Chỉ có PR tài liệu của chính checkpoint này sẽ mở sau khi tạo; các PR #61–#64 đều merged. Không có GitHub Release tại lần truy vấn. Không có bằng chứng deploy production thực tế, staging E2E, cold backup/restore drill hoặc rollback rehearsal.

### 16 gate: snapshot mới, không tự nâng khi thiếu bằng chứng

| Gate | Trạng thái | Điều kiện nghiệm thu còn thiếu |
|---|---|---|
| G01 Git integration | IN_PROGRESS | CI trên main merge SHA #64 và release candidate còn thiếu |
| G02 Release CI | NOT_RUN | Không có release candidate SHA và release package |
| G03 Architecture | INCONCLUSIVE | Architectural full parity và migration evidence còn thiếu |
| G04 Functional QA | IN_PROGRESS | CI regression có; staging E2E và soak chưa đạt |
| G05 Job persistence | IN_PROGRESS | PR #63/#64 có fault injection; chưa chứng minh power loss, disk corruption, cross-process replay |
| G06 Concurrency | INCONCLUSIVE | Download lease trong một process đã có; chưa có full multi-host/multi-process race và long streaming soak |
| G07 Security | IN_PROGRESS | Internet threat model, authz, TLS và isolation deployment chưa nghiệm thu |
| G08 Performance | NOT_RUN | Cold/warm benchmark với baseline/candidate đo đồng nhất |
| G09 IFC Geometry | INCONCLUSIVE | Golden công trình thực B1/B2 vẫn DRAFT, reviewer null, evidence rỗng |
| G10 FDS/CFD | INCONCLUSIVE | Solver CI không phải independent physical V&V |
| G11 Staging | NOT_RUN | Chưa có staging smoke, negative test, soak |
| G12 Backup/Restore | NOT_RUN | Có scripts/tests, chưa có staged recovery drill |
| G13 Rollback | NOT_RUN | Chưa rollback rehearsal |
| G14 Observability | IN_PROGRESS | Cần logs/metrics/alerts có chứng cứ quan sát vận hành |
| G15 Production | NOT_RUN | Không có actual production deployment/smoke |
| G16 Documentation | IN_PROGRESS | Tracker cập nhật; thiếu sign-off/release evidence |

**Kết luận bắt buộc:** `NOT_PRODUCTION_READY`. Không được cấp `SIMULATION_VERIFIED` cho công trình B1/B2. `MAPPING_VERIFIED` (theo model/evidence giới hạn) không thay thế solver validation hoặc kiểm định PCCC độc lập. Chưa đủ chứng cứ để vận hành công khai với dữ liệu nhạy cảm.

**Finding tồn đọng:** `IO-DIAGNOSTIC-LEGACY-CORRUPT` (file cũ tồn tại nhưng JSON hỏng), `CI-BROWSER-HANDSHAKE-01` (cần repeated soak), crash windows sau SQLite commit trước filesystem cleanup, network/unsupported hard-link mounts, multi-process lease, backup/restore rehearsal, `SCI-REAL-01` và `SCI-PARITY-01`.

**Hành động tiếp theo:** xác minh CI `main@3640d99`, nghiệm thu PR tracker mới, chọn G05/G06 fault injection hoặc G07 staging security ưu tiên theo bằng chứng; nghiên cứu khoa học phải dựa trên IFC/FDS nguồn có provenance và chuyên gia ký duyệt.

---


## Checkpoint Git và production acceptance — 07/11/2026, sau PR #59

**HEAD main đã truy vấn:** `3f90132abae94a2efcd7ba4a73b12dbd786948c4` (merge #59). Các mục có ngày cũ bên dưới là snapshot lịch sử.

- **Không còn PR mở** tại lần truy vấn GitHub ở checkpoint này. PR #38–#59 đã được đối chiếu trong phạm vi chuỗi nghiệm thu, các PR phát sinh mới phải truy vấn tiếp.
- **PR #57:** [merge `5d3b1f4`](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/57). [Main Conversion #42262907385](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42262907385) và [Main Quality #42262907437](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42262907437) **SUCCESS**.
- **PR #58:** [merge `ff7f329`](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/58). [Main Conversion #42264208457](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42264208457) và [Main Quality #42264208452](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42264208452) **SUCCESS**.
- **PR #59:** [merge `3f90132`](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/59). PR HEAD `b53eaf11`: [Conversion #42264341863](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42264341863), [Quality #42264341872](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/42264341872) **SUCCESS**, 9/9 required contexts. **CI main merge SHA #42265343333/#42265343492 đang IN_PROGRESS tại thời điểm checkpoint; không gán PASS.**
- Quy tắc branch protection được giữ nguyên, không force merge, không force push. Finding `CI-DUPLICATE-SHA-01` tiếp tục được lưu để phân tích check-run cancellation lịch sử; GitHub Issues bị tắt.
- `IO-RETENTION-01`, `IO-CLEANUP-01`, `IO-CANCEL-DIAGNOSTIC-01` và `IO-SCHEDULER-DIAGNOSTIC-01` có code/test đã merge, nhưng **chỉ nghiệm thu các đường hồi quy tương ứng**; G05/G06 vẫn cần crash/power-loss, race, retention/delete/download và multi-process fault injection.

### Production gates (không nâng verdict thiếu chứng cứ)

| Gate | Status | Điều kiện còn thiếu |
|---|---|---|
| G01 Git Integration | IN_PROGRESS | Chờ nghiệm thu CI final main SHA sau #59 và cập nhật tracker qua CI |
| G02 Release CI | NOT_RUN | Chưa có release candidate SHA/release artifacts |
| G03 Architecture | INCONCLUSIVE | Architecture migration, detailed parity còn thiếu |
| G04 Functional QA | IN_PROGRESS | CI regression rộng có; chưa có staging E2E |
| G05 Job Persistence | IN_PROGRESS | Filesystem/SQLite crash windows, cold restart/power loss cần nghiệm thu |
| G06 Concurrency | INCONCLUSIVE | Race download/delete, multi-process tests rộng chưa đủ |
| G07 Security | IN_PROGRESS | Threat model internet, authz nhiều người, sandbox, TLS deployment |
| G08 Performance | NOT_RUN | Baseline/candidate cold/warm và resource benchmark |
| G09 IFC Geometry | INCONCLUSIVE | Real IFC provenance và reference B1/B2 `approval.json=DRAFT` |
| G10 FDS/CFD | INCONCLUSIVE | Independent physical V&V và solver experiment |
| G11 Staging | NOT_RUN | Chưa có staging environment/smoke/soak được nghiệm thu |
| G12 Backup/Restore | NOT_RUN | Script không thay thế staged restore drill |
| G13 Rollback | NOT_RUN | Chưa rehearsal rollback |
| G14 Observability | IN_PROGRESS | Cần telemetry, alerting và disaster drills |
| G15 Production | NOT_RUN | Chưa production deployment/smoke |
| G16 Documentation | IN_PROGRESS | Tracker/báo cáo có, thiếu release package và sign-off |

**Verdict:** `NOT_PRODUCTION_READY`; `MAPPING_VERIFIED` chỉ hợp lệ cho đúng model/evidence kiểm tra, không đồng nghĩa `SIMULATION_VERIFIED`. Không có bằng chứng phê duyệt khoa học độc lập cho công trình B1/B2 hoặc khả năng dùng trong thiết kế PCCC thực tế.

**Next safe action:** (1) xác minh CI `main@3f90132`; (2) tiếp tục G05/G06 fault injection SQLite/filesystem/queue và giới hạn tài nguyên; (3) security/threat model và recovery drills; (4) scientific verification có provenance/solver thực; (5) staging trước production. Không dùng dự án trên internet cho dữ liệu nhạy cảm khi G07/G11 chưa đạt.

---



## Checkpoint tích hợp mới — 07/11/2026 (sau merge PR #58)

**HEAD main đã đối chiếu:** `ff7f32933421f9984dd0eb50677c6b2fe07ba7e0` — merge [PR #58](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/58). **Không suy ra workflow trên merge SHA đã PASS** cho đến khi kiểm tra GitHub Actions.

- [PR #57](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/57) đã MERGED tại `5d3b1f4`, hai workflow main `#42262907385` và `#42262907437` SUCCESS.
- [PR #58](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/58) đã MERGED tại `ff7f329` sau khi hai workflow pull_request `#42263377779` và `#42263377785` SUCCESS trên HEAD `eb0913e`; các check bắt buộc đủ 9/9.
- [PR #59](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/59) đang OPEN, sửa `IO-SCHEDULER-DIAGNOSTIC-01`: supervisor không chết do `OSError` khi ghi diagnostic, bảo toàn SQLite cho retry. Nhánh cần đồng bộ cả logic `cancel()` từ #58 và CI trên HEAD mới; không merge khi có check pending/failed.
- Các checkpoint trước dòng này là **lịch sử**, không được diễn giải là main hiện tại.
- **Các gate G05/G06 chưa PASS.** Lỗi diagnostic đã có regression không thay thế crash-consistency filesystem/SQLite, nhiều process, backup/restore thực tế hay thử nghiệm server OS crash.
- **Scientific:** `SIMULATION_VERIFIED` chưa được cấp; reference B1/B2 `DRAFT`. G09/G10 `INCONCLUSIVE`; staging/production `NOT_RUN`.
- **Release:** `NOT_PRODUCTION_READY`.

**Bước an toàn tiếp theo:** xác minh CI merge `ff7f329`; xác minh PR #59 trên HEAD mới và reviewer; chỉ merge sau required checks; tiếp tục fault injection và lập evidence độc lập.

---




## Checkpoint tiếp tục — 07/11/2026 (trước khi tích hợp PR #58)

**HEAD `main` tại lần truy vấn GitHub:** `5d3b1f4d31eb00e501e7a335bf7568b18056ae17` (merge PR #57). Đây là commit mới hơn checkpoint #55 bên dưới; mọi snapshot cũ chỉ để truy vết.

- [PR #57](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/57) **MERGED** tại `5d3b1f4`; các workflow push/PR trên HEAD `ef9604b` SUCCESS, đủ 9 required checks trước merge. Hai workflow mới trên merge SHA `5d3b1f4` còn `IN_PROGRESS` khi ghi checkpoint; không tuyên bố đã PASS.
- [PR #58](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/58) **OPEN, Ready for review**, base `main`, đã ghép kết quả #57 và bảo toàn regression `tests/test_job_cleanup_nonfatal.py`. HEAD trước bản cập nhật tracker này: `7a96155dcf23c863a287b5291b791e2f015f713e`. Bắt buộc dùng HEAD mới nhất tại thời điểm merge; workflow CI đang được chạy lại.
- Lỗi trả HTTP thất bại sau `CANCELLED` durable mà không ghi được `diagnostics.json` có bản sửa và `tests/test_job_cancel_diagnostic_io.py`; trạng thái `FIXED_PENDING_VERIFICATION` cho đến khi có CI PASS/merge.
- GitHub branch protection vẫn giữ nguyên 9 required contexts. Không tự kết luận #57 G05/G06 đã PASS vì chỉ kiểm thử cleanup; trường hợp OSError tại các đường diagnostic scheduler khác còn cần sửa riêng.
- `CI-DUPLICATE-SHA-01` tiếp tục mở cho tình huống nhiều check runs có cùng SHA và trạng thái cancelled trong lịch sử. Quyết định merge phải dựa trên trạng thái mới nhất do GitHub thực thi.

**Ma trận gate tiếp tục giữ:** G01 `IN_PROGRESS`; G02 `NOT_RUN` (release SHA); G03 `INCONCLUSIVE`; G04/G05/G07/G14/G16 `IN_PROGRESS`; G06/G09/G10 `INCONCLUSIVE`; G08/G11/G12/G13/G15 `NOT_RUN`. `NOT_PRODUCTION_READY`. Chưa có staging, benchmark production, bài thử mất điện, nghiệm thu IFC công trình thực, independent CFD V&V hoặc GitHub Release.

**Next safe action:** Chỉ merge #58 sau khi CI PASS trên HEAD thực tế; kiểm tra CI `main` sau merge. Sau đó ưu tiên fault-injection đối với `JobService._terminal_diagnostic` tại scheduler, SQLite/filesystem crash windows và race download/retention.

---

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
