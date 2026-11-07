# P3b — Collision gate giữa vehicle và verified base geometry

**Trạng thái:** implementation candidate, chờ CI/solver regression trên PR P3b  
**Roadmap:** P3 — Vehicle identity & geometry  
**Claim dự kiến:** `EV-GEO-P3B-001` ở mức E2 nếu toàn bộ gate PASS  
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

## Verdict hiện tại

Chưa cấp PASS trước khi CI hoàn tất. P3b candidate chỉ được nâng thành `PASS / E2` khi regression, full CI và main post-merge evidence cùng PASS.
