# Kế hoạch đưa IFCtoFDS lên production
Phạm vi đã chốt: **mapping + HVAC vận hành + cháy xe điện**, chạy được qua **CLI và Web/API (Docker Compose)**, nghiệm thu cuối trên **IFC tầng hầm thật** của dự án.

## Context
Kiểm toán `main@ff91299` (ngày 14/11/2026, đo trên máy Windows của dự án) cho thấy:
- **CLI `convert` hỏng** (vòng import `fire` ↔ `validation.checkers.mesh_resolution`), exit 1, không có file `.fds`.
- **Cả 3 IFC mẫu đều `REJECTED`**, kể cả khi deck đúng: phép giao Boolean A∩A của Manifold mất 1–3,6% thể tích → gate openings báo sai; preflight gắn nhãn `SELF_INTERSECTION` cho hai khối chỉ chạm mặt.
- **Chậm**: FZK 36 s, Institute 153 s; 67–74% thời gian nằm trong `has_self_intersection` (vòng lặp Python từng cặp tam giác + numpy trên vector 3 phần tử + `Fraction`).
- **Tường có lỗ cửa luôn thành `GEOM`** → gate hình học hiệu dụng ở cấp solver luôn `INCONCLUSIVE` → không tầng hầm nào xác minh trọn được.
- **HVAC** chỉ nhận ống thẳng; cút/tê/côn/quạt/van bị chặn. **Cháy xe** dùng một surrogate C₂H₄O, HF chỉ nằm ở metadata, không có HCN, không có lớp vật liệu dẫn nhiệt; preset xe hai bánh 20–150 kW thấp hơn đo thực (1,57 MW).
- Kiến trúc có hai đường validation và hai `JobRepository`; test kiểm bản không chạy ở production.

Mục tiêu: một kỹ sư PCCC đưa IFC tầng hầm thật vào CLI hoặc web, nhận deck FDS **chạy được tới `T_END`** có HVAC hút khói vận hành và nguồn cháy xe có căn cứ, kèm báo cáo truy vết mà mọi `REJECTED` đều là lỗi thật của mô hình.

## Nguyên tắc thực hiện
- Mỗi bước = 1 PR nhỏ, có test hỏng trước khi sửa (TDD), CI xanh mới merge. Không gộp bước.
- Sửa ở chỗ dùng chung, không thêm lớp/facade mới. Ưu tiên xóa code.
- Mỗi **giai đoạn** kết thúc bằng một **cổng nghiệm thu** đo được; chưa qua cổng thì không sang giai đoạn sau (trừ chỗ ghi "song song").
- Script đo đặt trong `scripts/`, số đo baseline lưu ở `docs/evidence/production-roadmap/`.
- IFC tầng hầm thật **không commit** (riêng tư): đặt ngoài repo, trỏ bằng biến môi trường `IFCFDS_PRIVATE_BASEMENT_IFC`; test liên quan đánh dấu `@pytest.mark.private` và tự skip khi thiếu biến.

---

## Giai đoạn 0 — Nền đo và lưu kế hoạch (0,5–1 ngày)
- [x] 0.1 Chép file kế hoạch này vào `docs/plans/production-roadmap.md` (nguồn sự thật để làm từng bước; đánh dấu `[x]` khi xong).
- [ ] 0.2 `scripts/stage-profile.py`: chạy `pipeline.convert` và ghi thời gian từng giai đoạn + thời gian `has_self_intersection` theo nơi gọi (dựa trên script đo đã dùng trong kiểm toán). Xuất JSON.
- [x] 0.3 `scripts/verdict-snapshot.py`: với mỗi IFC mẫu, lưu `{entity_key: (element_status, witness kind)}` + verdict tổng → `docs/evidence/production-roadmap/baseline-<model>.json`. Dùng để chứng minh tối ưu tốc độ **không đổi kết quả**.
- [x] 0.4 Thêm marker `private` và `slow` vào `pyproject.toml:40` (cạnh `solver`, `browser`). Test `slow` chạy Institute (hiện chưa test nào dùng) trong job CI riêng, không chặn PR thường.
**Cổng 0:** baseline FZK/Duplex/Institute + tầng hầm thật được ghi lại (thời gian, RSS, verdict, số finding theo loại).

