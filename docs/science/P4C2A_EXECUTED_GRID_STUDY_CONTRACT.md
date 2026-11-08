# P4c2a — Executed pinned-FDS grid study và DEVC provenance contract

**Trạng thái:** software/solver-integration verified candidate  
**Work package:** P4c2a  
**Scoped claim:** `MESH-SENS-P4C2A-001`  
**Không phải:** EV-fire mesh-independence proof, convergence acceptance, numerical-uncertainty estimate, model validation hoặc application validation.

## 1. Mục tiêu

P4c2a nối P4c1 study-plan contract với solver output thật:

```text
ResolvedGridSensitivityPlan
→ COARSE / MEDIUM / FINE rendered FDS
→ pinned FDS 6.11.1
→ durable solver evidence
→ CHID_devc.csv / CHID_<n>_devc.csv
→ typed GridSensitivityObservation
→ P4c1 descriptive analysis
```

Mục tiêu của vòng này là xác minh **execution + provenance pipeline** và fail-closed behavior. P4c2a không biến một solver run tối giản thành bằng chứng rằng mesh đã đủ cho bài toán cháy xe điện.

## 2. Cơ sở có thẩm quyền

Nguồn chính:

1. NIST/FDS manuals:
   - https://pages.nist.gov/fds/manuals.html
2. FDS 6.11.1 release:
   - https://github.com/firemodels/fds/releases/tag/FDS-6.11.1
3. FDS source, `Source/dump.f90`:
   - https://github.com/firemodels/fds/blob/master/Source/dump.f90
4. P4c1 scientific basis:
   - FDS Validation Guide — Error Chapter
   - FDS Validation Guide — Plume Chapter
   - https://github.com/firemodels/fds/discussions/11797

`dump.f90` là cơ sở cho output contract được parser P4c2a hỗ trợ:

- device output dùng `CHID_devc.csv`;
- khi split output theo cột, dùng `CHID_<n>_devc.csv`;
- header đầu chứa units và bắt đầu bằng `s`;
- header thứ hai bắt đầu bằng `Time`, sau đó là các `DEVC ID`.

P4c2a không suy đoán định dạng CSV từ fixture test.

## 3. Pinned solver execution contract

`execute_grid_sensitivity_study()`:

- reject scenario nếu SHA-256 khác `scenario_invariant_sha256` của P4c1 plan;
- reject mọi solver version khác pinned FDS `6.11.1` trước khi chạy;
- render ba case bằng chính P4c1/P4b mesh path;
- gọi `solver_gates()` hiện hành, không tạo đường thực thi solver riêng hoặc bypass checksum/version gate;
- đối chiếu `solver_gate.evidence["fds_sha256"]` với exact rendered FDS hash trước khi ingest output;
- chỉ coi output evidence là accepted khi solver PASS và evidence directory/provenance hợp lệ.

Solver execution và output-evidence acceptance là hai trạng thái riêng:

```text
solver_status
output_evidence_status
```

Do đó FDS có thể chạy thành công nhưng output artifact vẫn bị reject; trường hợp đó study là `INCOMPLETE`, không chạy comparative analysis.

## 4. Simple point-DEVC scope

P4c2a cố ý chỉ hỗ trợ một subset nhỏ, có thể kiểm chứng rõ:

- `DEVC.ID`;
- `DEVC.XYZ` với đúng ba tọa độ;
- explicit `DEVC.QUANTITY`;
- optional `DEVC.UNITS`;
- aggregation:
  - `MAX`;
  - `MIN`;
  - `FINAL`.

Các modifier DEVC ngoài subset trên bị reject trước solver, ví dụ:

- `SPEC_ID`;
- `PROP_ID`;
- `TEMPORAL_STATISTIC`;
- `SPATIAL_STATISTIC`;
- `RELATIVE`;
- các qualifier khác có thể thay đổi semantics của observable.

P4c2a không tự diễn giải sprinkler/detector `PROP_ID`, không suy diễn species/flux semantics và không tính `MEAN` bằng arithmetic sample mean.

## 5. Time-window comparability

Nếu observable khai báo `time_window_s=(start, stop)`, DEVC series phải bao phủ toàn bộ cửa sổ:

```text
first_time <= start
last_time >= stop
```

Nếu output chỉ có dữ liệu ngắn hơn cửa sổ yêu cầu, artifact bị reject. Điều này ngăn việc lấy output 0–0.1 s rồi gắn nhãn như một statistic của 0–60 s.

## 6. Output parser contract

Parser DEVC CSV fail closed khi:

- không có file phù hợp `CHID_devc.csv` / `CHID_<n>_devc.csv`;
- header width không khớp;
- first unit không phải `s`;
- first label không phải `Time`;
- device ID rỗng hoặc trùng;
- cùng device ID xuất hiện ở nhiều split files;
- giá trị không numeric hoặc non-finite;
- thời gian không strictly increasing.

Mỗi series giữ:

- artifact filename;
- artifact SHA-256;
- unit;
- exact device ID;
- times;
- values.

