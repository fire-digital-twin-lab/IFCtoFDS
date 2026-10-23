# Củng cố module Artifacts: publication, toàn vẹn và checkpoint

Ngày: 23/10/2026. Nhánh `chore/research-acceptance-hardening`, HEAD nền `5d715a7df7b7606747285b7073287723f20506f3`. Tiếp nối Verification và Reference; các thay đổi vẫn trong working tree, chưa commit/push.

## 1. Kết quả thực hiện

| Vấn đề | Sửa đổi | Bằng chứng |
| --- | --- | --- |
| Payload/index bị hỏng sau audit vẫn có thể được đóng gói cùng report cũ | Mở lại geometry index và kiểm payload đã staging trước khi đụng bundle đích. Không chỉ dùng object package đã nạp. | Sửa byte payload, sửa index trên đĩa khi object vẫn giữ dữ liệu cũ, sửa checksum inline: đều bị từ chối và bundle trước đó giữ nguyên từng byte. |
| Payload cũ còn lại khi đổi biểu diễn hoặc tái dùng workspace | Inline publication xóa thư mục payload của bundle cũ; bản staging disk chỉ giữ blob được index tham chiếu. | Không phát hành blob từ lượt trước; không sửa/xóa blob nguồn. Lỗi publication sau khi thay payload vẫn khôi phục bộ cũ. |
| Hai writer có thể ghi xen kẽ | Tạo khóa độc quyền theo stem cho publisher và inspector; đích bắt buộc `.fds` để tách namespace khỏi IFC/JSON và các tên bằng chứng sinh kèm. | Yêu cầu cùng đích trong lúc writer hoạt động bị từ chối; stem khác vẫn độc lập. IFC/JSON hoặc tên không có đuôi không bị ghi đè. Đây là test xen kẽ xác định qua API, không phải soak/load test đa tiến trình. |
| Không có capability mở lại toàn bộ bộ xuất để kiểm tra | Thêm `verify_run_artifacts` vào public API. Kiểm đúng tập 12 artifact, checksum từng file và mọi payload geometry được tham chiếu. | Sửa FDS/report/ZIP/payload hoặc thêm đường dẫn ngoài hợp đồng vào checksum inventory đều bị từ chối. Bundle nguyên vẹn trả PASS với scope chỉ gồm toàn vẹn lưu trữ. |
| Lượt ghi mới có thể để lại nhãn SEALED của lượt trước | Đổi checkpoint về DRAFT trước khi ghi lại geometry/metadata. Thay JSON/state qua file tạm cùng thư mục. | Lỗi ngay khi ghi geometry hoặc checkpoint không để nhãn cũ VERIFIED_SEALED. Lỗi thay state vẫn giữ JSON hợp lệ trước đó. |
| Metadata hoàn tất không hợp lệ vẫn có thể mang nhãn đã nghiệm thu | SEALED cần report đạt mapping, output hoàn chỉnh và bundle hash khớp. Nếu report nói đạt nhưng điều kiện này thiếu, state giữ INCONCLUSIVE/DRAFT và output_complete=false. | Ca manifest chưa hoàn chỉnh hoặc đã sửa sau reseal không được coi là checkpoint đã nghiệm thu. |

Giữ 12 checksum top-level như hợp đồng cũ; file checksum không tự hash chính nó. Publisher vẫn lưu report REJECTED/INCONCLUSIVE phục vụ chẩn đoán, không tự nâng trạng thái mapping. Bộ FZK có lỗi nguồn vẫn được kiểm tra là ca nghiệm thu phủ định dù các artifact được lưu thành công.

## 2. Kiểm tra

Thêm 22 test, nâng nhóm Artifacts từ 24 lên 46 test. Lượt yêu cầu mới trước triển khai có 17 FAIL và 2 PASS, gồm các hành vi sai đã tái hiện và capability inspector chưa có. Sau đó bổ sung kiểm tra blob không tham chiếu và hai trường hợp metadata hoàn tất không hợp lệ.

