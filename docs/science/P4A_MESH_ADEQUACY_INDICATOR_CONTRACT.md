# P4a — Hợp đồng chỉ số mesh adequacy và tách solver evidence

**Trạng thái:** software-verified candidate  
**Work package:** P4a  
**Claim scoped:** `MESH-INDICATOR-P4A-001`  
**Không phải:** Local MeshPlan, solution verification, grid independence, model validation hoặc application validation.

## 1. Vấn đề được sửa

Checker trước P4a dùng `4 <= D*/dx <= 16` như một acceptance range:

- `D*/dx < 4` → `FAIL`;
- `4 <= D*/dx <= 16` → `PASS`;
- `D*/dx > 16` → `INCONCLUSIVE` với diễn giải “too fine”.

Cách dùng này không được coi là scientific acceptance rule của dự án.

FDS Validation Guide định nghĩa `D*/dx` là **Plume Resolution Index** và lưu ý các validation studies sử dụng một dải rộng; khi viện dẫn validation studies, physical và numerical parameters phải tương đồng với application. Bảng hiện hành chứa các case thấp khoảng 1–3 và cao tới khoảng 118, vì vậy một khoảng lịch sử hẹp không thể tự động trở thành universal minimum/maximum.

FDS maintainer cũng đã làm rõ rằng các giá trị lịch sử không phải “acceptable minimum” và grid adequacy phải được đánh giá theo grid-resolution/sensitivity study của bài toán cụ thể.

## 2. Nguồn tham chiếu

1. NIST/FDS, **FDS 6.11.1 Validation Guide**, current manuals page:
   - https://pages.nist.gov/fds/manuals.html
2. FDS Validation Guide source, `Experiment_Chapter.tex`, mục numerical parameters:
   - https://github.com/firemodels/fds/blob/master/Manuals/FDS_Validation_Guide/Experiment_Chapter.tex
3. firemodels/fds issue #11269, maintainer clarification về việc không dùng các giá trị D*/dx của validation table như acceptable minimum:
   - https://github.com/firemodels/fds/issues/11269

Các nguồn trên được dùng để sửa **semantics của checker**. Chúng không tự cấp validation cho IFCtoFDS.

## 3. Contract sau P4a

### 3.1 D*/dx

Với positive-fire case:

- D* vẫn được tính và lưu làm evidence;
- `D*/dx` vẫn được tính và lưu;
- `indicator_band` chỉ mô tả vị trí so với historical subset 4–16:
  - `BELOW_HISTORICAL_4_16_SUBSET`;
  - `WITHIN_HISTORICAL_4_16_SUBSET`;
  - `ABOVE_HISTORICAL_4_16_SUBSET`;
- mọi band trên đều **không** phải acceptance rule;
- `historical_4_16_is_acceptance_rule = false`;
- `grid_sensitivity_required = true`;
- mesh gate giữ `INCONCLUSIVE` cho đến khi có evidence solution verification phù hợp.

Không còn đường fallback nào tạo P1/P2 finding chỉ vì D*/dx nằm ngoài 4–16.

### 3.2 Critical EV geometry metrics

Khi scenario evidence có geometry tương ứng, checker báo:

- `ground_clearance_m`;
- `ground_clearance_over_dx`;
- `battery_thickness_m`;
- `battery_thickness_over_dx`.

P4a **không đặt threshold PASS mới** cho các tỷ số này vì chưa có reviewed scientific decision/source để chứng minh universal threshold.

### 3.3 Provenance của dx

P4a không giả vờ đã có local source resolution.

Direct helper ghi:

```text
cell_size_basis = CALLER_SUPPLIED_UNVERIFIED_LOCALITY
local_source_mesh_resolved = false
```

Khi checker đọc FDS multi-mesh hiện tại, nó dùng conservative global maximum spacing và ghi:

```text
cell_size_basis = GLOBAL_MAX_MESH_SPACING_NOT_SOURCE_LOCAL
local_source_mesh_resolved = false
```

Các basis khác cũng được gắn nhãn tường minh nếu cell size đến từ configuration hoặc legacy default.

Local `dx` tại EV source chỉ được phép xuất hiện sau P4b khi MeshPlan có source-local mesh ownership/lookup được kiểm thử.

### 3.4 Provenance của HRR

Nếu EV selection cung cấp peak HRR tường minh:

```text
peak_hrr_basis = EXPLICIT_SELECTION
```

Nếu checker phải dùng midpoint của preset range để khớp với scenario emitter hiện hành, evidence bắt buộc ghi:

```text
peak_hrr_basis = PRESET_RANGE_MIDPOINT_ASSUMPTION
peak_hrr_range_kw = [...]
preset_confidence = ...
preset_citations = [...]
```

Không được biến midpoint này thành measured/validated value.

Nonfinite HRR hoặc invalid/nonfinite cell size bị reject.

## 4. Solver evidence tách khỏi mesh adequacy

P4a phân biệt hai claim:

1. **Solver integration:** pinned FDS có chạy/accept input hay không.
2. **Mesh adequacy:** grid có đủ để giải bài toán khoa học hay không.

Vì vậy:

- syntax/topology blocker vẫn có thể làm solver `NOT_RUN`;
- `mesh_resolution = INCONCLUSIVE` không tự chặn solver execution;
- solver có thể `PASS` integration đồng thời evidence ghi `mesh_adequacy_status = INCONCLUSIVE`;
- solver PASS không được nâng mesh adequacy lên PASS.

Cả independent validation engine và checker-based ValidationRunner dùng cùng semantics này.

## 5. Regression evidence

Code candidate:

```text
ffe9d7ed519028a68ce8aa35ecf5530fcf8edfcd
```

Source quality run:

```text
#42403923771
926 passed
14 deselected
117 warnings
coverage 87%
artifact 13587020449
sha256:a8d5add592ecb6431cd98c31effda642e2ab80ecac7c147f6b6f410f1ae29aab
```

Conversion run:

```text
#42403923594
Linux/Windows Python 3.10–3.13 PASS
JavaScript PASS
browser PASS
pinned FDS solver PASS
solver artifact 13586344048
sha256:d27dea30722b310a72cae6d3ed752bb134b86378aea00fc46899b4f9a3463f69
browser artifact 13586059568
sha256:ac78e95294343660e4ed4d25cd8954bffe943560a19f97fa993e4ace1adfc18e
```

CI trong quá trình remediation đã bắt bốn regression contract/parity; chúng được sửa ở root cause hoặc cập nhật như intentional semantic change. Không thay golden để che lỗi và không khôi phục hard gate 4–16.

## 6. Verdict và giới hạn

### Scoped P4a

```text
MESH-INDICATOR-P4A-001 = PASS / E2
```

PASS này chỉ có nghĩa software contract đã được kiểm thử:

- D*/dx không còn là universal acceptance threshold;
- critical geometry cell-count evidence được report khi có dữ liệu;
- provenance HRR/dx được ghi rõ;
- solver integration được tách khỏi mesh adequacy;
- hai validation paths nhất quán.

### Broad mesh claim

```text
MESH-LOCAL-001 = INCONCLUSIVE / E0
```

Vẫn thiếu:

- typed Local MeshPlan;
- source-local mesh lookup;
- non-overlapping refined mesh layout được solver-verified;
- post-snap clearance/battery resolution evidence;
- coarse/medium/fine grid sensitivity;
- comparison metrics như temperature, visibility, heat flux, activation time, species concentration, ASET;
- numerical uncertainty;
- domain-of-applicability review.

P4a không phải solution verification và không cấp `SIMULATION_VERIFIED`.
