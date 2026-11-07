# P3d — Exact GEOM collision contract from sealed FDS

## Phạm vi

P3d xác minh separation/collision giữa vehicle body dạng axis-aligned AABB của current scientific scenario contract và **GEOM thực đã emit trong verified base FDS**.

Đây là software verification/evidence-integrity scope. P3d không phải CFD model validation, EV fire physics validation hay application validation.

## Cơ sở hình học

Triangle/AABB narrow phase dựa trên Separating Axis Theorem (SAT) theo Tomas Akenine-Möller, *Fast 3D Triangle-Box Overlap Testing*:

- https://fileadmin.cs.lth.se/cs/Personal/Tomas_Akenine-Moller/pubs/tribox.pdf
- DOI: 10.1080/10867651.2001.10487535

SAT triangle/AABB dùng 13 axes:
1. ba AABB face normals;
2. triangle face normal;
3. chín cross-product axes giữa ba AABB axes và ba triangle edges.

Implementation P3d không dùng floating distance epsilon cho 13-axis SAT. Tọa độ binary64 đã parse được chuyển thành exact rational values trước projection. Vì vậy kết quả SAT là chính xác đối với chính các binary64 input đã seal trong artifact.

## Tại sao dùng emitted FDS GEOM

Collision không được kiểm bằng source IFC mesh rồi giả định source mesh bằng FDS representation. Boundary treatment hoặc representation policy có thể làm emitted geometry khác source geometry.

Verified scenario-base loader vì vậy:
1. xác minh bundle/report/evidence index như trước;
2. kiểm FDS SHA-256 với sealed manifest;
3. parse chính `model.fds`;
4. đối chiếu từng GEOM ID với:
   - FDS source `entity_key`;
   - `ManifestRecord.fds_primitive_ids`;
   - `manifest.primitive_to_ifc`;
5. reject missing/extra/mismatched GEOM;
6. reconstruct exact emitted triangle mesh từ `VERTS/FACES`.

Legacy `load_verified_base()` vẫn giữ tuple ba giá trị; worker scientific scenario dùng typed `VerifiedScenarioBase`.

## Clearance contract

Tolerance hiện tại: **1e-4 m**.

Vehicle AABB được nở thêm 1e-4 m theo cả sáu hướng. Mỗi phép cộng/trừ sau đó được `nextafter` làm tròn hướng **ra ngoài**. Do đó binary64 rounding không thể vô tình thu nhỏ vùng rejection.

Đây là một conservative axis-expanded envelope:
- nếu GEOM chạm/intersect envelope: FAIL;
- nếu GEOM nằm ngoài envelope: chứng minh Euclidean clearance lớn hơn 1e-4 m;
- một số điểm ở diagonal corner có thể cách Euclidean hơn 1e-4 m nhưng vẫn nằm trong axis-expanded envelope, nên FAIL có thể bảo thủ; PASS không overclaim.

## Narrow-phase contract

Với GEOM có AABB overlap/touch vehicle AABB:

1. GEOM exact evidence bắt buộc phải có từ sealed FDS.
2. GEOM phải là valid solid.
3. Self-intersection CONFIRMED => không được dùng làm collision evidence.
4. Self-intersection UNCERTAIN => INCONCLUSIVE.
5. Vectorized triangle AABB chỉ là broad phase để chọn candidate triangles.
6. Mỗi candidate chạy exact-rational 13-axis SAT với outward-expanded vehicle AABB.
7. Boundary contact được xem là clearance violation.
8. Nếu không triangle nào intersect nhưng expanded vehicle box có thể nằm hoàn toàn trong GEOM, reviewed solid-boolean intersection kiểm containment.
9. Boolean backend unavailable => INCONCLUSIVE, không fallback AABB.

GEOM có disjoint AABB vẫn PASS bằng AABB separation proof; không cần narrow phase.

OBST behavior không đổi.

## Evidence

Code candidate: `834bad73e218a171329293fe2567c9e3f13c1212`.

- Source quality #42391766635: PASS.
- Full Python: **924 passed, 14 deselected, 117 warnings**, coverage **87%**.
- Source-quality artifact `13581603383`: `sha256:ccde0618a8057504e53f797abd4255755c3d053572593ff33b7d50c01e148c94`.
- Conversion #42391766582: PASS trên Linux/Windows Python 3.10–3.13, JavaScript, browser và pinned FDS.
- Solver artifact `13582350222`: `sha256:c67a206755b4cc767d99d2619cfe06d3d73fc5247a92aa47205dbd1905d7a013`.
- Browser artifact `13581782426`: `sha256:be40c96b6f513790603068c5df12b34174769bb8f920faf2a21fe4a50e0a1b07`.

Regression evidence gồm:
- boundary contact;
- adjacent binary64 plane ngay ngoài AABB;
- degenerate triangle;
- outward-rounding;
- AABB overlap nhưng tetrahedron thực sự separated;
- sub-tolerance separation;
- full containment;
- missing exact GEOM evidence;
- worker E2E với real converted `all_geom=True` base, seal/save/reload emitted GEOM rồi reject true collision bằng exact evidence.

## Giới hạn khoa học

P3d chỉ chứng minh collision/separation của current **axis-aligned vehicle body AABB** với sealed emitted GEOM/OBST.

P3d chưa chứng minh:
- arbitrary rotated vehicle OBB hoặc arbitrary GEOM vehicle body;
- front/rear heading;
- local/post-snap MeshPlan clearance;
- grid sensitivity;
- jet/outlet geometry;
- battery-to-building detailed collision beyond current body/battery source exclusions;
- EV fire physics;
- numerical verification;
- experimental validation;
- application validation.

## Verdict

Scoped `EV-GEO-P3D-001`: **PASS / E2** after full code-head CI.

Broad `EV-GEO-001`: **FAIL**.

Overall scientific/application verdict: **INCONCLUSIVE**.

Release verdict: **NOT_PRODUCTION_READY**.
