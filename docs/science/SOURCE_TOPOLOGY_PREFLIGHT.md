# Topology preflight cho source self-intersection

**Phạm vi:** software verification của pipeline kiểm định hình học nguồn  
**Evidence level:** E2  
**Không phải:** solution verification, model validation, application validation hoặc chứng nhận PCCC

## 1. Vấn đề

Trước thay đổi này, source-topology preflight chỉ dùng điều kiện `valid_solid()`:

- vertex/face hữu hạn;
- closed manifold;
- positive signed volume.

Điều kiện trên là cần nhưng chưa đủ. Một mesh có thể vẫn closed-manifold và có thể tích dương nhưng các bề mặt hoặc component của chính nó tự giao nhau. Trường hợp đó trước đây chỉ bị phát hiện muộn khi `compare_solids()` chạy self-intersection oracle.

Hậu quả là khi cấu hình yêu cầu fail-fast theo source topology, các gate phụ thuộc như Air Path, Openings hoặc Solver có thể được phép chạy trước khi source self-intersection được nhận diện.

## 2. Quy tắc mới

`source_topology_preflight()` kiểm từng physical source mesh đang `IN_SCOPE` hoặc `BOUNDARY_RETAINED`.

### 2.1 Invalid manifold/volume

Nếu `valid_solid() == False`:

```text
status = FAIL
reason = INVALID_SOLID
```

Evidence chứa `mesh_quality`.

### 2.2 Self-intersection xác nhận

Nếu mesh đạt `valid_solid()` nhưng `self_intersection_evidence()` trả `CONFIRMED`:

```text
status = FAIL
reason = SELF_INTERSECTION
```

Evidence phải có witness machine-readable. Các loại witness hiện được oracle hỗ trợ gồm:

```text
TRIANGLE_CROSSING
COPLANAR_FACE_OVERLAP
COMPONENT_VOLUME_OVERLAP
```

Không repair mesh, không thay bằng bounding box và không giảm tolerance để cấp PASS.

### 2.3 Self-intersection không kết luận được

Nếu oracle trả `UNCERTAIN`:

```text
status = INCONCLUSIVE
reason = SELF_INTERSECTION_UNCERTAIN
```

Không được chuyển uncertainty thành clean/PASS.

## 3. Hai chế độ audit

### 3.1 `fail_fast_on_source_errors = True`

Nếu tồn tại topology blocker `FAIL` hoặc `INCONCLUSIVE`:

- Geometry giữ verdict tương ứng với source evidence;
- Air Path = `NOT_RUN`;
- Openings = `NOT_RUN`;
- Solver = `NOT_RUN`;
- metric `source_topology_preflight_rejected` chỉ được ghi khi execution thật sự bị chặn;
- metric `source_topology_preflight_evidence` lưu structured evidence.

Mục tiêu là không chạy downstream calculation trên source geometry chưa đủ điều kiện.

### 3.2 `fail_fast_on_source_errors = False`

Audit đầy đủ tiếp tục chạy các diagnostics/comparison lịch sử để thu thập evidence tối đa.

Structured self-intersection evidence vẫn có thể được ghi, nhưng **không** được dùng để short-circuit full diagnostics và không được gắn nhãn `source_topology_preflight_rejected`.

Điều này bảo toàn behavior parity của các baseline hiện hữu và tránh làm mất finding chỉ vì thêm oracle sớm hơn.

## 4. Compatibility contract

`invalid_source_solids()` giữ nguyên semantics lịch sử: chỉ liệt kê physical source mesh không đạt manifold/positive-volume predicate.

Self-intersection mới được quản lý bằng `source_topology_preflight()`. Việc tách hai API tránh làm thay đổi ngầm các consumer legacy đang dùng `invalid_source_solids()` cho accounting hoặc diagnostics.

## 5. Regression oracle

`tests/test_source_topology_self_intersection.py` tạo hai closed boxes giao nhau rồi ghép thành một mesh nhiều component.

Fixture được yêu cầu thỏa:

```text
valid_solid(mesh) == True
self_intersection_evidence(mesh).status == CONFIRMED
```

Nhờ đó regression chứng minh chính xác trường hợp mà predicate manifold/volume cũ không phát hiện.

Test stack kiểm:

- structured witness;
- fail-fast orchestration trong `ValidationRunner`;
- fail-fast orchestration trong independent validation;
- uncertainty => `INCONCLUSIVE`;
- non-fail-fast giữ full comparison diagnostics;
- compatibility semantics của `invalid_source_solids()`.

## 6. Evidence CI của code candidate

Code candidate: `a8076880c12ddf8ec382f3fc270e190b0457ab05`.

### Source quality

Run: `42385398407`

```text
894 passed
14 deselected
112 warnings
coverage = 87%
```

Artifact:

```text
source-quality-evidence
artifact id = 13579038618
sha256 = acaaf526ce12501ce136457183112f80329cadd122411e49327277e78721819e
```

### Conversion correctness

Run: `42385398466`

PASS:

- Python 3.10–3.13 trên Ubuntu;
- Python 3.10–3.13 trên Windows;
- JavaScript;
- browser;
- pinned FDS solver.

Solver artifact:

```text
artifact id = 13579825786
sha256 = 8b20558c44bc7aaa28f8e2673bafdfce25949d074ccbd2fa9f8f4d39a9874a67
```

Browser artifact:

```text
artifact id = 13579396691
sha256 = 98e7241c36281ea87e079e2b5a4572ec01ad372708cec80f3136ec38df1fe0c5
```

## 7. Regression phát hiện trong quá trình sửa

Hai regression đã được CI phát hiện và sửa ở root cause, không cập nhật golden để che lỗi:

1. FZK baseline đổi `geometry_preservation: FAIL → NOT_RUN` vì metric `source_topology_preflight_rejected` bị ghi ngay cả khi fail-fast tắt.
2. Duplex bị giảm finding count vì structured blocker bị dùng để short-circuit full diagnostics ngoài chế độ fail-fast.

Sửa cuối cùng:

- chỉ ghi `source_topology_preflight_rejected` khi fail-fast thực sự chặn;
- khi fail-fast tắt, giữ full diagnostics lịch sử;
- giữ semantics cũ của `invalid_source_solids()`.

Sau sửa, full regression và behavior parity PASS trên code candidate nêu trên.

## 8. Giới hạn

Work package này **không**:

- sửa source IFC bị open edge/non-manifold;
- tự loại Door/Beam/Plate/Ramp khỏi mô phỏng;
- tự tạo reviewed disposition;
- repair self-intersection;
- chứng minh source model là airtight;
- chứng minh numerical accuracy của FDS;
- chứng minh predictive validity của fire model.

Nếu source geometry thực sự invalid, verdict vẫn phải FAIL/INCONCLUSIVE cho tới khi source được sửa hoặc có explicit reviewed disposition với provenance đầy đủ.

## 9. Verdict

Scoped software claim:

```text
GEO-PREFLIGHT-001 = PASS / E2
```

Overall scientific/application verdict của IFCtoFDS vẫn:

```text
INCONCLUSIVE
```

Release verdict vẫn:

```text
NOT_PRODUCTION_READY
```