## Giai đoạn 1 — Sửa lỗi chặn (P0) (2–3 ngày)
- [x] 1.1 **Vòng import CLI.** Xóa re-export `MeshResolutionChecker`, `calculate_d_star`, `check_mesh_resolution` khỏi `ifc_to_fds/fire/__init__.py:44-48` và `__all__`; sửa import trong `tests/test_fire_mesh_gate.py` sang `ifc_to_fds.validation.checkers.mesh_resolution` / `ifc_to_fds.fire.mesh_metrics`.
   Test mới `tests/test_cli_cold_start.py`: `subprocess.run([sys.executable, "-m", "ifc_to_fds", "convert", tiny.ifc, "-o", tmp])` → exit 0 và có `.fds`; tương tự cho `audit` và `python -m ifc_to_fds.jobs <job_dir>`.
- [x] 1.2 **Lối mở A△A.** Trong `passage_metrics` (`ifc_to_fds/validation/metrics.py:222`): nếu danh sách vật cản ứng viên hai vế giống hệt nhau từng byte (so `vertices`/`faces`) → trả `normalized_symmetric_difference=0` và số component của một vế, không chạy Boolean. Với hai vế khác nhau: thêm tự kiểm `V(A∩A)≈V(A)`; nếu Manifold tự mâu thuẫn → `INCONCLUSIVE` kèm số đo (không `FAIL`).
   Test hồi quy: ba lỗ FZK STEP 22174/31539/31607 → lệch = 0. Áp dụng như nhau cho `golden/gate.py:302` (dùng chung hàm).
- [x] 1.3 **Khóa bbox/frame của CLI.** `cli.py:292-298` ghi frame vào `scope.bounding_box.coordinate_frame` (pydantic `BoundingBox` lặng lẽ bỏ khóa lạ), còn `model_preparer.py:29` đọc `scope.coordinate_frame`. Sửa: ghi `config["scope"]["coordinate_frame"]` (`SelectionScope` đã có trường này, `domain/scope/model.py:26-29`). Đồng thời cho `--coordinate-frame` áp cả khi không có `--domain` (`cli.py:288-289`). Test: `--bbox ... --coordinate-frame WORLD` trên model có rebase tường minh → exit 0.
- [x] 1.4 CI: trong `.github/workflows/verified.yml` (hiện chỉ chạy `python -m ifc_to_fds --help` ở dạng cold, `:35`) thêm bước `python -m ifc_to_fds convert tests/baseline/fixtures/tiny.ifc -o out.fds` + kiểm file tồn tại, trên ma trận ubuntu/windows.
**Cổng 1:** `convert` CLI chạy trên tiny + FZK từ tiến trình mới; FZK không còn finding openings với A vs A; toàn suite xanh.

## Giai đoạn 2 — Tốc độ (1–1,5 tuần) — song song được với Giai đoạn 3
- [ ] 2.1 **Viết lại phần lõi `has_self_intersection`** (`ifc_to_fds/geometry/mesh.py:267-430`), giữ nguyên hợp đồng (CLEAN/CONFIRMED + witness kind):
   a. Gom cặp ứng viên một lần (giữ R-tree `tm.triangles_tree`), loại `j<=i`.
   b. Bộ lọc dấu `orient3d` **vector hóa numpy** cho mọi cặp, cùng cận sai số hiện có (`sum|terms|·eps·16`).
   c. Lối tắt chính xác: điểm trùng bit một đỉnh tam giác → dấu 0; đoạn có đầu mút trùng đỉnh tam giác → không cắt (đã đo: 0 khác biệt trên 81 mesh FZK).
   d. Đường chính xác dùng **số nguyên có scale chung 2^k** thay `Fraction` (đo: 31,8 → 4,4 µs, cùng dấu); phép toán còn lại trong vòng lặp dùng float/tuple Python thay numpy 3 phần tử (15,5 → 0,5 µs).
   Test: property test so phiên bản mới với hàm cũ (giữ hàm cũ trong test làm oracle) trên mesh ngẫu nhiên + toàn bộ mesh của 3 IFC mẫu → cùng kết quả và cùng loại witness.
