# Củng cố module Reference và bằng chứng đối chiếu

Ngày: 23/10/2026. Nhánh `chore/research-acceptance-hardening`, HEAD nền `5d715a7df7b7606747285b7073287723f20506f3`. Thay đổi nằm trong working tree cùng các bản sửa Verification trước đó, chưa commit/push. Module Reference được xử lý tiếp theo thứ tự trong báo cáo chức năng 15.

## 1. Phạm vi đã thực hiện

| Luồng | Vấn đề xác nhận | Thay đổi |
| --- | --- | --- |
| Phê duyệt | Giá trị chỉ chứa khoảng trắng hoặc sai kiểu vẫn có thể vượt kiểm tra truthiness ở CLI/parity. | Dùng chung `is_approved_reference`: APPROVED, reviewer/rationale là chuỗi có nội dung, evidence là danh sách không rỗng gồm chuỗi có nội dung. Phân biệt tính toàn vẹn và khai báo phê duyệt. |
| Integrity bundle | Có thể tính lại checksum cho sources/domain/geometry/openings tự mâu thuẫn với golden manifest. | Kiểm tra source signatures, domain, tập entity, metadata/ports, danh tính opening/filling, liên kết checksum và inventory hình học FDS. Giữ đường đọc schema 0.4.0; parity vẫn yêu cầu revision mới. |
| Registry phục vụ giao diện | Chỉ kiểm JSON digest nên payload mất/hỏng hoặc bundle mâu thuẫn vẫn có thể hiển thị VERIFIED/APPROVED. | Registry dùng đầy đủ `inspect_case`, gồm kiểm byte payload. Corrupt, thiếu phê duyệt và unavailable có trạng thái riêng. Một mục cấu hình lỗi không làm mất các case hợp lệ khác. |
| Delta/alias | Kiểu dữ liệu sai có thể gây exception thay vì finding; bằng chứng chỉ chứa khoảng trắng chưa bị chặn thống nhất. | Kiểm tra cấu trúc change, entity/field, before/after và bằng chứng. Alias vẫn phải qua biến đổi cứng và so sánh hình học. Delta không miễn các gate độc lập. |
| Workflow thực | Cần kiểm tra cả nguồn và artifacts đã lưu thay vì chỉ model trong bộ nhớ. | Test tạo IFC có tường hộp được định nghĩa rõ kích thước, lưu FDS/manifest/package, tạo DRAFT, audit lại nguồn, xét duyệt fixture có kiểm soát và phát hiện FDS bị sửa dù manifest được reseal. |

Không có lệnh tự phê duyệt. Candidate sản phẩm vẫn DRAFT. Các hồ sơ APPROVED trong test là dữ liệu test do tác giả fixture khai báo, không phải bộ chuẩn công trình đã được kỹ sư nghiệm thu.

`reference-check` công bố `data_integrity_verified` và `human_approval_verified` riêng. Mã thoát: 0 khi integrity và khai báo phê duyệt hợp lệ; 2 cho DRAFT/SUPERSEDED/thiếu bằng chứng; 3 khi bundle lỗi. Registry dùng UNVERIFIED_APPROVAL cho khai báo APPROVED thiếu/sai bằng chứng; UNVERIFIED_CORRUPT khi integrity không đạt.

## 2. Kiểm tra và kết quả

Thêm 33 test, nâng nhóm Reference từ 45 lên 78 test. Các ca mới bao gồm sáu kiểu khai báo phê duyệt sai, sửa bundle rồi tính lại các checksum, sửa/xóa payload, metadata thiếu, opening/filling sai, JSON sai cấu trúc, delta/alias sai định danh, vòng đời DRAFT/SUPERSEDED và audit qua artifact đã lưu.

| Trạng thái | Kiểm tra | Bằng chứng và giới hạn |
| --- | --- | --- |
| PASS | Baseline Reference trước sửa | 45 test đạt; `.cache/reference-baseline.xml`. |
| PASS | Suite Python không cần HTTP/browser | 540 test đạt, 32 deselected theo marker solver/browser; có 78 test Reference, architecture, baseline và workflow. Chủ động không thu thập `tests/interfaces/http` và toàn bộ `test_job_lifecycle.py` trong lượt này. `.cache/reference-offline-final.xml`, 131,91 giây. |
| PASS | Hai harness frontend | `node scripts/test-golden-workflow.js`: domain/profile/decisions/artifacts, reference viewer và chống kết quả job cũ ghi đè; `node scripts/test-verified-regressions.js`: export completeness, opening rays và JSON provenance. Đây là harness Node, không phải browser thật. |
| NOT_RUN | HTTP, browser thật và CI GitHub | Chưa chạy trong lượt module Reference; không suy từ harness hoặc tests application thành PASS giao diện HTTP/trình duyệt. |
| NOT_RUN | FDS/PyroSim thật trong lượt Reference | Không sửa serializer hoặc adapter solver trong lượt này. Kết quả solver Verification trước đó được ghi riêng tại báo cáo 18. |
| BLOCKED | Nghiệm thu bộ chuẩn công trình thực | Chưa có bộ chuẩn độc lập của công trình được người có thẩm quyền phê duyệt để đánh giá trong lượt này. Fixtures không thay thế dữ liệu đó. |

Runtime: Windows 11, Python 3.12.10, pytest 9.1.1, IfcOpenShell 0.9.0.post1, NumPy 2.5.4, SciPy 1.18.1, trimesh 5.1.1, Pydantic 2.14.1. TEMP/TMP được đặt trong `.cache/reference-runtime`. Các warning phép đo mesh trong ca lỗi/mutation vẫn được pytest ghi lại, không tắt để làm báo cáo sạch.

```powershell
New-Item -ItemType Directory -Force .cache/reference-runtime | Out-Null
$env:TEMP = (Resolve-Path .cache/reference-runtime).Path
$env:TMP = $env:TEMP
.venv/Scripts/python.exe -m pytest -q tests/modules/reference --basetemp .cache/reference-reproduce
.venv/Scripts/python.exe -m pytest -q --ignore=tests/interfaces/http --ignore=tests/modules/jobs/test_job_lifecycle.py --basetemp .cache/reference-offline-reproduce
node scripts/test-golden-workflow.js
node scripts/test-verified-regressions.js
```

## 3. Giới hạn còn lại

Phê duyệt là hồ sơ cục bộ, chưa xác thực reviewer bằng chữ ký số hoặc hệ thống thẩm quyền bên ngoài. Kiểm tra integrity chứng minh các ràng buộc đã kiểm tra và tính toàn vẹn payload; không xác nhận đầy đủ chất lượng kỹ thuật của bộ chuẩn. Registry nay đọc toàn bộ payload, nên cần đánh giá thời gian trên vault lớn trước khi kết luận hiệu năng vận hành.

Parity hiện chứng minh các nguồn/metadata/solids/openings/MEP theo hợp đồng đang triển khai; không chứng nhận mọi điều kiện vật lý hoặc toàn bộ ngữ nghĩa FDS. Không nâng `SIMULATION_VERIFIED`, không tự thêm vận hành quạt/sprinkler, không suy chuẩn độc lập từ candidate do converter tự sinh. GEOM cut-cell và phiên nhập/xuất PyroSim thật vẫn là các khoảng trống nghiệm thu đã nêu ở báo cáo Verification.
