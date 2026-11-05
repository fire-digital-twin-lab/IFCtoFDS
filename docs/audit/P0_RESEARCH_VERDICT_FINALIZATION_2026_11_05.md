# P0 — Không công bố research acceptance trước khi verdict khoa học được finalize

**Thời điểm kiểm tra:** 05/11/2026. **Trạng thái:** bản vá chờ nghiệm thu CI; không phải giấy chứng nhận thực nghiệm hay kết quả mô phỏng CFD.

## P0-SCI-RESEARCH: Research status có nguy cơ phản ánh verdict trung gian

**Luồng trước sửa:**
1. `run_independent_validation` khởi tạo và finalize report trên các gate ánh xạ ban đầu.
2. `apply_independent_source_integrity`, `apply_mep_and_coverage` và `golden_gate` thay đổi gate/trạng thái khoa học.
3. `research_context(... report.model_dump())` lấy `mapping_status` **trước khi** `finalize` lại report sau golden.
4. Final report có thể `mapping_status=INCONCLUSIVE/REJECTED` trong khi `report.configuration.research.research_acceptance` còn giữ `MAPPING_VERIFIED` từ lần tổng hợp cũ.

Trường hợp dễ tái hiện: profile `research-basement` không có golden reference APPROVED. `golden_reference_parity=INCONCLUSIVE` là kết luận chính xác, research acceptance phải `INCONCLUSIVE`, không được quảng bá mapping verified cũ.

**Sửa:** finalization sau tất cả source integrity / MEP / golden gates; chỉ sau đó mới tính `research_context`. Không nâng status hay tự cấp approved reference.

**Kiểm thử:** `tests/test_scientific_verdict_fail_closed.py::test_research_acceptance_uses_finalized_independent_audit_verdict`, kiểm tra cả control mapping hợp lệ và research case thiếu golden reference.

## Ranh giới nghiệm thu khoa học

- `MAPPING_VERIFIED` chỉ áp dụng đối chiếu ánh xạ BIM→FDS trên 12 core mapping gates + các gate required khác; không phải `SIMULATION_VERIFIED`.
- `research_acceptance` là thông tin phản ánh mapping verdict đã finalize cho profile nghiên cứu, **không phải** phê duyệt an toàn cháy.
- `solver` CI kiểm tra FDS pinned/boundary fixtures; chưa có benchmark thực nghiệm đáng tin cậy, phân tích hội tụ, uncertainty, calibration và phê duyệt kỹ sư.
- `EVIDENCE_VALID` của persisted audit chỉ kiểm tra consistency và hash; không xác nhận giá trị khoa học của kết quả.
- Gate G09/G10 vẫn `INCONCLUSIVE`; G11/G13/G15 `NOT_RUN`. Production vẫn `NOT_PRODUCTION_READY`.

## Acceptance gate cho PR

- Required Linux/Windows Python 3.10–3.12, browser, JavaScript, solver PASS trên **HEAD cuối**.
- Unit test xác minh research status không giữ verdict cũ khi golden gate đổi thành INCONCLUSIVE.
- Không đổi IFC/FDS raw artifact, tolerance, solver binary, dữ liệu tham chiếu, approval người dùng hay simulated evidence.
- Chỉ merge PR bình thường sau khi GitHub báo clean. Không bypass branch protection.
