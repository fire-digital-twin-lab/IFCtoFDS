# P3b — Collision gate giữa vehicle và verified base geometry

**Trạng thái:** `PASS / E2` trên code candidate `6ad904c7b5fb975968e856fa8bbc686b4b6b4d85`  
**Roadmap:** P3 — Vehicle identity & geometry  
**Claim:** `EV-GEO-P3B-001 = PASS / E2`  
**Claim tổng:** `EV-GEO-001` tiếp tục FAIL cho đến khi orientation/GEOM vehicle binding, post-snap/local mesh và application evidence hoàn tất.

## Vấn đề

P3a đã giải quyết identity, ground clearance và underbody source cho `PARAMETRIC` / `IFC_BOUND`, nhưng scenario vẫn chỉ kiểm va chạm giữa các vehicle trong cùng request. Một scientific vehicle vẫn có thể xuyên vào wall, column, door, MEP obstacle hoặc geometry nền khác mà không bị reject.

## Mục tiêu P3b

P3b bổ sung một collision gate tất định trên `MappingPlan` đã kiểm chứng:

- chỉ bật cho `PARAMETRIC` và `IFC_BOUND`;
- `LEGACY` giữ nguyên hành vi để bảo toàn compatibility;
- kiểm mọi base entity có `fds_representation=OBST|GEOM`;
- `IFC_BOUND` loại trừ đúng body source và battery source của chính vehicle;
- mọi source base khác, kể cả vehicle khác, vẫn phải được kiểm.

## Oracle hình học

### Base `OBST`

Với `OBST`, representation bounds chính là solid axis-aligned được serializer phát ra. P3b tính khoảng cách Euclidean giữa hai AABB:

- khoảng cách > `1e-4 m` → PASS cho cặp đó;
- khoảng cách <= `1e-4 m` → reject collision/contact.

Quy tắc này cố ý reject cả zero-clearance contact. Ground/floor hợp lệ vẫn PASS nếu vehicle có positive vertical clearance.

### Base `GEOM`

MappingPlan hiện chỉ có bounding box, không có exact triangle mesh để chạy intersection oracle trong scenario emitter.

Vì vậy:

- AABB tách rời → đủ để chứng minh geometry thực cũng tách rời;
- AABB overlap/touch → **INCONCLUSIVE và reject fail-closed**, không được suy đoán là safe.

P3b không được đổi `GEOM` overlap thành PASS bằng heuristic.

## Bằng chứng machine-readable

Mỗi scientific vehicle sinh `VehicleCollisionAssessment`:

- vehicle index / geometry mode;
- entity keys được loại trừ;
- số base OBST/GEOM đã kiểm;
- nearest entity key;
- minimum AABB clearance;
- tolerance;
- method và status.

Worker chỉ thêm `vehicle_collision_assessments` vào scenario evidence khi scientific collision gate thực sự chạy. Legacy result không tự thêm evidence field mới.

## Regression bắt buộc

- Legacy overlap với base geometry không bật P3b.
- Parametric vehicle tách khỏi OBST → PASS + minimum clearance.
- Parametric overlap/touch OBST → reject.
- Vertical clearance trên floor-like OBST → PASS.
- GEOM AABB overlap/touch → reject INCONCLUSIVE.
- GEOM AABB tách rời → PASS.
- IFC-bound loại trừ own vehicle + battery source.
- IFC-bound vẫn reject collision với source body khác.
- Missing bounds trên emitting base entity → fail-closed.
- Worker E2E với IFC thật phải lưu collision evidence.

## Non-goals

P3b **không** chứng minh:

- exact collision cho GEOM khi AABB overlap;
- rotated/non-axis-aligned vehicle orientation fidelity;
- automatic native IfcVehicle classification;
- post-snap clearance trên FDS mesh;
- local MeshPlan/grid sensitivity;
- EV fire physics hoặc application validation.

Các hạng mục đó thuộc P3c/P4/P6.

## Rollback

Revert P3b commits. `LEGACY` không đổi contract; scientific scenario sẽ trở về trạng thái P3a không có base-geometry collision gate.

## CI và bằng chứng

Code candidate: `6ad904c7b5fb975968e856fa8bbc686b4b6b4d85`.

- Source quality #42382470834: **SUCCESS**, `889 passed, 14 deselected`, coverage **87%**.
- Source-quality artifact `13578780011`, digest `sha256:43ea31cc163100cd89c61a7b711cac5ca597b84c4cdde44005871f62829c71f1`.
- Conversion #42382470941: **SUCCESS** cho Linux/Windows Python 3.10–3.13, JavaScript, browser và pinned FDS.
- Solver job: **9 passed, 894 deselected**.
- Solver artifact `13577534013`, digest `sha256:b1575008ebed1e2d3694e25b50dcf3cc1e930a839ba6d45013a614702f5eb6b4`.
- Worker E2E tạo verified base từ IFC thật gồm hai wall tách rời và xác nhận collision assessment được persist trong scenario evidence.

Bằng chứng này chỉ là software/solver-integration verification E2. Solver PASS không biến collision gate thành numerical verification hoặc application validation.

## Verdict hiện tại

`EV-GEO-P3B-001 = PASS / E2` cho đúng phạm vi AABB separation/fail-closed GEOM contract ở trên.

`EV-GEO-001 = FAIL` vẫn giữ nguyên vì orientation, exact GEOM collision khi AABB overlap, jet outlets, post-snap/local MeshPlan và application evidence chưa hoàn tất.

PR final HEAD và hậu-merge `main` vẫn phải PASS CI trước khi checkpoint P3b được coi là đóng hoàn toàn.
