# Kiểm chứng độc lập

Đánh giá nguồn đọc lại và đầu ra đã lưu, gates/findings/evidence và boundary certification.

## Tổ chức

application/engine.py vẫn là engine active. saved_evidence.py giữ đúng thứ tự các gate overrides và coverage từ workflow cũ. Runner/checkers chưa thay thế engine. infrastructure/fds/ chạy executable; engine adapter inject solver_runner.

| File/package | Vai trò |
| --- | --- |
| `api.py` | API công khai |
| `application/boundary_acceptance.py` | Implementation nội bộ |
| `application/boundary_certification.py` | Implementation nội bộ |
| `application/checkers/air_path.py` | Implementation nội bộ |
| `application/checkers/boundary.py` | Implementation nội bộ |
| `application/checkers/domain.py` | Implementation nội bộ |
| `application/checkers/geometry.py` | Implementation nội bộ |
| `application/checkers/mep.py` | Implementation nội bộ |
| `application/checkers/openings.py` | Implementation nội bộ |
| `application/checkers/representation.py` | Implementation nội bộ |
| `application/checkers/scope.py` | Implementation nội bộ |
| `application/checkers/solver.py` | Implementation nội bộ |
| `application/checkers/structural.py` | Implementation nội bộ |
| `application/checkers/syntax.py` | Implementation nội bộ |
| `application/checkers/traceability.py` | Implementation nội bộ |
| `application/effective_obstructions.py` | Implementation nội bộ |
| `application/engine.py` | Implementation nội bộ |
| `application/runner.py` | Implementation nội bộ |
| `application/saved_evidence.py` | Implementation nội bộ |
| `contracts.py` | Hợp đồng công khai |
| `infrastructure/engine_adapter.py` | Implementation nội bộ |
| `infrastructure/fds/solver_process.py` | Implementation nội bộ |

## API và dependency

Caller ngoài module dùng `api.py` hoặc `contracts.py`. Export hiện có: `IndependentValidationEngine`, `ValidationRunner`, `assess_saved_evidence`, `calculate_bbox_iou`, `compare_solids`, `finalize_boundary`, `passage_metrics`, `run_independent_validation`, `verify_opening_retention`.

Module phụ thuộc: fds, geometry, simulation, bim. Hợp đồng model/schema dùng chung vẫn có một định nghĩa tại `domain/`.

## Ownership và tương thích

Không sửa IFC nguồn, không clone model/mesh để truyền state, không tự nâng VERIFIED. Giữ source identity và checksum. Mutations theo stage được ghi trong [ownership](../../../docs/architecture/decisions/0001-module-ownership.md). File phẳng cũ là alias, không đặt implementation mới vào đó.

Các export lớp adapter/repository hiện có tiếp tục được hỗ trợ; caller mới ưu tiên capability/port và composition root. Ngoại lệ compatibility được liệt kê chính xác trong `docs/architecture/dependency-policy.json`.

## Kiểm tra

Chạy từ root: `python -m pytest tests/architecture tests/modules/verification -q`. Các kiểm tra xuyên workflow nằm trong `tests/workflows`, HTTP ở `tests/interfaces/http`; fixture/snapshot chuẩn giữ tại `tests/baseline`. Geometry, BIM và Verification còn được kiểm tra chung trong baseline/workflows.