- [ ] 2.2 **Kiểm chất lượng mesh một lần**: memo `inspect_mesh_quality` theo byte mesh trong `mesh_evidence_scope` có sẵn (`mesh.py:130`) — cùng cơ chế cache của self-intersection, không thêm cơ chế mới. Đo: Institute 21.581 lần gọi → ≈ số mesh.
- [ ] 2.3 Chạy `scripts/verdict-snapshot.py` → so với baseline Giai đoạn 0: **phải trùng 100%**.
**Cổng 2:** trên máy dự án: FZK ≤ 12 s, Institute ≤ 60 s (mục tiêu ước lượng, ghi lại số thật); verdict snapshot trùng baseline.

## Giai đoạn 3 — Dọn kiến trúc (3–4 ngày) — song song với Giai đoạn 2
- [ ] 3.1 **Một đường validation.** Xóa `ifc_to_fds/validation/runner.py`, `Container.get_validation_runner`, và 7 checker chỉ runner dùng: `syntax, traceability, geometry, openings, mep, representation, domain` (+ export trong `checkers/__init__.py`); chuyển/xóa test tương ứng (9 file test tham chiếu). Giữ `structural, air_path, hvac, mesh_resolution, scope, boundary, solver` (engine/mapping đang import). Trước khi xóa: rà test của 7 checker, test nào kiểm hành vi mà `engine.py` chưa có test → viết lại nhắm `run_independent_validation`.
- [ ] 3.2 **Một JobRepository.** So `server/job_repository.py` với `adapters/jobs/repository.py`; hành vi nào của commit #98 chỉ có ở bản sao (vd `reconcile_orphaned_jobs`) thì chuyển sang bản thật hoặc xác nhận `JobService._reconcile_startup_jobs` đã bao. Trỏ `tests/test_challenger_p1.py`, `test_empirical_p1_03_challenge.py`, `test_p1_fixes.py` sang bản thật. Xóa thư mục `ifc_to_fds/server/` (shim `SourceFileLoader`).
- [ ] 3.3 Bỏ monkey patch toàn cục `trimesh.triangles.mass_properties` (`mesh.py:13-34`): chỉ dùng trong helper cục bộ nơi cần.
- [ ] 3.4 Test kiến trúc (`tests/test_architecture_contracts.py`): thêm kiểm "không có hai module cùng tên `JobRepository`", và import cold của từng package con (bắt vòng import sớm).
**Cổng 3:** suite xanh; giảm ≈1.400 dòng; API khởi động và chạy job tiny qua `JobService` thật.

## Giai đoạn 4 — Tọa độ và đơn vị (1 tuần)
- [ ] 4.1 Placement (`core/placement.py:33-42`, hiện gắn `CONFIRMED` chỉ cần hữu hạn): tách đoạn kiểm `RᵀR≈I`, `|det R−1|≤1e-6` ở `core/coordinate_preflight.py:64-73` (trong `_classify_local_placement`) thành helper nhận ma trận 3×3, dùng chung cho cả preflight và `extract_placement` (kể cả ma trận MappedItem `:54-57`); IfcAxis2Placement3D không trực giao → trực chuẩn Gram–Schmidt theo chuẩn IFC (giữ Z, chiếu RefDirection) và so bbox với `create_shape`; lệch → `UNVERIFIED` + finding. Test: `RefDirection=(1,0,1)` (case báo cáo).
- [ ] 4.2 Đơn vị: `core/units.py` kiểm kiểu unit (`IfcSIUnit`, `IfcConversionBasedUnit` có chuỗi về SI; `IfcContextDependentUnit` → từ chối). Test fixture `CUSTOM_LENGTH` → exit 3.
- [ ] 4.3 `rebase_model_to_origin` (`core/federation.py:176-286`) dịch thêm `storey_references[].elevation_m` (đang bỏ sót; ảnh hưởng chọn tầng ở `mapping/scope.py:43-73`) và mọi tọa độ phụ (vent_xb, scope bbox) theo cùng một vector; kích hoạt auto-rebase cả theo Z. Test probe `rebase_vector=[1001,0,3]`.
- [ ] 4.4 Ghi `IfcMapConversion`/CRS vào provenance (chỉ ghi nhận, không đổi frame mô phỏng).
**Cổng 4:** tầng hầm thật: placement không còn `CONFIRMED` sai; storey/mesh cùng frame; báo cáo provenance có CRS.

