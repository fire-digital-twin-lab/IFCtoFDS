# Vòng đời job

Điều phối queue, supervision, cancel, timeout và retention cho worker local.

## Tổ chức

application/service.py nhận JobStore, WorkerProcesses, JobRetention và clock. tick() chạy một lượt supervision dưới RLock. factory.py nối SQLite/process/retention adapters; bootstrap gọi public factory.

| File/package | Vai trò |
| --- | --- |
| `api.py` | API công khai |
| `application/service.py` | Implementation nội bộ |
| `contracts.py` | Hợp đồng công khai |
| `factory.py` | Composition root |
| `infrastructure/retention.py` | Implementation nội bộ |
| `infrastructure/sqlite_repository.py` | Implementation nội bộ |
| `infrastructure/worker_process.py` | Implementation nội bộ |

## API và dependency

Caller ngoài module dùng `api.py` hoặc `contracts.py`. Export hiện có: `JobManager`, `JobRepository`, `JobService`, `create_job_manager`.

Module phụ thuộc: không có module khác. Hợp đồng model/schema dùng chung vẫn có một định nghĩa tại `domain/`.

## Ownership và tương thích

Không sửa IFC nguồn, không clone model/mesh để truyền state, không tự nâng VERIFIED. Giữ source identity và checksum. Mutations theo stage được ghi trong [ownership](../../../docs/architecture/decisions/0001-module-ownership.md). File phẳng cũ là alias, không đặt implementation mới vào đó.

Các export lớp adapter/repository hiện có tiếp tục được hỗ trợ; caller mới ưu tiên capability/port và composition root. Ngoại lệ compatibility được liệt kê chính xác trong `docs/architecture/dependency-policy.json`.

## Kiểm tra

Chạy từ root: `python -m pytest tests/architecture tests/modules/jobs -q`. Các kiểm tra xuyên workflow nằm trong `tests/workflows`, HTTP ở `tests/interfaces/http`; fixture/snapshot chuẩn giữ tại `tests/baseline`. Geometry, BIM và Verification còn được kiểm tra chung trong baseline/workflows.
