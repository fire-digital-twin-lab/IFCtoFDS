# P0 — Nghiệm thu lại tính đúng đắn của verdict khoa học IFCtoFDS

**Ngày rà soát:** 05/11/2026  
**Phạm vi mã đã đối chiếu:** `AcceptanceReport.finalize`, `ConversionResult.check_acceptance`, `ScenarioResult.check_verdict`, `WorkerRunner`, `solver_gates`, audit độc lập và persisted-evidence audit.  
**Trạng thái:** Đã đề xuất khắc phục và regression tests trong PR này; **không coi là VERIFIED/PASS trước khi CI kết thúc và PR được merge.**

## 1. Phân cấp bằng chứng bắt buộc

| Kết quả/gate | Điều kiện và điều được chứng minh | Không chứng minh |
|---|---|---|
| `syntax=PASS` | Serialized FDS được parser kiểm tra trong phạm vi hỗ trợ | Đúng hình học IFC, vật lý hoặc CFD |
| `source_inventory/traceability/scope/geometry/structural_completeness/air_path/openings/mep/representation/boundary/domain` | Các yêu cầu độc lập của ánh xạ BIM → FDS có bằng chứng tương ứng | Mô phỏng cháy đã được chứng thực |
| `MAPPING_VERIFIED` | Tất cả 12 gate mapping bắt buộc có mặt, `required=true`, PASS hoặc NOT_APPLICABLE có lý do; không còn blocker mapping khác | `SIMULATION_VERIFIED`, kết quả CFD hay nghiệm thu an toàn cháy công trình |
| `solver=PASS` | Phiên khởi tạo FDS pinned đáp ứng hợp đồng kiểm tra đầu vào và điều kiện kết thúc được parser nhận biết | Đã kiểm định trường nhiệt/khói, mesh convergence hoặc thiết lập mô phỏng thực |
| `effective_geometry=PASS` | Có evidence hình học hiệu dụng từ solver khi thu thập được | Mức độ đúng đắn của vật lý cháy |
| `energy_budget_status=PASS` | Năng lượng burner danh định không vượt budget khai báo | Các chất ô nhiễm, HF, chemistry, safety margin hoặc tính đúng dữ liệu nguồn |
| `scenario.verdict=INCONCLUSIVE` | EV scenario chưa có independent CFD verification | Không được diễn giải thành simulation acceptance |
| `audit_outcome=EVIDENCE_VALID` | Cấu trúc JSON/hashes và evidence hiện hữu nhất quán ở phạm vi kiểm tra | Phê duyệt mô phỏng độc lập hoặc provenance được ký số |

**Nguyên tắc:** `SIMULATION_VERIFIED` hiện **không được phát hành** bởi `AcceptanceReport.finalize`. Các job EV có `simulation_status=NOT_RUN`. Không được nâng verdict chỉ vì FDS được sinh ra, parser PASS, setup solver PASS, energy budget PASS hoặc file hash không đổi.

## 2. Finding P0-SCI-01 — Thiếu required gates vẫn có thể được cấp Mapping Verified

**Trước sửa:** `AcceptanceReport.finalize()` lấy danh sách các gate được truyền vào và yêu cầu tất cả gate hiện diện PASS. Một đối tượng chỉ khai báo `syntax=PASS` có thể trả `MAPPING_VERIFIED` dù không có source inventory, geometry hay traceability.

**Sửa:** Dùng hằng `REQUIRED_MAPPING_GATES` gồm 12 gate; mọi gate phải có mặt, `required=true`. Bảy gate cốt lõi (`syntax`, `source_inventory`, `traceability`, `scope`, `geometry`, `representation`, `domain`) **bắt buộc PASS và không được miễn bằng NOT_APPLICABLE**, kể cả có lý do. Năm gate còn lại PASS hoặc NOT_APPLICABLE có lý do dựa trên đúng phạm vi nguồn. Gate vắng mặt, NOT_RUN, INCONCLUSIVE hoặc bị hạ thành optional đều ngăn MAPPING_VERIFIED. FAIL trên required gate hay blocker mapping tiếp tục trả REJECTED.