## Giai đoạn 5 — Tô-pô nguồn và lỗ mở cho IFC thật (1,5–2 tuần) — chìa khóa để hết "REJECTED oan"
- [ ] 5.1 Phân loại lại trong `has_self_intersection`/`source_topology_preflight`:
   - Đồng phẳng chồng lấn giữa **hai shell khác nhau với pháp tuyến ngược chiều** = tiếp xúc mặt (giao thể tích 0) → `CONTACT`, không chặn.
   - Diện tích chồng lấn < (IFC `Precision` của context)² → `NUMERICAL_CONTACT` có witness, không chặn.
   - Xuyên tam giác, chồng thể tích, đồng phẳng cùng chiều → vẫn `SELF_INTERSECTION`.
   Fixture: hai hộp chạm mặt (CLEAN), lệch 1 nm, xuyên, lồng nhau, cavity (bảng 2.2 báo cáo).
- [ ] 5.2 Đường xử lý lỗi nguồn thật: dùng cơ chế `decisions` sẵn có (`mapping/policy.py:validate_decisions`) thêm action duyệt `ACCEPT_SOURCE_DEFECT` có lý do + witness hash, để kỹ sư chấp nhận có ghi vết thay vì sửa tay IFC. Report liệt kê rõ phần tử nào được duyệt.
- [ ] 5.3 Đo lại 3 IFC mẫu + tầng hầm: số witness theo loại trước/sau; mỗi witness còn lại phải được 1 người kiểm bằng mắt (ghi kết quả vào `docs/evidence`).
**Cổng 5:** tiny/opening fixture `MAPPING_VERIFIED`; với tầng hầm thật: mọi finding còn lại là lỗi nguồn thật đã được người xác nhận, hoặc được duyệt qua decision → đạt `MAPPING_VERIFIED`.

## Giai đoạn 6 — Hình học hiệu dụng cấp solver (2–3 tuần)
- [ ] 6.1 **Tách tường trực giao có lỗ chữ nhật thành nhiều `OBST`**: trong `mapping/policy.py`, nếu mesh host là đa diện trực giao (mọi mặt vuông góc trục) → chiến lược mới `OBST_SET`: lưới tọa độ duy nhất, giữ ô có tâm nằm trong solid, gộp tham lam thành hộp. Chứng minh chính xác bằng `compare_solids` (hợp các hộp vs mesh nguồn) — tận dụng gate có sẵn. Tường nghiêng/cong vẫn `GEOM`.
- [ ] 6.2 Gate hiệu dụng (`validation/effective.py:88-92`) hiện trả `INCONCLUSIVE` cho cả deck nếu có **bất kỳ** `VENT`/`HOLE`/`GEOM` nào — tức mọi deck có HVAC hoặc burner đều không qua được. Sửa: hỗ trợ `VENT` phẳng trên mặt OBST/biên mesh (đọc vị trí vent sau snap từ SMV, kiểm diện tích và mặt tựa); `OBST` có `CTRL_ID` (cửa đóng/mở) kiểm ở cả hai trạng thái; GEOM chuyển thành `INCONCLUSIVE` theo từng phần tử thay vì cả deck.
- [ ] 6.3 `GEOM` còn lại: gate báo `INCONCLUSIVE` theo từng phần tử (không phải cả deck) + danh sách cho kỹ sư review; production chấp nhận nếu phần tử GEOM không nằm trên đường thoát khói/cửa (kiểm qua air_path).
- [ ] 6.4 Planner lưới: cảnh báo khi khe/cửa < 2 ô hoặc vách < h/2 bị collapse (đã có phát hiện collapse — đưa thành gate bắt buộc cho cửa trên đường khói).
**Cổng 6:** tầng hầm thật: ≥90% vật cản là OBST/OBST_SET (đo), solver setup PASS, `effective_geometry` PASS cho mọi OBST/VENT; mọi cửa trên đường khói giữ diện tích mở sau snap.

