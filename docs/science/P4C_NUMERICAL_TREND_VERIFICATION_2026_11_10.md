# P4-NUM-001 — Kiểm định số học của phân loại xu hướng grid sensitivity

**Ngày lập:** 10/11/2026 · **Base:** `main@77f047f392fc4ac7fc3d4414df4cbc9087151ebb`  
**Scientific claim ảnh hưởng:** scoped `MESH-SENS-P4C1-001` / `MESH-SENS-P4C2A-001`; broad `MESH-LOCAL-001` giữ **INCONCLUSIVE**.  
**Required evidence:** E2 — software/numerical implementation verification; **không** tuyên bố E3 mesh convergence, E4 experimental validation hoặc E5 application validation.

## 1. Finding và root cause

**Input:** ba kết quả scalar đã provenance, cùng observable và scenario-invariant SHA, sắp xếp COARSE/MEDIUM/FINE.  
**Transformation:** `analyze_grid_sensitivity` → hai sai phân `medium-coarse`, `fine-medium` → `_trend`, `_change_trend` và relative changes.  
**Output/consumer:** `MetricSensitivityEvidence.trend` trong `GridSensitivityStudyEvidence`, dùng để mô tả độ nhạy lưới; **không** cấp convergence PASS.

Phiên bản trước sửa suy xu hướng bằng `first * second > 0` / `first * second < 0`. Phép nhân có thể **underflow về ±0** mặc dù hai sai phân đầu vào là finite/nonzero. Khi đó một chuỗi strictly monotonic hoặc đổi chiều bị gắn sai `PLATEAU_OR_UNRESOLVED`.

**Tái hiện độc lập bằng Python binary64:**

| Dãy coarse / medium / fine | Tích sai phân | Kết quả cũ | Oracle toán học |
|---|---:|---|---|
| `0, 1e-200, 2e-200` | `0.0` | `PLATEAU_OR_UNRESOLVED` | `MONOTONIC` |
| `0, 2e-200, 1e-200` | `-0.0` | `PLATEAU_OR_UNRESOLVED` | `OSCILLATORY` |
| `0, 1, 2` | `1.0` | `MONOTONIC` | `MONOTONIC` |
| `0, 2, 1` | `-2.0` | `OSCILLATORY` | `OSCILLATORY` |

Đây là vi phạm **scale invariance**: đổi đơn vị bằng hệ số dương không được biến xu hướng tăng đơn điệu thành plateau. Vấn đề là số học IEEE binary64, **không** phải kết quả solver FDS.

## 2. Work package và tiêu chí nghiệm thu

- **Finding:** product-of-differences underflow tạo false plateau/unknown; phép trừ/chia có thể overflow từ finite observations.
- **Root cause:** nhân hai sai phân để suy dấu, thiếu kiểm tra derived numbers trước khi xuất evidence.
- **Files:** `ifc_to_fds/fire/grid_sensitivity_analysis.py`, `tests/test_grid_sensitivity.py` và technical note này.
- **Non-goals:** không đổi mesh spacing, scenario inputs, CFD data, thresholds, solver, mốc D*/dx, GCI/Richardson, FDS reference, acceptance policy.
- **Risk:** báo cáo trend thay đổi khi đầu vào rất nhỏ; đây là sửa lỗi phân loại toán học có chủ đích, không thay đổi final scientific status.
- **Acceptance criteria:** monotonic/oscillatory/flat/plateau đúng oracle; dấu không tính bằng nhân; bất biến dưới positive unit rescaling; derived overflow `ValueError` fail-closed; hiện trạng với dữ liệu thông thường không regression; `status=INCONCLUSIVE` và `numerical_uncertainty_status=NOT_ESTIMATED` giữ nguyên.
- **Tests:** positive/boundary/negative; metamorphic scale invariance; targeted pytest, static/lint/type, full Python regression, JS và pinned solver CI.
- **Rollback:** revert commit/PR P4-NUM-001 nếu test/CI phát hiện regression, không sửa golden hay tăng tolerance. Nếu revert, phải ghi nợ khoa học do false plateau được tái hiện.

## 3. Implementation và kiểm toán scope

Sử dụng so sánh dấu của từng sai phân khác zero, không tạo tích mới. Nếu sai phân hoặc tỷ lệ tương đối không còn finite trong binary64 thì từ chối xuất metric thay vì ghi giá trị `inf` hay `nan`. Không thêm epsilon, không hardcode numerical convergence threshold.

**T1 trước sửa:** nguồn toán học tối giản đã tái hiện misclassification, chưa phải full repository targeted pytest.  
**T1/T2/T4/T5/T6:** chỉ ghi PASS sau khi GitHub workflow chạy trên **HEAD cuối**, không dựa trên code review hoặc statement.  
**Scientific oracle:** dấu của `Δ1` và `Δ2`, bất biến dương; không phải solver/experimental oracle.  
**Known limitations:** binary64 cũng có thể làm tròn chênh lệch quá bé về 0 ngay ở phép trừ; không thể khôi phục thông tin dưới độ phân giải float. Các metric không đại diện cho application EV-fire khi reference/uncertainty chưa duyệt.

## 4. Verdict

- **Numerical implementation:** `INCONCLUSIVE` trước CI; có thể nâng scoped software test sau đủ test + reviewer theo master prompt.
- **Mesh independence:** `INCONCLUSIVE`.
- **EV-fire scientific/application:** `INCONCLUSIVE`.
- **Production release:** `NOT_PRODUCTION_READY`.

**Không sửa `docs/science/SCIENTIFIC_CLAIMS.md` để tuyên bố E3/E4/E5 từ unit tests.**
