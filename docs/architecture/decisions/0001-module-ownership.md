# ADR 0001 — Module ownership và mô hình dùng chung

Trạng thái: áp dụng trong đợt tổ chức mã sau tài liệu 13, ngày 22/10/2026.

## Quyết định

Giữ 4 context BIM, Simulation, Verification, Reference và 4 capability Geometry, FDS, Artifacts, Jobs. Bên trong module, folder thể hiện trách nhiệm; chỉ tạo folder khi có code thật. Các lời gọi pipeline tiếp tục đồng bộ. Không thêm broker hoặc bus để tổ chức thư mục.

Model Pydantic vẫn định nghĩa một lần tại `ifc_to_fds/domain`; `domain/contracts.py` chỉ re-export. Vị trí định nghĩa và JSON schema không được thay để tạo ranh giới hình thức. Chưa tách CanonicalModel thành các model độc lập.

| Dữ liệu/trường | Owner cập nhật theo stage |
| --- | --- |
| SourceIdentity, SourceMetadata, GlobalId, STEP ID, original filename/hash, native units/placement, MEP nguồn | BIM ingestion |
| ScopeDecision, mapping_strategy, simulation_role, representation bounds, boundary intent | Simulation preparation |
| Primitive IDs, FDS representation, primitive-to-IFC index, serialized manifest | FDS serialization |
| Geometry evidence payloads, hash/index và lifetime của lazy meshes | Geometry storage; Artifacts giữ lifetime/checkpoint |
| Findings, gates, evidence, element statuses và coverage | Verification trên model đọc lại độc lập |
| Reference approval, integrity và parity evidence | Reference |
| QUEUED/RUNNING/COMPLETED/FAILED/CANCELLED/TIMED_OUT và retention | Jobs service dưới lock, persisted bởi store |

Model hiện vẫn mutable. Bảng này là quyền sở hữu theo workflow, không phải chứng minh immutability được thực thi. Không dùng converter cache/model đã sửa làm reference audit.

## Dependency

Policy thực thi nằm tại [dependency-policy.json](../dependency-policy.json); facade registry tại [compatibility-imports.json](../compatibility-imports.json). Tests kiểm tra import tuyệt đối/tương đối, API exports, hướng phụ thuộc và checksum của các facade được review.

Verification có thêm cạnh công khai tới BIM để dùng `graph_differences` khi kiểm tra MEP được đọc lại. Cạnh này đã có về nghĩa trong audit workflow cũ; chuyển owner rule về Verification làm nó hiện rõ. BIM chỉ phụ thuộc Geometry nên không tạo cycle. Không dùng cạnh này để cho Verification mở native source thay workflow.

## Bốn bridge tương thích

1. Direct constructor `JobService()` chọn local defaults qua factory; production bootstrap inject repository/process/retention.
2. Function `run_independent_validation()` giữ solver default cho caller cũ; production engine adapter inject solver_runner.
3. `golden_gate()` giữ mặc định đọc case cho caller cũ; production workflow inject case_reader.
4. Boundary policy re-export `adapter_digest` cho caller cũ; digest implementation thuộc infrastructure.

Bridge là cặp source→target cụ thể, không miễn cả package. Caller mới dùng DI/contract. Không gỡ bridge trước khi cập nhật caller và kiểm tra compatibility. `results.py` cũng giữ delegation để override registry qua module cũ còn tác dụng; không sao chép logic research hoặc tạo thêm registry state.

## Các quyết định giữ ổn định

- Engine chính vẫn là `modules/verification/application/engine.py`; đường dẫn phẳng cũ là alias.
- Không đổi signature/schema/URLs để giống repository tham khảo. Tên `api.py`, classic scripts/IIFE và `file://` tiếp tục được hỗ trợ.
- Source hash/certificate bind implementation bytes; thay nội dung/import path đòi hỏi tạo chứng nhận mới, không giữ chứng nhận không còn đúng.
- Chưa có ngân sách hiệu năng được phê duyệt. Báo phép đo đối chứng; không tự đặt ngưỡng rồi tuyên bố nghiệm thu.