| Trạng thái | Lượt kiểm tra | Kết quả / giới hạn |
| --- | --- | --- |
| PASS | Baseline Artifacts + geometry export investigation | 32 test; `.cache/artifacts-baseline.xml`. |
| PASS | Kiến trúc + Artifacts + geometry export investigation | 100 test trước khi thêm ca blob không tham chiếu; `.cache/artifacts-targeted.xml`. Có chồng lặp với suite bên dưới, không cộng tổng. |
| PASS | Suite Python không cần HTTP/browser | 562 test, 32 deselected theo marker solver/browser, 141,82 giây. Gồm 46 test Artifacts. Không thu thập `tests/interfaces/http` và toàn bộ `tests/modules/jobs/test_job_lifecycle.py`. `.cache/artifacts-offline-final.xml`. |
| PASS | Kiểm tra lại sau chốt status của completion | 22 test publication/checkpoint trên mã cuối; `.cache/artifacts-completion-final.xml`. Lượt rộng bên trên chạy trước khi thêm chốt hạ status xuống INCONCLUSIVE; các ca bị ảnh hưởng được chạy lại ở lượt này. |
| PASS | Hai harness Node | `test-artifact-downloads.js`: auth, checkpoint đúng job, MIME ZIP, lỗi và reset liên kết cũ. `test-artifact-viewer.js`: concurrency giới hạn, dispose, cancel và lỗi artifact. Không phải browser thật. |
| NOT_RUN | HTTP/browser thật và CI GitHub | Không suy từ harness/unit tests thành PASS cho các luồng này. |
| NOT_RUN | Solver/PyroSim thật trong lượt Artifacts | Không sửa serializer hoặc solver adapter; kết quả Verification trước đó được ghi riêng tại báo cáo 18. |

Runtime: Windows 11, Python 3.12.10, pytest 9.1.1, IfcOpenShell 0.9.0.post1, NumPy 2.5.4, SciPy 1.18.1, trimesh 5.1.1, Pydantic 2.14.1. TEMP/TMP đặt tại `.cache/artifacts-runtime`. Không sửa fixture/snapshot chuẩn hoặc IFC nguồn.

```powershell
New-Item -ItemType Directory -Force .cache/artifacts-runtime | Out-Null
$env:TEMP = (Resolve-Path .cache/artifacts-runtime).Path
$env:TMP = $env:TEMP
.venv/Scripts/python.exe -m pytest -q tests/architecture tests/modules/artifacts tests/modules/geometry/test_geometry_export_investigation.py --basetemp .cache/artifacts-reproduce
node scripts/test-artifact-downloads.js
node scripts/test-artifact-viewer.js
```

## 3. Phạm vi sử dụng và giới hạn

`verify_run_artifacts` trả `scope=ARTIFACT_BYTES_AND_GEOMETRY_PAYLOAD_INTEGRITY`: bằng chứng các file khớp checksum được khai báo và payload khớp geometry index. Không chứng minh nguồn IFC, hình học, phê duyệt reviewer hoặc vật lý mô phỏng đúng. Checksum manifest không có chữ ký xác thực độc lập; không coi việc tính lại checksum là thay thế audit nguồn.

Khóa chỉ bảo vệ thao tác hợp tác qua API. Các file được thay riêng lẻ và rollback khi có exception; không công bố transaction nhiều file chống mất điện/kill cưỡng bức. Nếu tiến trình chết hoặc rollback lỗi, cần kiểm tra writer và backup rồi phục hồi; không tự xóa khóa theo tuổi file. Inspector hiện cần quyền ghi thư mục để giữ khóa.

Chưa có crash/soak test, nhiều máy hoặc filesystem mạng. Nghiệm thu nội dung công trình thực, GEOM cut-cell và nhập/xuất PyroSim vẫn cần bằng chứng riêng; module lưu trữ không giải quyết thay các điều kiện đó.