**Regression:** Mỗi gate bị xóa, bỏ required hoặc NOT_RUN riêng đều trả INCONCLUSIVE, không có positive verdict do thiếu evidence.

## 3. Finding P0-SCI-02 — API cho phép overall status không khớp profile yêu cầu

**Trước sửa:** `ConversionResult.check_acceptance()` chấp nhận `status` nếu bằng **một trong** `mapping_status` và `simulation_status`. Với `profile=simulation`, JSON có thể công bố overall `MAPPING_VERIFIED` dù simulation là `INCONCLUSIVE`.

**Sửa:** `profile=simulation` phải có overall status **bằng `simulation_status`**; các profile mapping/research-basement/geometry-fidelity phải có overall status bằng `mapping_status`. Hợp đồng public cũng yêu cầu đủ 12 gate bắt buộc và không cho ngụy trang gate là optional.

**Regression:** JSON khai báo simulation-profile kèm overall MAPPING_VERIFIED phải bị từ chối ở trust boundary; combination đúng `status=INCONCLUSIVE, mapping_status=MAPPING_VERIFIED, output_complete=true` vẫn được giữ.

## 4. Finding P1-SCI-03 — Scenario physics verdict có thể trái với physics evidence

**Trước sửa:** `ScenarioResult` kiểm tra physics evidence là một dictionary nhưng không so trạng thái với `physics_status`. JSON đã tồn tại có thể chứa `physics_status=PASS` trong khi physics evidence là `INCONCLUSIVE`.

**Sửa:** `physics_status` phải trùng `evidence.physics.status`. Physics assessment hiện chỉ kết luận `FAIL` hoặc `INCONCLUSIVE` ở tầng physical acceptance; không được thay `energy_budget_status=PASS` bằng physical `PASS`. Những trường hợp mâu thuẫn bị từ chối.

**Regression:** Physics status/evidence mismatch, PASS giả, FAIL giả đều phải bị từ chối; FAIL thật được giữ nguyên.

## 5. Chứng cứ và giới hạn chưa khép

- Unit/contract CI **không phải** khoa học thực nghiệm, không phải độc lập kiểm định FDS/CFD.
- Việc hash khớp có thể chứng minh consistency nội bộ, **không chứng minh tác giả của evidence** hoặc kết quả mô phỏng có giá trị khoa học.
- Cần test IFC thực (geometry openings, nhiều tầng, MEP), mô hình tham chiếu đã phê duyệt, sai lệch có ngưỡng có căn cứ và review bởi chuyên gia khoa học.
- Cần solver case có thể tái lập với phiên bản binary, checksum, log, input/output, mesh convergence, physical boundary conditions, uncertainty và calibration.
- Chưa có bằng chứng độc lập về EV thermal runaway, HRRPUA, HF yields, thực nghiệm so sánh, chất lượng lưới và độ nhạy.
- Cần đối chiếu engine legacy với modular validation runner ở **chi tiết** gate evidence, không chỉ status (parity detailed mode), và kiểm tra bất biến source/manifest.
- Mọi `P0`/finding còn mở và gate `NOT_RUN` làm suy yếu khả năng nghiệm thu; không được gắn `SCIENTIFIC_VERIFIED` hay `SIMULATION_VERIFIED`.

## 6. Tiêu chí chấp nhận

1. Chạy regression mới trên Python/Windows/Linux theo GitHub Actions, cùng full suite.
2. Không làm mất khả năng cấp `MAPPING_VERIFIED` cho trường hợp có **đủ** evidence; mẫu đủ 12 gate có PASS.
3. Không có đường công bố overall `SIMULATION_VERIFIED` khi chưa tồn tại simulation epic và independent evidence.
4. Hợp đồng persisted/public ngăn tất cả status/evidence/profile mâu thuẫn.
5. Merge không bỏ branch protection; ghi SHA, CI links và trạng thái gate.
6. Cho đến khi hoàn thành scientific V&V thực, **G09/G10 = INCONCLUSIVE** và **NOT_PRODUCTION_READY**.
