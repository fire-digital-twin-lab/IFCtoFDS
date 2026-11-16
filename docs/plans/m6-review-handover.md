# M6 — phân tích và bàn giao (khắc phục audit 2026-11-15)

Lập ngày 2026-11-15, `main` tại `e448e11`. Nguồn: [bản audit của Codex](../audit/AUDIT_2026-11-15_ifctofds-chuyen-doi-hvac-fds.md) (PR #119 đưa vào `main`) và mốc M6 trong [kế hoạch production](production-roadmap.md). Quyết định đã chốt: F9 dùng `ROUND=.FALSE.`, F1 MESH chồng nhau là FAIL, F4 áp cho mọi OBST.

## 1. Trạng thái từng bước

| Bước | PR | Nội dung | CI | Ghi chú |
|---|---|---|---|---|
| M6.0 | #119 | Lưu audit, ghi mốc M6, cập nhật bằng chứng sau #118, test lớp vỏ qua `compare_solids` | xanh | Chỉ tài liệu và test |
| F1 | #120 | Cổng `domain` kiểm MESH phủ kín miền: không chồng nhau (FAIL), tổng thể tích bằng thể tích miền | xanh | B vẫn `MAPPING_VERIFIED` |
| F3 | #121 | `passage_resolution` INCONCLUSIVE khi còn lỗ chưa đo | xanh | Mốc parity FZK đổi PASS → INCONCLUSIVE (17 lỗ không đo được) |
| F4 | #122 | Vật cản co về đường hoặc điểm trên lưới là FAIL, với mọi OBST | xanh | **Xung đột với #121** (xem 2.3) |
| F2 | #123 | VENT HVAC nằm trọn trên mặt rắn–khí của các hộp OBST được ghi ra | **ĐỎ** | Lỗi test, xem 2.1 |
| F9 | #124 | `ROUND=.FALSE.` cho ống `AREA/PERIMETER`; deck cũ chỉ nhận finding P2 | xanh | 8 ca solver đạt với FDS 6.11.1 |
| F7 | #125 | Thương gần số nguyên không thêm ô lưới | xanh | |
| F5 | #126 | Từ chối thư mục đầu ra quá sâu trước khi chuyển đổi (Windows) | **ĐỎ** | Cổng nợ nguồn, xem 2.2 |
| F8 | #127 | README: mesh gate D*/Δx và năng lực HVAC | đang chạy | Đúng khi #123 và #124 merge |

Mỗi PR có test hỏng trước khi sửa, đã thử đột biến, chạy toàn bộ suite mặc định (1342–1352 đạt cục bộ) và cổng nợ nguồn cục bộ.

## 2. Phát hiện khi rà soát

### 2.1 Phải sửa: test của #123 đỏ trên CI (đã xác nhận bằng log CI)
`tests/test_vent_faces.py::test_the_exporter_writes_exactly_the_boxes_the_compiler_checks` so `written == pytest.approx(expected)` trên danh sách các bộ 6 số. Bản pytest của CI không hỗ trợ cấu trúc lồng nhau (`TypeError: pytest.approx() does not support nested data structures`), bản cục bộ thì chạy. Làm đỏ mọi job Python của PR. Sửa: so từng bộ sau khi làm tròn, ví dụ `[tuple(round(v, 9) for v in b) for b in ...]`.

### 2.2 Phải sửa: #126 vi phạm cổng nợ nguồn (đã xác nhận bằng log CI)
`ifc_to_fds/adapters/storage/path_budget.py` có `import winreg` trong hàm; cổng báo `imports_in_functions increased 0 -> 1`. Cục bộ cổng báo sạch vì so tệp mới khác cách. Sửa: nhập ở đầu tệp, bọc `try/except ImportError` đặt `winreg = None` (mô-đun chỉ có trên Windows), và `long_paths_enabled` trả `True` khi `winreg is None`.

### 2.3 Phải sửa trước khi merge: #121 và #122 cùng sửa `passage_resolution.py`
Đã kiểm bằng `git merge-tree`: có xung đột. Cách làm: merge #121 trước, rồi cập nhật nhánh #122, giải quyết xung đột ở khối cuối hàm (F3 viết lại nhánh INCONCLUSIVE/NOT_APPLICABLE). Sau khi cả hai vào, chỉnh câu chữ còn nhắc "enclosure obstructions" ở các chuỗi lý do và đếm lại `assessed` (F4 đếm mọi OBST).

### 2.4 Thứ tự merge để tài liệu đúng
#127 (README) mô tả VENT trên hộp OBST và `ROUND=.FALSE.`; chỉ đúng sau #123 và #124. Thứ tự đề xuất: #119, #120, #121, #122 (sau khi cập nhật), #124, #125, #123 (sau khi sửa 2.1), #126 (sau khi sửa 2.2), #127. Sau mỗi lần merge `main` đổi nên các PR khác cần cập nhật nhánh và chờ CI lại.

### 2.5 Chưa kiểm hoặc rủi ro còn lại
- **F2:** chưa chạy lại ca `ERROR(818)` của audit bằng FDS (cần mô hình canonical tổng hợp); hình học kiểm bằng đúng các hộp của audit, và ca solver HVAC có sẵn đạt.
- **F4:** `assessed` nay đếm mọi OBST, nên mô hình chỉ có vật cản không phải vỏ bao đổi từ `NOT_APPLICABLE` sang `PASS`/`FAIL`. Chưa chạy lại A và C; B vẫn `MAPPING_VERIFIED`, không có finding `passage_resolution`.
- **F3:** FZK đổi gate sang INCONCLUSIVE; B có 20 lỗ không đo được nên cũng INCONCLUSIVE (chỉ ảnh hưởng verdict mô phỏng, mapping giữ nguyên).
- **F9:** deck HVAC đã lưu trước đây (bằng chứng trong `docs/evidence/hvac-network-v1`, tham chiếu golden) chưa được đối chiếu riêng; suite xanh nhưng chưa có ca golden mô phỏng deck cũ.
- **F5:** không hỗ trợ đường dẫn tiền tố `\?\`; chỉ kiểm sớm và báo lỗi rõ. Giữ nguyên tiền tố `.staging-`, `.backup-`, `.ifcfds-work-` vì test hiện có ghim chúng.
- Chưa chạy suite solver đầy đủ và suite browser trên các nhánh M6.
- Số đo `verdict-snapshot` cho Duplex và Institute vẫn lệch mốc đóng băng cũ (gate `passage_resolution` mới, `air_path`, `representation` chập chờn đã ghi); khác biệt giống hệt trước M6, mốc chưa được tạo lại.

## 3. Việc tiếp theo (theo thứ tự)
1. Sửa 2.1 trên nhánh #123 và 2.2 trên nhánh #126; chờ CI xanh.
2. Merge theo thứ tự ở 2.4 (người dùng yêu cầu merge từng PR).
3. M6.9: ghi kết quả từng ID vào Phần A của roadmap (đánh dấu `[x]` các bước M6, đính chính mục M3.6 về ma sát ống chữ nhật: nguyên nhân là thiếu cờ trong serializer), xóa tệp audit khỏi `docs/audit/` theo quy ước.
4. Chạy lại `convert` A và C sau khi gộp để xác nhận F3/F4 không đổi verdict ngoài thay đổi có chủ ý; ghi vào `docs/evidence/production-roadmap/`.
5. Các việc còn lại của kế hoạch chung: M1.7 phần A, M3.1, M0.3, đối chiếu PyroSim (T19–T21) khi có deck.

## 4. Cách chạy lại kiểm thử M6
- Suite: `PYTHONUTF8=1 IFCFDS_SOLVER_AUTODISCOVERY=0 python -m pytest -q -m "not solver and not browser and not slow" -o faulthandler_timeout=90 -p no:cacheprovider`.
- Solver HVAC (Windows): đặt `PATH` thêm `.deps/fds-6.11.1/firemodels/FDS6/bin/mpi` và `bin`, `IFCFDS_SOLVER=<fds_openmp.exe>`, `I_MPI_FABRICS=shm`, `OMP_NUM_THREADS=1`, rồi `python -m pytest -q -m solver tests/test_hvac_fds_pressure.py tests/test_hvac_junction.py tests/test_hvac_network.py`.
- Cổng nợ: `PYTHONUTF8=1 python scripts/quality/source_quality_budget.py --git-base <merge-base với origin/main>`; lưu ý cổng CI tính cả tệp mới (khác kết quả cục bộ ở 2.2).