## 7. Observable provenance

Mỗi accepted `GridSensitivityObservation` liên kết hai phía:

**Input descriptor**
- `source_device_id`;
- canonical SHA-256 của exact parsed `DEVC` descriptor;
- quantity;
- XYZ location.

**Solver output**
- source CSV filename;
- source CSV SHA-256;
- actual unit;
- scalar value theo aggregation đã khai báo.

P4c1 comparison descriptor được mở rộng để khóa cả `source_device_id` và `source_descriptor_sha256`, nên ba grid không thể âm thầm so sánh các probe khác nhau.

## 8. Case/study evidence chain

Mỗi case giữ:

- level / refinement ratio / local dx;
- Local MeshPlan SHA-256;
- rendered FDS SHA-256;
- required/reported solver version;
- solver binary SHA-256;
- configuration SHA-256;
- `audit.fds`, `run.json`, `stdout.log`, `stderr.log` SHA-256;
- toàn bộ output-file SHA-256 map;
- return code;
- timeout state;
- warning lines/count;
- typed result nếu và chỉ nếu evidence được chấp nhận.

Validator kiểm tra nội tại:

- COARSE/MEDIUM/FINE order;
- ratio tăng, dx giảm;
- three distinct MeshPlan hashes;
- three distinct FDS hashes;
- result metadata/hash phải khớp execution case;
- accepted case yêu cầu `returncode=0`, `timed_out=false`;
- observation artifact hash phải đúng file hash trong case evidence;
- `analysis.cases` phải đúng ba executed results.

Study luôn giữ:

```text
status = INCONCLUSIVE
acceptance_policy = NOT_DEFINED
numerical_uncertainty_status = NOT_ESTIMATED
```

## 9. Installer reliability hardening

CI từng gặp lặp lại `HTTP 504 Gateway Time-out` khi tải official FDS bundle.

`scripts/install-fds.py` được harden nhưng không nới solver pin:

- tải vào file `.part`;
- retry hữu hạn chỉ cho transport errors tạm thời:
  - HTTP 429;
  - HTTP 5xx;
  - URL/timeout errors;
- không retry non-transient 4xx;
- archive SHA-256 vẫn bắt buộc;
- extracted binary SHA-256 vẫn bắt buộc;
- checksum mismatch không được promote thành cached artifact;
- version/URL official bundle không thay đổi.

Regression khóa 504 retry, 404 no-retry và checksum mismatch rejection.

## 10. Code-head regression evidence

**Code candidate:**

```text
1520d9fdad9e50ca08a382d3c5a5df5219c749f9
```

Source Quality PR run `#42471828594`:

```text
SUCCESS
959 passed
16 deselected
121 warnings
coverage 87%
10916 statements / 1428 missed
artifact 13614090611
sha256:3d13f27fb6277e2aeaba125473ac7d41f635e5a9d8a005fc0b1c67eb03ee09a4
```

Push Conversion run `#42471825172`:

```text
SUCCESS
Linux/Windows Python 3.10–3.13 PASS
JavaScript PASS
browser PASS
pinned FDS PASS
solver: 11 passed, 964 deselected, 2 warnings
solver artifact 13613906019
sha256:ad5f08e76abf779a61b0df532ed6bbb0394ec931f2cf7a3a8b0bfe8b3efb1c48
browser artifact 13613906012
sha256:302a429e03c31ca8530ec541d3ebde71fad8078b34dcdffefba97b645b997317
```

PR Conversion run `#42471828517`:

```text
SUCCESS
Linux/Windows Python 3.10–3.13 PASS
JavaScript PASS
browser PASS
pinned FDS PASS
```

## 11. Scientific limitation of the real solver regression

Real P4c2a regression intentionally uses a minimal comparable scenario:

- `T_END=0.1 s`;
- point `TEMPERATURE` DEVC;
- no claim that the fixture represents a developed EV fire;
- no claim that temperature response over 0.1 s establishes mesh sensitivity for an EV garage scenario.

This run proves:

- three rendered grid cases can execute through pinned FDS 6.11.1;
- real DEVC CSV can be ingested;
- output can be bound to exact input/solver/artifact provenance;
- failure states are handled fail closed.

It does **not** prove:

- application-relevant grid convergence;
- mesh independence;
- asymptotic convergence;
- observed order;
- Richardson extrapolation applicability;
- GCI;
- numerical uncertainty;
- EV-fire predictive validity.

## 12. Scoped verdict

```text
MESH-SENS-P4C2A-001 = PASS / E2
```

PASS chỉ bao phủ software + pinned-solver-output provenance contract trong validation domain nêu trên.

Broad claim vẫn:

```text
MESH-LOCAL-001 = INCONCLUSIVE
```

Work package tiếp theo là **P4c2b application-relevant executed grid sensitivity** với fire scenario/observables và thời lượng có ý nghĩa cho câu hỏi kỹ thuật. Chỉ sau đó mới cân nhắc P4c3 convergence/numerical-uncertainty method nếu các scientific assumptions được chứng minh.
