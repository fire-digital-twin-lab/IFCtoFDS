# P3c — IFC-bound vehicle orientation/provenance contract

## Phạm vi

P3c chỉ xác minh orientation cho `IFC_BOUND` vehicle trong **current axis-aligned OBST contract**. Đây là software verification/evidence-integrity scope, không phải CFD model validation hay application validation.

## Cơ sở IFC

Theo IFC4/IFC4.3, `IfcSweptAreaSolid.Position` có thể reposition resulting swept solid relative to object coordinate system. Vì vậy `IfcObjectPlacement` một mình không đủ để chứng minh hướng hình học của vehicle.

Reference:
- buildingSMART IFC4, `IfcSweptAreaSolid`: https://standards.buildingsmart.org/IFC/RELEASE/IFC4/FINAL/HTML/schema/ifcgeometricmodelresource/lexical/ifcsweptareasolid.htm
- buildingSMART IFC4.3, `IfcSweptAreaSolid`: https://standards.buildingsmart.org/IFC/DEV/IFC4_3/HTML/lexical/IfcSweptAreaSolid.html

## Acceptance contract

Một `IFC_BOUND` vehicle chỉ được xác nhận orientation khi tất cả điều kiện sau đúng:

1. Source entity có reviewed `semantic_role=VEHICLE`, `PASSIVE_OBSTACLE`, `review_status=APPROVED`.
2. Verified base representation là `OBST`.
3. Source placement provenance tồn tại và `status=CONFIRMED`.
4. Placement convention là metre, row-major matrix, column-vector convention.
5. `effective_world` là finite rigid homogeneous transform, orthonormal, determinant +1.
6. Không có tilt.
7. Không có mapped-item transforms; trường hợp này vẫn fail-closed.
8. Object placement yaw là quarter-turn world-axis: 0/90/180/270 độ.
9. Verified OBST footprint có một major horizontal axis rõ ràng; footprint gần vuông bị reject vì trục dọc ambiguous.
10. Trục X của object placement phải trùng với major horizontal axis của verified OBST:
    - yaw 0/180 => OBST dài theo world X;
    - yaw 90/270 => OBST dài theo world Y.
11. Nếu representation-item transform (ví dụ `IfcSweptAreaSolid.Position`) làm body axis khác ObjectPlacement, cross-check phải reject.

## Evidence

Code candidate: `7866d0f341779cef2f2c5e44d5e5c5f948d9b3d6`.

- Source quality #42389022580: PASS; 912 passed, 14 deselected, 113 warnings; coverage 87%.
- Source-quality artifact `13580833047`: `sha256:2a1842350cfa6e3417a4c03e47dfca80c1f7c442d902d0730fee9fa6e6c43e42`.
- Conversion #42389022590: PASS trên Linux/Windows Python 3.10–3.13, JavaScript, browser và pinned FDS.
- Solver artifact `13581090420`: `sha256:5339b3cd20fc60d6f4a0de2a7a6b4d660af67c9b342559f46e989afb8f743e83`.
- Browser artifact `13580847198`: `sha256:0b2bb244a0632159e3e67d209e40460ab15c34312b6a79d64d487a0fd5f38389`.
- Regression includes real IFC with ObjectPlacement yaw 0° and `IfcSweptAreaSolid.Position` rotating the body 90°; P3c must reject the orientation claim.
- Real IFC ObjectPlacement 90° round-trip through convert → sealed manifest → verified-base reload → scenario emission remains accepted when OBST major axis agrees.

## Scientific limitation

Verified OBST AABB proves only the **longitudinal axis modulo 180°**. It does not prove front-versus-rear heading. Therefore P3c evidence must not be used to authorize directional jet outlets, asymmetric front/rear source placement, or any claim requiring directed heading.

P3c also does not support arbitrary rotated GEOM vehicles, general representation-item composition, mapped-item composition, automatic native `IfcVehicle` classification, exact GEOM collision, post-snap/local MeshPlan clearance, grid sensitivity, EV fire physics, numerical verification, experimental validation, or application validation.

## Verdict

Scoped `EV-GEO-P3C-001`: **PASS / E2** after full final code-head CI.

Broad `EV-GEO-001`: **FAIL**.

Overall scientific/application verdict: **INCONCLUSIVE**.

Release verdict: **NOT_PRODUCTION_READY**.
