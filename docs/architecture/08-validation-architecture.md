# 08 — Kiểm chứng độc lập

AuditConversionUseCase nhận ModelPreparationPort và ValidationEnginePort. Reader chạy reference=True, mở lại IFC và dựng reference geometry; không lấy mesh đã sửa hoặc converter cache làm bằng chứng độc lập.

FDS/manifest được đọc lại từ checkpoint. Geometry package được kiểm tra nội dung/hash; graph MEP đã lưu đối chiếu quan hệ nguồn. Boundary acceptance và reference parity hoàn thiện bằng chứng trước manifest cuối.

Adapter mặc định vẫn gọi `modules/verification/application/engine.py:run_independent_validation` và inject solver runner. `application/saved_evidence.py` sở hữu đánh giá checkpoint đã lưu; workflow giữ điều phối và thứ tự gates. Runner/checkers có trong application cùng module; protocol/evaluator thuộc domain. Chúng chưa thay thế đường chạy chính của toàn workflow.

Chỉ chuyển engine sau khi so findings, severity, element statuses, coverage, evidence, gates, report, manifest, boundary và reference. So vài counters/status tổng là chưa đủ. Không bỏ gate hoặc dùng lại dữ liệu converter để đạt parity.

NOT_RUN là chưa chạy; INCONCLUSIVE là thiếu bằng chứng; FAIL/REJECTED là vi phạm được ghi nhận. MAPPING_VERIFIED không phải SIMULATION_VERIFIED. Solver lỗi phải giữ reason/evidence, không tự chuyển thành PASS. Boundary certificate gắn với mã adapter/executable; thay mã cần tái chứng nhận.