## Giai đoạn 7 — HVAC vận hành (3–4 tuần)
Mở rộng `decision["hvac"]` (đang validate bằng `DuctSpec` ở `domain/mep/hvac.py`) thành spec theo loại, tham số do kỹ sư duyệt (hệ số K, đường cong quạt) — không suy từ tessellation.
- [ ] 7.1 `IfcDuctFitting` 2 cổng (cút, côn): thành `DUCT` có `LOSS=(K_thuận,K_ngược)` quy về tiết diện tham chiếu; chiều dài = chiều dài đường tâm (duyệt) thay dây cung.
- [ ] 7.2 Tê/junction ≥3 cổng: thành `NODE` có `LOSS(I,J)` theo hướng.
- [ ] 7.3 `IfcFan`: `&HVAC TYPE_ID='FAN'` với `VOLUME_FLOW` hoặc `FAN_CURVE` (RAMP) + `FAN_ID` trên duct; `IfcDamper`: `DAMPER=.TRUE.` + `CTRL_ID`/DEVC (đóng/mở theo kịch bản).
- [ ] 7.4 Sửa guard trong `mep/network.py:20` để nhận các loại trên; `fds_records.py` sinh namelist mới; parser `validation/parser.py` + `checkers/hvac.py` nhận và kiểm.
- [ ] 7.5 VENT HVAC: thêm trường frame (WORLD/REBASED) cho `EndpointSpec.vent_xb`.
- [ ] 7.6 Kiểm chứng: (a) mạng 1 quạt + 1 ống thẳng + 1 cút: Δp–Q từ FDS (`DEVC QUANTITY='DUCT VOLUME FLOW'`, chạy ngắn) so lời giải tay `Δp=(f L/D_h+ΣK)ρu|u|/2` trong ±5%; (b) tê: bảo toàn khối lượng sai số < 1%; (c) đảo chiều dòng.
**Cổng 7:** hệ hút khói của tầng hầm thật (hoặc nhánh đại diện) biên dịch đầy đủ, FDS chạy tới `T_END`, lưu lượng tại miệng hút so thiết kế trong ±10%.

## Giai đoạn 8 — Cháy xe điện (3–4 tuần, cần dữ liệu ngoài)
- [ ] 8.1 Thư viện preset (JSON trong `reference-cases/ev-library/`, schema `EVPreset` ở `fire/ev_library.py`): thêm `e-moped`/`e-motorbike` từ dữ liệu đo whole-vehicle (Fire Technology 2025: 1,2 kWh → 1,57 MW), sửa `auto-nmc` theo 6 BEV (4,4–12,1 MW). Mỗi preset có citation, miền áp dụng, mức chứng cứ.
- [ ] 8.2 Chế độ **replay đường HRR đo** (CSV T,Q → RAMP) bên cạnh t².
- [ ] 8.3 HF/HCN: HCN qua `HCN_YIELD` của REAC (nhiên liệu có N); HF qua `&SPEC` + bề mặt phát khối lượng theo cùng RAMP. **Xác minh cú pháp/ngữ nghĩa với FDS User's Guide 6.11.1 và chạy setup trước khi code.** Yield lấy từ dữ liệu whole-vehicle, không quy đổi thẳng từ mg/Wh cấp pin.
- [ ] 8.4 Biên truyền nhiệt: `MATL` + `SURF MATL_ID/THICKNESS` cho bê tông/thép host trong kịch bản (tính chất có nguồn, ghi provenance).
- [ ] 8.5 Kiểm chứng: FDS chạy ca 1 xe trong khoang nhỏ → HRR `_hrr.csv` khớp RAMP ±5% (trước khi thiếu ôxy); tích phân năng lượng khớp `assess_scenario_physics`.
**Cổng 8:** kịch bản 1 xe máy điện + 1 ô tô điện trên tầng hầm thật chạy tới `T_END`; báo cáo nêu rõ miền áp dụng và bất định của preset.

## Giai đoạn 9 — Vận hành Web/API (1–1,5 tuần) — song song từ sau Giai đoạn 3
- [ ] 9.1 Spool upload: `TMPDIR` chưa đặt ở đâu, app container `read_only` với tmpfs `/tmp` 256 MiB (`compose.production.yml:40-42`) trong khi job tối đa 500 MiB. Đặt `TMPDIR` trỏ vào thư mục con của volume jobs; bổ sung bước test upload 2×150 MiB vào smoke test của `.github/workflows/container.yml` (đã có chuyển đổi IFC qua HTTPS ở `:244-249`).
- [ ] 9.2 Load test gần hạn mức (queue, 429, timeout, RSS) + restart giữa các stage → job phục hồi đúng.
- [ ] 9.3 Backup/restore `jobs.sqlite3` + artifacts (đã có `operations/offline_backup.py`) — diễn tập có ghi lại.
- [ ] 9.4 Image có FDS 6.11.1 Linux (hash cố định) để chạy gate solver trong container; CI chạy suite `-m solver` trên Linux.
**Cổng 9:** Compose production chạy job tầng hầm thật end-to-end qua web; diễn tập backup/restore thành công.

