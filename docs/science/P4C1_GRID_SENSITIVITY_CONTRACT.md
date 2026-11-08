# P4c1 — Hợp đồng grid-sensitivity coarse/medium/fine

**Trạng thái:** software-verified candidate  
**Work package:** P4c1  
**Scoped claim:** `MESH-SENS-P4C1-001`  
**Không phải:** mesh-independence proof, numerical-uncertainty estimate, model validation hoặc application validation.

## 1. Mục tiêu

P4c1 tạo hợp đồng phần mềm cho một nghiên cứu grid-sensitivity ba mức:

```text
COARSE → MEDIUM → FINE
```

Mục tiêu của vòng này là bảo đảm ba case **có thể so sánh đúng** và kết quả được mô tả có provenance, nhưng không biến một chuỗi ba giá trị thành scientific convergence PASS khi chưa có acceptance policy và uncertainty model đã được review.

## 2. Cơ sở khoa học

Nguồn chính:

1. NIST/FDS, FDS Validation Guide — Error Chapter:
   - https://github.com/firemodels/fds/blob/master/Manuals/FDS_Validation_Guide/Error_Chapter.tex
2. NIST/FDS, FDS Validation Guide — Plume Chapter:
   - https://github.com/firemodels/fds/blob/master/Manuals/FDS_Validation_Guide/Plume_Chapter.tex
3. FDS maintainer discussion về mesh/grid sensitivity:
   - https://github.com/firemodels/fds/discussions/11797

Các nguồn trên hỗ trợ các quyết định sau:

- discretization error là một thành phần của numerical error;
- detailed convergence analysis có thể hỗ trợ ước lượng discretization error;
- grid sensitivity phụ thuộc scenario và observable đang được hỏi từ mô hình;
- nhiều grid resolutions có thể được dùng để quan sát thay đổi prediction;
- convergence/grid sensitivity không tự giải quyết toàn bộ prediction uncertainty.

P4c1 vì vậy **không** hard-code ngưỡng 5%, 10% hoặc bất kỳ universal percentage nào.

## 3. Study-plan contract

`GridSensitivityPlanRequest` yêu cầu:

- đúng một `source_vehicle_index`;
- một reviewed `local_region`;
- đúng ba `refinement_ratios`;
- mỗi ratio >= 2;
- ratios tăng strictly từ COARSE → MEDIUM → FINE.

Resolver dùng chính P4b `resolve_local_mesh_plan()` để tạo ba Local MeshPlan.

Ba case chỉ được chấp nhận ở cấp software plan khi:

- thứ tự case là COARSE/MEDIUM/FINE;
- refinement ratio tăng strictly;
- local dx giảm strictly;
- effective local region của ba plan giống nhau;
- mỗi plan có SHA-256 canonical riêng.

## 4. Scenario invariance

P4c1 tính:

```text
scenario_invariant_sha256 = SHA256(pre-mesh scenario FDS)
```

Fingerprint này khóa exact scenario **trước khi** MESH được thay đổi.

`render_grid_sensitivity_cases()` reject nếu scenario text đã thay đổi sau khi plan được resolve.

Mỗi case FDS được sinh từ cùng một invariant source bằng `apply_local_mesh_plan()`, vì vậy thay đổi có chủ đích ở P4c1 chỉ nằm ở MESH layout.

Case FDS phải có ba SHA-256 khác nhau; nếu không, study plan bị reject.

## 5. Observable contract

Mỗi `GridSensitivityObservation` bắt buộc có:

- `metric_id`;
- `quantity`;
- `unit`;
- scalar `value`;
- `aggregation`: POINT / MAX / MIN / MEAN / FINAL / TIME_TO_THRESHOLD / INTEGRAL;
- optional `location_m`;
- optional `time_window_s`;
- `source_artifact`;
- `source_sha256`.

Ba case phải có cùng tập `metric_id`.

