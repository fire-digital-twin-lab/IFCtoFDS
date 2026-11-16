# Kế hoạch thực hiện M6 — Khắc phục audit IFCtoFDS ngày 15/11/2026

> Khi triển khai, dùng `superpowers:executing-plans` và ghi kết quả theo từng mục. Các ô dưới đây theo dõi việc thực hiện trên commit ứng viên.

**Mục tiêu** · Sửa hai cổng CI đang lỗi, tích hợp tám phát hiện M6 qua chín PR theo thứ tự đã rà soát và chốt bằng chứng hồi quy trước khi đóng mốc.

**Phạm vi** · #119–#127 là chuỗi M6. #128 là PR bàn giao tài liệu. Các task dùng nhánh PR hiện có, kiểm trên `main` mới nhất từng lượt và lưu bằng chứng theo ID F1–F9. F6 đã đóng tại #92.

**Mốc lập** · 2026-11-15 17:54:52 +07:00 (Asia/Bangkok, UTC+7). GitHub báo base của cả mười PR là `e448e11d43d2fe004dff28d95f0fb18cfb58b903`. Checkout khi lập kế hoạch là `docs/m6-review-handover@cfd5a77`.

**Đặc tả và công cụ** · [Bàn giao M6](../../plans/m6-review-handover.md), [roadmap production](../../plans/production-roadmap.md), [mục M6 trên nhánh #119](https://github.com/fire-digital-twin-lab/IFCtoFDS/blob/6d6fdb103a7bf6e3ce4b688bfeb6b94dda98dc95/docs/plans/production-roadmap.md), [audit gốc](AUDIT_2026-11-15_ifctofds-chuyen-doi-hvac-fds.md), [đối chứng F2](AUDIT_2026-11-15_hvac-vent-doi-chung-doc-lap.md). Dùng Git, GitHub Actions, PowerShell, Python theo `uv.lock`, pytest và FDS 6.11.1 đã ghim.

## 0. Trạng thái đã kiểm và phạm vi thay đổi

GitHub xác nhận cả #119–#128 đang mở. Các trạng thái dưới đây thuộc đúng HEAD đã tra tại thời điểm lập kế hoạch.

| PR | ID | HEAD | Tệp chính và trạng thái CI |
| --- | --- | --- | --- |
| [#119](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/119) | M6.0 | `6d6fdb1` | Audit, roadmap, `tolerance-A-C.json` và `tests/test_audit_hardening.py`. Bốn workflow đạt. |
| [#120](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/120) | F1 | `d063832` | `validation/domain_coverage.py`, `validation/engine.py` và `tests/test_domain_coverage.py`. Bốn workflow đạt. |
| [#121](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/121) | F3 | `6debb08` | `validation/passage_resolution.py`, `tests/test_passage_resolution.py` và `tests/baseline/test_behavior_parity.py`. Bốn workflow đạt. |
| [#122](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/122) | F4 | `4f47dee` | `validation/passage_resolution.py` và `tests/test_passage_resolution.py`. Bốn workflow đạt trên base hiện tại. |
| [#123](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/123) | F2 | `cd64c09` | `mapping/exporter.py`, `mapping/obst_boxes.py`, `mep/network.py` và `tests/test_vent_faces.py`. Verified và Quality đỏ. |
| [#124](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/124) | F9 | `6891bb5` | `mep/fds_records.py`, `validation/checkers/hvac.py` và test HVAC/áp suất. Bốn workflow đạt. |
| [#125](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/125) | F7 | `5cd9e55` | `mapping/exporter.py` và `tests/test_audit_remediation.py`. Bốn workflow đạt. |
| [#126](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/126) | F5 | `82d56a1` | `adapters/storage/path_budget.py`, `adapters/storage/filesystem.py`, `cli.py` và `tests/test_path_budget.py`. Quality đỏ, ba workflow còn lại đạt. |
| [#127](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/127) | F8 | `3bf41e5` | `README.md` và `docs/HVAC_NETWORK_IMPLEMENTATION.md`. Bốn workflow đạt. Phụ thuộc hành vi của #123 và #124. |
| [#128](https://github.com/fire-digital-twin-lab/IFCtoFDS/pull/128) | Bàn giao | `cfd5a77` | `docs/plans/m6-review-handover.md`. Bốn workflow đạt. |

Các mục `validation/`, `mapping/`, `mep/` và `adapters/` trong bảng nằm dưới `ifc_to_fds/`.

- **F2 / #123.** Verified lỗi ở job Ubuntu/Python 3.12 tại `test_vent_faces.py:101` với `pytest.approx() does not support nested data structures`. Các job khác trong ma trận Python bị hủy ở lượt này. Quality lỗi ở bước chạy suite có coverage. [Verified](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/43701287891/job/132772773005), [Quality](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/43701287899/job/132772772948).
- **F5 / #126.** Log Quality ghi `path_budget.py: imports_in_functions increased 0 -> 1`. Lượt chạy đã kết thúc. [Quality](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/43703422991/job/132779282131).
- **F3 + F4.** Chạy thử `git merge-tree` trên `6debb08` và `4f47dee` với base chung `e448e11`. Hunk xung đột trực tiếp nằm ở `tests/test_passage_resolution.py`, tại khu vực hai nhánh thêm test. `ifc_to_fds/validation/passage_resolution.py` được cả hai nhánh sửa và gộp được về văn bản. Trạng thái cuối, bộ đếm `assessed` và lý do vẫn cần kiểm sau gộp.
- **Đối chứng F2 đã có.** Audit bổ sung ghi FDS 6.11.1 tái hiện `ERROR(818)` trên deck tổng hợp và khởi tạo được ca tường đặc. Ca dời VENT sang tường đặc, giữ nguyên port IFC vẫn khởi tạo được và bị phép đối chứng tọa độ từ chối. Đây là bằng chứng mốc `e448e11`. Nghiệm thu #123 cần xác nhận compiler trên commit mới từ chối ca ô cửa và deck dương vẫn khởi tạo được. [Phép thử IFC và FDS](AUDIT_2026-11-15_hvac-vent-doi-chung-doc-lap.md#7-bằng-chứng-đã-chạy).

## 1. Ràng buộc tích hợp và trọng tâm kiểm

- Cổng M6 giữ các quyết định đã duyệt. F1 coi MESH chồng là `FAIL`. F4 áp cho mọi OBST khi vật cản co trên ít nhất hai trục. F9 ghi `ROUND=.FALSE.` cho DUCT dạng `AREA/PERIMETER` và giữ đường đọc deck legacy.
- Dùng worktree có đường dẫn ngắn khi bắt đầu sửa. Lưu trạng thái checkout ban đầu gồm các audit local. Tệp audit gốc có cùng đường dẫn với tệp #119 đưa vào Git, nên làm việc tách khỏi checkout đang giữ các bản audit.
- Dùng quyết định review và fixture có nguồn rõ ràng. Chạy các ca A/B/C với cấu hình, phạm vi và dữ liệu được phép. Báo cáo chỉ lưu bí danh, số liệu tổng hợp và verdict.
- Commit, push và merge từng PR theo quyền đã cấp cho thao tác đó. Merge qua GitHub, so khớp HEAD đã kiểm và tuân thủ quy tắc nhánh. Dùng tiêu đề và nội dung commit tiếng Việt có dấu. Ghi kết quả trong roadmap sau khi qua cổng.
- Ưu tiên năm ca dễ lọt. #123 phải phát hiện thay đổi một tọa độ OBST. #126 phải kiểm cả Linux và Windows tắt long paths. #122 phải giữ `FAIL` khi đồng thời có lỗ chưa đo. #124 phải re-audit một bundle ghi trước F9. #127 phải kiểm cả README và tài liệu HVAC sau khi hai PR hành vi có trong `main`.

## 2. Chuẩn bị và xử lý ba điểm chặn

### P0 · Ghim base và chuẩn bị bằng chứng

- [ ] Tại lúc bắt đầu triển khai, cập nhật ref `origin/main` và đọc lại `state`, `baseRefOid`, `headRefOid`, `mergeStateStatus` và kết quả checks của từng PR. Lưu thời gian UTC+7. Nếu PR đã merge, xác minh merge SHA là tổ tiên của `origin/main` rồi chuyển tới bước chưa hoàn tất.
- [ ] Ghi `git status --short`, HEAD, diff đã stage và chưa stage, và kiểm `tests/baseline/snapshots/baseline_metrics.json` trước suite. Mỗi task chạy từ ứng viên tách biệt và giữ dữ liệu checkout trước đó.
- [ ] Lấy hoặc tạo bundle đối chứng F9 từ trước khi đổi serializer. Dùng nguồn công khai `docs/evidence/hvac-network-v1/connected-ducts.ifc` và `configuration.json`. Nếu deck `model.fds` đang lưu có đủ manifest và geometry package tương ứng thì dùng nguyên bộ. Nếu chỉ có deck, xuất một bundle đầy đủ từ `e448e11` và lưu ở thư mục đối chứng riêng, ghi SHA deck, verdict và cấu hình. Đây là đầu vào của P5.
- [ ] Chốt cặp snapshot trước/sau cho FZK, Duplex, Institute và B. Dùng các mốc đóng băng hiện có. Khi chúng đã khác base, ghi thêm lần đo trên `e448e11` hoặc base trước chuỗi với cùng model, scope và cấu hình để nhận ra sai khác mới. Chờ dữ liệu thì ghi rõ ca bị `BLOCKED`.

### P1 · #123 / F2 — Sửa test tương thích pytest

**Tệp sửa** · `tests/test_vent_faces.py::test_the_exporter_writes_exactly_the_boxes_the_compiler_checks`. Test tiếp tục kiểm đúng hai hộp có cùng sáu tọa độ `XB`, ghép theo thứ tự sắp xếp.

- [x] Lưu kết quả lỗi ở lượt Verified/Quality gắn với `cd64c09`. Khi môi trường khớp CI, chạy lại đúng test lỗi trước sửa và quan sát `TypeError`.
- [x] Thay `pytest.approx` trên cả danh sách bằng so sánh các tuple đã làm tròn 9 chữ số thập phân. Giữ `len(written) == len(expected) == 2`. Giá trị 9 chữ số áp cho số học của test này.

  ```python
  assert len(written) == len(expected) == 2
  assert [tuple(round(v, 9) for v in box) for box in written] == [
      tuple(round(v, 9) for v in box) for box in expected
  ]
  ```

- [x] Chạy `python -m pytest -q tests/test_vent_faces.py tests/test_hvac_network.py`. Ca cửa phải bị compiler từ chối và nêu khóa port. Ca hợp mặt hai hộp đồng phẳng phải đạt, ca mặt chung và nửa VENT hở phải bị từ chối. Kiểm phản chứng rằng đổi một cận XB đủ rõ làm assertion đỏ. Chạy `python -m pytest -q -m solver tests/test_hvac_network.py::test_real_fds_accepts_connected_network` với FDS 6.11.1. Dùng cặp deck đóng băng ở mục 7 của audit F2 cho đối chứng solver. Deck cũ trong ô cửa phải trả `ERROR(818)`, deck tường đặc phải khởi tạo thành công. Ghi cả SHA deck và kết quả compiler trên nhánh #123 để phân biệt hai phép kiểm.
- [x] Soát diff test, ghi commit tại nhánh #123, chạy Verified và Quality trên HEAD ứng viên. Cổng qua khi hai workflow hoàn tất thành công cùng SHA. Lỗi `F2-SMV` và đường audit độc lập được theo dõi trong audit riêng. Kết quả `solver=PASS` và kết quả đọc `effective_geometry` có hai hàng bằng chứng riêng.

### P2 · #126 / F5 — Xóa nợ import trong hàm

**Tệp sửa** · `ifc_to_fds/adapters/storage/path_budget.py`. Giao diện giữ `long_paths_enabled() -> bool` và `check_output_path_budget(output, *, limit=260, long_paths=None)`.

- [x] Ghim log lỗi và chạy cổng Quality ở commit `82d56a1` với merge-base thật. Xác nhận tệp mới nằm trong `git diff --name-only $baseSha HEAD` và lỗi thuộc `imports_in_functions`.
- [x] Đặt import `winreg` ở cấp module trong `try/except ImportError`, gán `winreg = None` khi module vắng. Cho `long_paths_enabled()` trả `True` khi chạy ngoài Windows hoặc thiếu module. Giữ cách đọc `LongPathsEnabled` và trả `False` khi Registry báo `OSError`. Giữ ngưỡng 260 gồm NUL theo ý nghĩa của hằng hiện có, tên staging/backup và hành vi báo lỗi trước ghi.
- [x] Chạy `python -m pytest -q tests/test_path_budget.py tests/test_source_quality_budget.py`. Kiểm test ngưỡng chính xác, CLI lỗi sớm, và bundle cũ còn nguyên. Xác nhận import được module và `long_paths_enabled()` trả `True` trên Linux. Trên Windows xác nhận lần lượt Registry `0` → `False`, `1` → `True`, và `OSError` → `False`. Có thể mô phỏng `winreg` tại module để kiểm ba giá trị mà không chỉnh Registry máy.
- [x] Ghi commit tại nhánh #126. Chạy Quality trên chính commit đó theo `5` và xác nhận `path_budget.py` được đưa vào phép so. Cổng qua khi step `Reject newly introduced import/exception debt relative to PR base` và Verified đạt trên HEAD ứng viên.

### P3 · #121 / #122 — Chuẩn bị gộp F3 và F4

**Tệp tổng hợp** · `ifc_to_fds/validation/passage_resolution.py`, `tests/test_passage_resolution.py`. `tests/baseline/test_behavior_parity.py` từ #121 giữ kỳ vọng có lý do cho FZK.

- [ ] Trước chuỗi merge, thử gộp hai HEAD trong worktree kiểm thử hoặc dùng `git merge-tree` để khoanh hunk. Lưu phương án giữ cả nhóm test F3 và F4. Áp lại trên nhánh #122 **sau khi #121 đã có trong `main`**.
- [ ] Ở `PassageResolutionChecker.check` kiểm thứ tự kết quả sau gộp. Finding lỗi cho `FAIL`, lỗ chưa đo cho `INCONCLUSIVE` nếu chưa có lỗi, và `NOT_APPLICABLE` nếu không có gì cần đánh giá. `PASS` khi phần đã đánh giá đạt và không còn lỗ chưa đo. Đếm mỗi OBST được đánh giá một lần trong `assessed`. Cập nhật chuỗi lý do đang giới hạn ở “enclosure obstructions” để khớp diện kiểm mới.
- [ ] Chạy `python -m pytest -q tests/test_passage_resolution.py tests/baseline/test_behavior_parity.py`. Giữ test lỗ qua biên MESH `INCONCLUSIVE`, một mesh có mọi lỗ đo được `PASS`, dầm co hai trục `FAIL`, dầm đủ dày `PASS` và vật cản không phải vỏ bao chỉ co một trục vẫn `PASS` theo test hiện có. Kiểm ca cùng có lỗ chưa đo và OBST co hai trục. Kết quả phải `FAIL`, evidence vẫn có `openings_not_estimated > 0`. Nếu test hiện tại chưa kết hợp hai điều kiện, thêm một ca ghép từ hai fixture sẵn có.
- [ ] Sau #121, cập nhật #122 từ `origin/main`, giải quyết hunk, ghi commit, chạy lại các test trên và chờ Verified/Quality của SHA mới. Xác nhận danh sách diff giữ kết quả F3 và F4 trước khi merge.

## 3. P4 · Lịch tích hợp

- [ ] Hoàn tất vòng sửa P1/P2 và kiểm hợp nhất P3 trước khi bắt đầu chuỗi. Cập nhật #122 chính thức ở lượt của nó.
- [ ] Merge từng PR theo thứ tự **#119 → #120 → #121 → #122 → #124 → #125 → #123 → #126 → #127**. Đọc lại CI sau mỗi cập nhật base. Kiểm `main` chứa merge SHA của lượt trước rồi xác minh SHA của lượt kế tiếp. Trạng thái đỏ, chưa xong, xung đột hoặc head vừa đổi thì giữ PR ở bước chờ tương ứng và xử lý điều kiện đó.
- [ ] Sau #127, rà #128 riêng. Xem các trạng thái đỏ/đang chạy trong `m6-review-handover.md` là quan sát tại thời điểm bàn giao và ghi rõ mốc đó nếu cập nhật tệp. Kiểm link audit và roadmap ở base mới trước khi duyệt PR tài liệu.

| Lượt merge | Kiểm tập trung ngoài CI của HEAD ứng viên |
| --- | --- |
| #119 · M6.0 | `python -m pytest -q tests/test_audit_hardening.py::test_real_compare_solids_feeds_the_shell_rule`. Đọc mốc M6 và bằng chứng A/C sau #118, đối chiếu snapshot FZK/Duplex/Institute. |
| #120 · F1 | `python -m pytest -q tests/test_domain_coverage.py`. MESH tiếp giáp kín đạt, có khe hoặc chồng FAIL, kể cả tổng thể tích bằng nhau. Xác nhận deck hở miền `REJECTED`, đối chứng FZK/B giữ verdict ánh xạ. |
| #121 · F3 | Chạy test passage và parity theo P3. Ghi chuyển `PASS → INCONCLUSIVE` của gate mô phỏng FZK khi có lỗ chưa đo. Xác nhận kết luận mapping được đánh giá theo các cổng mapping. |
| #122 · F4 | Chạy lại P3 trên base đã có #121. Ca chỉ có OBST không thuộc vỏ bao có thể chuyển từ `NOT_APPLICABLE` sang `PASS` hoặc `FAIL`. Ghi chứng cứ cho từng chuyển trạng thái. |
| #124 · F9 | P5 bên dưới. Chạy test áp suất với 4A/P và re-audit deck legacy. |
| #125 · F7 | `python -m pytest -q tests/test_audit_remediation.py`. Kiểm thương rất gần số nguyên không sinh thêm ô và ca vượt giới hạn thật vẫn bị chặn. Đối chiếu snapshot FZK/Duplex/Institute/B. |
| #123 · F2 | Làm mới các lượt P1 trên base đã có #124/#125, chú ý phần exporter cùng thay đổi với #125. |
| #126 · F5 | Làm mới các lượt P2, kiểm cổng nợ trên SHA có tệp mới và ma trận Linux/Windows. |
| #127 · F8 | Rà README mục 8.3–8.5, 9.4 và `docs/HVAC_NETWORK_IMPLEMENTATION.md` theo behavior đã có trên `main`. Kiểm VENT, `ROUND=.FALSE.`, `LOSS(i,j)`, chiều quạt và `D*/Δx`. Soát liên kết và `git diff --check`. |

### P5 · F9 — Giữ bằng chứng thủy lực và deck cũ

- [ ] Chạy `python -m pytest -q tests/test_hvac_network.py`. Ca `test_a_deck_saved_without_round_false_is_reported_not_rejected` phải giữ `hvac=PASS`, có finding `HVAC-FRICTION-0002` P2 ở mức mô phỏng và vẫn từ chối biến đổi `AREA`. Ống tròn giữ giao ước hiện có.
- [ ] Chạy solver theo `5` gồm `tests/test_hvac_fds_pressure.py`. Ca `test_rectangular_duct_friction_uses_the_hydraulic_diameter_with_round_false` đối chiếu sụt áp theo `D_h=4A/P`. Lưu phiên bản solver, điều kiện thử và kết quả.
- [ ] Chạy audit bằng CLI trên bundle trước F9 đã khóa ở P0 với đúng IFC, deck, manifest, cấu hình và bằng chứng geometry. So sánh kết luận mapping, `hvac`, finding và hash. Kỳ vọng giữ kết luận mapping và mã `HVAC-FRICTION-0002` P2 của deck chữ nhật cũ, với điều kiện phát cảnh báo và nội dung theo chính sách F9. Ghi rõ sai khác câu chữ so với baseline. Nếu có sai khác khác, tìm nguyên nhân trước khi nghiệm thu. Lưu kết quả ứng viên riêng để đối chiếu từng trường với bộ mốc.

## 4. P6 · Kiểm tổng hợp và đóng M6.9

- [ ] Tại SHA `main` sau chuỗi M6, chạy suite mặc định và cổng Quality/Verified trên hợp nhất. Kiểm suite solver và browser toàn bộ từ workflow của SHA đó. Có thể chạy cục bộ với môi trường đã sẵn sàng. Ghi link run, phiên bản và kết quả riêng cho solver/browser.
- [ ] Chạy `scripts/verdict-snapshot.py --compare` cho FZK, Duplex và Institute, dùng ba IFC mẫu trong `examples/` và các mốc `baseline-fzk.json`, `baseline-duplex.json`, `baseline-institute.json`. Đối chiếu B với `real-B.json` và cấu hình đã ghi. Phân tích theo gate, finding và đối tượng. Tách thay đổi F3/F4 có chủ ý, sai khác đã có ở base, và hồi quy mới ở ứng viên. Lưu snapshot ứng viên riêng. Nếu Duplex chập chờn, chạy đối chứng lần hai với cùng đầu vào trước khi kết luận.
- [ ] Chạy A và C với cùng scope và cấu hình đã chuẩn y. Ghi bí danh, số `MATCHED/DEVIATED`, verdict mapping, trạng thái `passage_resolution`, số lỗ chưa đo, OBST bị co và kết quả solver nếu chạy. Thiếu quyền hoặc dữ liệu thì ghi `BLOCKED` ở ca IFC và `NOT_RUN` ở phần solver tương ứng. Tách phép xác nhận này khỏi những lượt CI đã xanh.
- [ ] Trong `docs/plans/production-roadmap.md`, ghi từng ID F1–F9 với PR, SHA merge, gate, ca âm/dương và trạng thái. Giữ F6 là đã xử lý ở #92. Đính chính `M3.6` về ma sát chữ nhật theo cờ serializer của F9. Hoàn thành M6.9 sau khi có bằng chứng theo tiêu chí roadmap hoặc quyết định kỹ thuật đã ghi cho phần còn mở.
- [ ] Sau khi đóng hoặc chuyển toàn bộ mục của audit gốc, chuyển bản bằng chứng cần giữ sang `docs/history/` và cập nhật liên kết liên quan. Giữ hồ sơ đang còn việc trong `docs/audit`, gồm đối chứng HVAC độc lập, F2-SMV và các phát hiện kiến trúc/Docker cho tới khi xử lý. Kiểm `git diff --check` và xem cả tệp mới trước bàn giao.

## 5. Lệnh dùng khi triển khai

Chạy trong PowerShell từ worktree của ứng viên, dùng Python của môi trường dự án đã đồng bộ `uv sync --locked --extra test`. Mỗi lượt kiểm sau cập nhật phải nhìn đúng nội dung commit ứng viên, vì script Quality chọn tệp bằng diff tới `HEAD` và đọc mã từ đĩa.

```powershell
$env:PYTHONUTF8 = '1'
$env:IFCFDS_SOLVER_AUTODISCOVERY = '0'
$m6PytestTemp = '.cache/m6-' + [guid]::NewGuid().ToString('N').Substring(0,8)
python -m pytest -q -p no:cacheprovider --basetemp $m6PytestTemp -m "not solver and not browser and not slow" -o faulthandler_timeout=90
if ($LASTEXITCODE -ne 0) { throw 'Suite mặc định chưa qua.' }

$m6BaseSha = git merge-base HEAD origin/main
if ($LASTEXITCODE -ne 0 -or -not $m6BaseSha) { throw 'Không xác định được merge-base để kiểm Quality.' }
git diff --name-only $m6BaseSha HEAD
python scripts/quality/source_quality_budget.py --git-base $m6BaseSha
```

Đoạn dùng `origin/main` tương ứng cổng PR chĩa vào `main`. Run của `main` ngoài PR dùng `HEAD^` theo `quality.yml`. Để so lũy kế toàn M6, dùng base đã ghim ở P0. Khi `origin/main` trùng `HEAD`, diff của phép so PR bằng rỗng. So kết quả Ruff và Pyright với bước tương ứng trong Quality, gồm cả tập tệp Pyright thực sự đang kiểm. [Workflow Quality](../../../.github/workflows/quality.yml), [workflow Verified](../../../.github/workflows/verified.yml).

```powershell
$m6SolverDir = (Resolve-Path '.deps/fds-6.11.1/firemodels/FDS6/bin').Path
$env:IFCFDS_SOLVER = Join-Path $m6SolverDir 'fds_openmp.exe'
$env:PATH = "$m6SolverDir;$m6SolverDir\mpi;$env:PATH"
$env:I_MPI_FABRICS = 'shm'
$env:OMP_NUM_THREADS = '1'
python -m pytest -q -m solver tests/test_hvac_fds_pressure.py tests/test_hvac_junction.py tests/test_hvac_network.py
```

Để chứng minh một PR đủ điều kiện ở lượt hiện tại, ghi `gh pr view <PR> --json state,baseRefOid,headRefOid,mergeStateStatus,statusCheckRollup` và `gh pr checks <PR> --watch`. Khi thực hiện merge theo quyền được cấp, dùng `--match-head-commit` với SHA đã kiểm hoặc chức năng tương đương. Mỗi dòng bàn giao dùng các trường sau.

| PR / ID | Base SHA / HEAD SHA / merge SHA | Lệnh hoặc link run | Kỳ vọng và quan sát | Kết quả | Thời điểm UTC+7 |
| --- | --- | --- | --- | --- | --- |
| Điền khi triển khai | Ghi đủ theo vai trò | Gắn chứng cứ | Ghi gate và dữ liệu đối chứng | `PASS` / `FAIL` / `NOT_RUN` / `INCONCLUSIVE` / `BLOCKED` | Giờ kiểm thật |

Phạm vi của kế hoạch này là tích hợp các PR M6 đã lập. Thiết kế đối chứng tọa độ độc lập, lỗi F2-SMV, đóng gói EV và ratchet kiến trúc có hồ sơ riêng trong [audit HVAC](AUDIT_2026-11-15_hvac-vent-doi-chung-doc-lap.md) và [audit kiến trúc](AUDIT_2026-11-15_kien-truc-docker.md).

## Tiến độ triển khai — 2026-11-15 23:51:39 +07:00

| Mục | Commit hoặc dữ liệu nguồn | Kết quả đã kiểm |
| --- | --- | --- |
| P0 / F9 | `e448e11` | Bundle cũ lưu tại `.cache/m6-f9-base`. Deck SHA-256 `9087c7c6c73549435e1954153a5efccbe74e9c3e5ef86a397a946c9427891f35`, mapping `MAPPING_VERIFIED` và `hvac=PASS`. |
| P0 / snapshot | `e448e11` | Đã lưu FZK, Duplex và Institute vào `.cache/m6-before`. Verdict ba ca khớp mốc đóng băng. FZK khớp các trường đã so. Duplex và Institute đã có lệch `findings_by_gate` trước M6. Ca B và xác minh công trình A/C chưa chạy trong lượt này. |
| M6.0 / #119 | `6d6fdb1` → `6dce86f` | Test `test_real_compare_solids_feeds_the_shell_rule` đạt và #119 đã merge. [Merge SHA](https://github.com/fire-digital-twin-lab/IFCtoFDS/commit/6dce86f742678887058bcfc7a90b8be2a38b890a). |
| P1 / F2 | [`34d4544`](https://github.com/fire-digital-twin-lab/IFCtoFDS/commit/34d454415638117905da41063c16f1b2d14af3cd) | Đã push #123. Local 27 test đạt và 2 ca FDS đạt. Pytest 9.1.1 local chạy được assertion cũ, còn log CI gốc có cùng test lỗi `TypeError`. Job Ubuntu 3.12 từng lỗi đã đạt trên SHA mới. Đổi một cận XB làm assertion mới lỗi. Cả bốn workflow đạt trên base ban đầu. [Verified](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/43736664409), [Quality](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/43736664389). |
| P1 / đối chứng solver | FDS 6.11.1 | Deck ô cửa `dd20a79e…` trả `ERROR(818)`. Deck tường đặc `1fd79fd1…` khởi tạo `PASS`, bộ đọc `effective_geometry` vẫn `FAIL` như audit F2-SMV. Đây là hai deck đối chứng đọc lại từ mục 7 của audit F2. |
| P2 / F5 | [`23508f2`](https://github.com/fire-digital-twin-lab/IFCtoFDS/commit/23508f2807dbdb5fe80dae398d3cb2ba52687846) | Đã tái hiện nợ trên commit cũ, xác nhận `SOURCE_QUALITY_NO_NEW_DEBT` trên commit mới và push #126. 11 test đạt. Probe Registry 0/1/OSError, thiếu `winreg` và nền tảng khác Windows đều đạt. Cả bốn workflow đạt trên base ban đầu. [Verified](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/43736784209), [Quality](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/43736784187). |
| P3 / F3 + F4 | `ce1bae7`, nhánh local `codex/m6-passage-preflight` | 16 test đạt. Ca mới có cả OBST co hai trục và lỗ chưa đo cho `FAIL` với `openings_not_estimated > 0`. Chuyển kết quả sang #122 sau khi #121 đã vào `main`. |
| P5 / F9 | `6891bb5` | 17 test HVAC và 8 ca FDS đạt. CLI re-audit cùng deck và manifest trước F9 giữ `MAPPING_VERIFIED`, `hvac=PASS` và `HVAC-FRICTION-0002` P2 mức mô phỏng. Nội dung cảnh báo đã nêu sự vắng mặt của `ROUND=.FALSE.`. Hash deck giữ nguyên. |

| P4 / F1 | [`cc99e8e`](https://github.com/fire-digital-twin-lab/IFCtoFDS/commit/cc99e8e9089ad0947e7676f1cbc0395a91ce7410) | Đã cập nhật #120 từ `main` sau #119. 9 test domain đạt và cổng nợ sạch. CI của SHA mới đang chạy. [Verified](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/43737812652), [Quality](https://github.com/fire-digital-twin-lab/IFCtoFDS/actions/runs/43737812678). |
| P4 / F7 | `5cd9e55` | 43 test `test_audit_remediation.py` đạt trên nhánh gốc. Chạy lại khi cập nhật base ở lượt #125. |

**Điểm tiếp tục** · Chờ CI của #120 trên `cc99e8e`. Khi đạt, xác nhận GitHub còn cùng head/base, merge và chuyển tới #121. Giữ `ce1bae7` làm bản đối chứng khi cập nhật #122. Mốc M6.9 vẫn mở.