## Giai đoạn 10 — Nghiệm thu trên tầng hầm thật (1–2 tuần)
- [ ] 10.1 Chạy CLI và web với cùng IFC → artifact giống nhau (hash deck).
- [ ] 10.2 Nghiên cứu lưới 3 mức (`fire/grid_sensitivity_*` có sẵn) cho các QoI đã chốt trước (nhiệt độ/tầm nhìn tại lối thoát, độ cao lớp khói) — báo cáo mô tả, kiểm xu hướng đơn điệu trước khi tính GCI.
- [ ] 10.3 Kỹ sư PCCC độc lập review deck + báo cáo theo checklist; ghi giờ công so với dựng tay (pilot).
**Cổng cuối (Definition of Done production):**
- CLI + web đều cho `MAPPING_VERIFIED` (hoặc REJECTED chỉ với lỗi nguồn thật đã xác nhận) trên tầng hầm thật.
- Deck có HVAC hút khói + kịch bản cháy xe chạy FDS 6.11.1 tới `T_END` không lỗi.
- Thời gian chuyển đổi + audit tầng hầm thật được đo và ghi (mục tiêu < 10 phút).
- Kỹ sư review ký nhận; mọi giới hạn (GEOM review, miền preset cháy) nằm trong báo cáo.

---

## File chính sẽ sửa
`ifc_to_fds/fire/__init__.py`, `validation/metrics.py`, `geometry/mesh.py`, `validation/preflight.py`, `validation/engine.py`, `cli.py`, `application/services/model_preparer.py`, `core/placement.py`, `core/units.py`, `core/federation.py`, `mapping/policy.py`, `mapping/exporter.py`, `validation/effective.py`, `mep/network.py`, `mep/fds_records.py`, `domain/mep/hvac.py`, `validation/parser.py`, `fire/scenario_emitter.py`, `reference-cases/ev-library/*.json`, `compose.production.yml`, `Dockerfile`, `.github/workflows/*`. Xóa: `validation/runner.py`, 7 checker, `ifc_to_fds/server/`.

## Tái dùng (không viết mới)
- Cache theo byte mesh: `mesh_evidence_scope` (`geometry/mesh.py:130`).
- Kiểm ma trận cứng: `core/coordinate_preflight.py`.
- So solid / chứng minh chính xác: `compare_solids` (`validation/metrics.py:78`).
- Duyệt quyết định của kỹ sư: `validate_decisions` (`mapping/policy.py:48`).
- Gate hiệu dụng OBST: `validation/effective.py`; parser FDS: `validation/parser.py`.
- Nghiên cứu lưới: `fire/grid_sensitivity_analysis.py`, `grid_sensitivity_execution.py`.
- Backup: `operations/offline_backup.py`.

## Kiểm tra (mỗi giai đoạn)
- `uv run pytest -q` (toàn suite) + `uv run pytest -q tests/test_cli_cold_start.py` (tiến trình mới).
- Linux có FDS: `IFCFDS_SOLVER=... uv run pytest -q -m solver`.
- `IFCFDS_PRIVATE_BASEMENT_IFC=... uv run pytest -q -m private`.
- `uv run python scripts/stage-profile.py --source <ifc>` và `scripts/verdict-snapshot.py` so baseline.
- Chạy tay: `python -m ifc_to_fds convert <ifc> -o out.fds` → mở deck trong FDS 6.11.1, chạy tới `T_END`, xem Smokeview.

## Ước lượng tổng
Khoảng 4–5 tháng cho 1 kỹ sư; Giai đoạn 2/3 và 9 chạy song song được. Giai đoạn 7–8 phụ thuộc dữ liệu ngoài (hệ số K, đường cong quạt của dự án; số đo cháy whole-vehicle).