Với một metric, metadata phải giống nhau giữa COARSE/MEDIUM/FINE:

- quantity;
- unit;
- aggregation;
- location;
- time window.

Nếu metadata khác, analysis reject thay vì so sánh các đại lượng không tương đương.

## 6. Descriptive analysis

P4c1 tính cho từng metric:

- signed COARSE→MEDIUM delta;
- signed MEDIUM→FINE delta;
- absolute deltas;
- relative-to-finer change khi denominator khác 0;
- trend:
  - `FLAT`;
  - `MONOTONIC`;
  - `OSCILLATORY`;
  - `PLATEAU_OR_UNRESOLVED`;
- change-magnitude trend:
  - `DECREASING_CHANGE`;
  - `INCREASING_CHANGE`;
  - `UNCHANGED_CHANGE_MAGNITUDE`.

Relative change dùng:

```text
abs(finer - coarser) / abs(finer)
```

Nếu finer value bằng đúng 0:

```text
relative_change = null
```

Không dùng epsilon ẩn để tạo một denominator giả.

## 7. Fail-closed scientific verdict

Kết quả P4c1 luôn ghi:

```text
status = INCONCLUSIVE
comparison_status = COMPARABLE
acceptance_policy = NOT_DEFINED
numerical_uncertainty_status = NOT_ESTIMATED
```

Điều này là intentional.

Pairwise deltas và trend không đủ để chứng minh:

- asymptotic convergence;
- grid independence;
- observed order of accuracy;
- Richardson extrapolation applicability;
- Grid Convergence Index;
- numerical uncertainty;
- application-specific mesh adequacy.

## 8. Regression evidence

Code candidate:

```text
f28f8846c17dfc4952f3862d6ef4dabf6c0a7cd2
```

Source Quality:

```text
run #42450794968
945 passed
15 deselected
121 warnings
coverage 87%
artifact 13605856905
sha256:9553d7784611eb54ce27d09753da6c4e323424fa16574090b857a47f87aadeab
```

Conversion:

```text
run #42450791576
Linux/Windows Python 3.10–3.13 PASS
JavaScript PASS
browser PASS
pinned FDS PASS
solver: 10 passed, 950 deselected
solver artifact 13605681774
sha256:c9bca00d25733a1bcdf622becdde33ea1790f685c730395d123b9d2a5a896f33
browser artifact 13605426706
sha256:51d583523d47c4c70f4dd9301e98170c8c5412c655a7ec39ef33e1db4818d18e
```

Regression P4c1 khóa:

- ratio ordering và minimum ratio;
- cùng effective local region;
- local dx giảm strictly;
- immutable pre-mesh scenario fingerprint;
- distinct rendered case hashes;
- parse-valid case FDS;
- monotonic/oscillatory descriptive trend;
- zero-denominator behavior không epsilon;
- non-mesh scenario drift rejection;
- observable metadata/unit drift rejection;
- verdict luôn INCONCLUSIVE.

## 9. Scoped verdict

```text
MESH-SENS-P4C1-001 = PASS / E2
```

PASS này chỉ bao phủ **software contract**:

- study plan ba mức;
- mesh-only scenario invariance;
- observable provenance/comparability;
- deterministic descriptive analysis;
- fail-closed scientific semantics.

## 10. Broad claim vẫn chưa đạt

```text
MESH-LOCAL-001 = INCONCLUSIVE
```

P4c1 chưa:

- chạy ba FDS cases như một study package;
- parse DEVC/output CSV thành observed metrics;
- chứng minh các observables thực tế hội tụ;
- định nghĩa reviewed acceptance policy;
- ước lượng numerical uncertainty;
- chứng minh application-specific mesh adequacy;
- chứng minh EV fire predictive validity.

Work package kế tiếp phải là **P4c2 execution + output-observable evidence**, sau đó mới cân nhắc phương pháp solution-verification cao hơn nếu scientific assumptions được chứng minh.
