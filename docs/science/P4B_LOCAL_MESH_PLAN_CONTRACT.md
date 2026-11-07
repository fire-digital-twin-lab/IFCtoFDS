# P4b1 — Local MeshPlan không chồng lấn và source-local resolution evidence

**Trạng thái:** software/solver-integration verified candidate  
**Work package:** P4b1  
**Scoped claim:** `MESH-LOCAL-P4B1-001`  
**Không phải:** grid independence, solution verification, numerical uncertainty, model validation hoặc application validation.

## 1. Mục tiêu

P4a đã sửa semantics của D*/dx nhưng chưa có source-local mesh. P4b1 bổ sung một Local MeshPlan thuộc **scenario phase**, vì EV/burner chỉ tồn tại sau khi verified base mapping đã được seal.

Ownership được giữ tách bạch:

```text
verified base
  owns: geometry + accepted mapping + simulation domain

scenario
  owns: EV source + Local MeshPlan + refined MESH layout
```

P4b1 chỉ thay MESH records. Nó không sửa verified geometry, MappingPlan decisions hoặc sealed evidence của base.

## 2. Contract

### 2.1 Typed request

`LocalMeshPlanRequest` gồm:

- `source_vehicle_index`;
- `local_region`;
- `refinement_ratio >= 2`.

Local refinement chỉ áp dụng cho scientific vehicle geometry. `LEGACY` bị reject.

### 2.2 Coarse-lattice alignment

Requested local-region boundaries phải nằm trên verified coarse-grid lattice. Không snap im lặng từ arbitrary coordinate sang grid.

Base MESH phải chứng minh cùng một coarse lattice trước khi replacement được phép.

### 2.3 Non-overlapping layout

P4b1 decomposition gồm:

- left/right coarse shell;
- front/back coarse shell;
- below/above coarse shell;
- một local refined mesh.

Các vùng chỉ adjacent ở boundary, không interior overlap.

Domain coverage được kiểm bằng:

```text
Σ mesh box volume = simulation-domain volume
```

và pairwise interior-overlap check.

### 2.4 FDS-compatible effective region

Pinned FDS timestep test phát hiện một requested layout tạo coarse shell `IJK=(4,4,1)` và FDS dừng với:

```text
ERROR(426): Poisson initialization error, MESH 3
```

P4b1 không che lỗi này. Resolver nay fail-closed/normalize theo coarse lattice để tránh:

- local span chỉ 1 coarse cell;
- residual coarse shell chỉ 1 coarse cell.

Nếu cần, effective local region được **mở rộng**, không thu hẹp source envelope.

Mọi thay đổi được ghi:

```text
requested_local_region
local_region
boundary_adjustments[]
```

Ví dụ regression:

```text
requested z coarse index: 0..3
effective z coarse index: 0..4
boundary_adjustments:
  - "zmax coarse index expanded 3->4"
```

Đây là compatibility rule của scoped P4b1 đã được pinned FDS regression phát hiện; không được diễn giải như universal scientific mesh-resolution threshold.

### 2.5 Cell-count constraint của implementation

P4b1 kiểm mọi emitted nonempty mesh có ít nhất 2 cells mỗi trục trong các layout do resolver này sinh ra.

Local refined mesh hiện phải <= 500,000 cells. Đây là implementation/resource guard cho work package này, không phải scientific adequacy threshold.

### 2.6 Structured MESH replacement

MESH records được thay bằng parser `text_span`, không regex post-processing.

Sau replacement:

1. parse lại toàn scenario;
2. reject parser error/unsupported field;
3. đối chiếu emitted MESH IDs với resolved plan.

Default scenario không có `mesh_plan` giữ nguyên path cũ.

## 3. Source-local resolution lookup

`MeshResolutionChecker` giữ full MESH geometry.

Với mỗi burner:

1. tính burner centroid;
2. tìm MESH có centroid nằm **strictly bên trong**;
3. chỉ khi có đúng một match mới cấp source-local lookup evidence.

Khi thành công:

```text
cell_size_basis = BURNER_CENTROID_UNIQUE_MESH
local_source_mesh_resolved = true
local_mesh_id = ...
local_cell_size_xyz_m = [...]
```

Nếu centroid nằm trên mesh interface hoặc không có đúng một match:

