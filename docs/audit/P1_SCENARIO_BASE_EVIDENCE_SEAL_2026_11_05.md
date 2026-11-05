# P1 — Niêm phong evidence của mô hình nền trước khi phát EV scenario

**Ngày:** 05/11/2026. **Finding:** `SCI-BASE-01` trong `FULL_REASSESSMENT_2026_11_05.md`.

## Lỗ hổng đã quan sát ở mã

`application/services/scenario_base.py::load_verified_base` trước đây kiểm tra manifest bundle SHA, mapping status, report finalize, FDS byte hash và geometry package. Tuy nhiên nó không bắt buộc `result_evidence.json` phải tồn tại và không đối chiếu report/result/checkpoint với mọi digest trong index. Vì vậy, một report được chỉnh sửa nhưng vẫn giữ verdict hợp lệ có thể được dùng lại làm mô hình nền EV, dù đường đọc result bình thường đã từ chối evidence bị thay đổi.

## Invariant mới

- Application cần một callback `verify_candidate` rõ ràng, **bắt buộc** để tải mô hình nền; không phụ thuộc trực tiếp vào adapter (giữ đúng Hexagonal).
- Adapter `base_integrity.py` xác minh public convert result contract, `MAPPING_VERIFIED` ở mapping status, `output_complete=true` và `verify_evidence_index`.
- Index phải ghi đầy đủ `result.json`, FDS, manifest, acceptance report, geometry package, `audit-state.json`. Checkpoint phải khai báo `VERIFIED_SEALED`, mapping status verified và bundle hash khớp manifest.
- Worker EV bắt buộc cung cấp adapter verifier khi gọi `load_verified_base`. Không tạo fallback building/physics.
- `tests/test_scenario_integrity.py` có control base hợp lệ, giả mạo FDS, báo cáo thêm byte whitespace, thiếu index, thiếu indexed checkpoint, và manifest bị hạ output_complete.

## Giới hạn

SHA-256 index chỉ chứng minh các byte đã công bố không thay đổi so với index. Người có quyền ghi lại toàn bộ thư mục vẫn có thể sửa cả artifact lẫn index; cần provenance ký số hoặc immutability từ storage trong production. Đây không phải independent CFD validation và không chứng minh physical safety. G09/G10 vẫn `INCONCLUSIVE`. Không nâng `SIMULATION_VERIFIED`.

Chỉ merge sau khi required checks trên HEAD cuối thành công. Không thay đổi tolerance, solver, geometry engine hay quyết định golden reference.