```text
local_source_mesh_resolved = false
```

và checker không đoán một phía theo thứ tự MESH.

## 4. Scientific metrics được report

LocalMeshPlan evidence có thể ghi:

```text
dx_local_m
local_cell_size_xyz_m
D*
D*/dx_local
ground_clearance/dz_local
battery_thickness/dz_local
total_cells
refinement_ratio
```

`dx_local_m` trong scoped contract là maximum local XYZ spacing và evidence ghi:

```text
d_star_denominator = MAX_LOCAL_CELL_SPACING
```

D*/dx vẫn chỉ là indicator.

Không có threshold universal nào cho:

- D*/dx;
- cells across ground clearance;
- cells across battery thickness.

## 5. HRR provenance

Dùng chung `ev_peak_hrr_evidence()` từ fire domain.

Nếu peak HRR explicit:

```text
peak_hrr_basis = EXPLICIT_SELECTION
```

Nếu scenario emitter/current preset path cần midpoint của cited range:

```text
peak_hrr_basis = PRESET_RANGE_MIDPOINT_ASSUMPTION
peak_hrr_range_kw = [...]
preset_confidence = ...
preset_citations = [...]
```

Midpoint này không phải measured/validated truth.

## 6. Worker evidence

Scenario WorkerRunner persist:

- `local_mesh_plan`;
- `local_mesh_evidence`;
- normal mesh checker evidence;
- scenario FDS.

Worker E2E kiểm chính emitted `scenario.fds` và xác nhận burner được resolve tới refined MESH.

## 7. Pinned FDS solver evidence

Solver test dùng FDS 6.11.1 thực và:

- `T_END=0.1 s`, không chấp nhận setup-only;
- yêu cầu return code 0;
- yêu cầu `completed successfully`;
- reject `ERROR:`;
- persist JSON + stdout/stderr logs;
- persist SHA-256 của input/stdout/stderr;
- persist warning count/lines.

Final code-head:

```text
df51ff056f2d33f2a179ffe719697fe5694b30ee
```

Source Quality:

```text
run #42408013138
935 passed
15 deselected
121 warnings
coverage 87%
artifact 13588337635
sha256:8a007e1f2ef5f8c91152613d43df2ec42305a0f8dd4376ef0c02ab9ae86c69fa
```

Conversion:

```text
run #42408013221
Linux/Windows Python 3.10–3.13 PASS
JavaScript PASS
browser PASS
pinned FDS PASS
solver: 10 passed, 940 deselected
solver artifact 13588546447
sha256:04d6f3609ea5a2d759f43984bf7877a0ca7df31fb066b6abf8a2e6c11ccf8e5e
browser artifact 13588810318
sha256:405eff9b55476823a9e2e209060970534a78a46ddeb8de969c5861a69039bca1
```

## 8. Remediation history

CI/audit đã phát hiện và sửa, không hạ gate:

1. new import debt;
2. `mesh_plan.py` god module;
3. resolver lại vượt 300 dòng sau Poisson remediation;
4. dùng sai `SolverResolution` như Path;
5. setup-only `T_END=0.0`;
6. FDS Poisson failure do one-cell coarse shell;
7. solver evidence ban đầu chỉ hash log tạm, chưa persist stdout/stderr.

Tất cả được sửa ở root cause.

## 9. Scoped verdict

```text
MESH-LOCAL-P4B1-001 = PASS / E2
```

PASS chỉ bao phủ:

- typed request/domain model;
- deterministic adjacent non-overlap layout;
- coarse-lattice alignment;
- explicit requested→effective boundary adjustments;
- structured MESH replacement;
- source-local burner→mesh lookup;
- WorkerRunner persisted evidence;
- pinned FDS timestep acceptance của regression layout.

## 10. Broad claim vẫn chưa đạt

```text
MESH-LOCAL-001 = INCONCLUSIVE
```

P4b1 **không** chứng minh:

- coarse/medium/fine convergence;
- grid independence;
- numerical uncertainty;
- sensitivity của temperature, visibility, heat flux, activation time, species hoặc ASET;
- application-specific mesh adequacy;
- EV fire predictive validity.

Work package kế tiếp phải là P4c grid-sensitivity/solution-verification, không được nhảy sang P6 EV physics.
