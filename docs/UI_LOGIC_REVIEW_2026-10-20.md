# Rà soát logic UI, hiệu năng và lỗi GEOM ngày 20/10/2026

Bổ sung sau điều tra sâu: [GEOMETRY_EXPORT_REVIEW_2026-10-20.md](GEOMETRY_EXPORT_REVIEW_2026-10-20.md) ghi nguyên nhân theo từng STEP, sửa luồng tải/xuất, bỏ thay cửa bằng hộp bao, kết quả FDS mới và giới hạn dọn tệp. Các số đo cache trong tài liệu này thuộc lượt kiểm tra trước.

## Kết quả

Đã sửa các luồng điều khiển hiển thị, hủy tác vụ, đọc kết quả chuyển đổi và xuất GEOM. Thay đổi được thực hiện tiếp trên working tree đang có sửa đổi; không commit hoặc push.

Hai nguồn thực tế dùng để kiểm tra là Tang7.ifc (902.871 byte) và Ham2Tang.ifc (32.655.047 byte). Không sửa tệp IFC nguồn. Các số đo dưới đây là đo trên máy hiện tại, không phải cam kết thời gian cho mọi mô hình.

## Nguyên nhân và cách sửa

| Vấn đề | Nguyên nhân xác minh được | Thay đổi |
| --- | --- | --- |
| Focus không có thao tác quay lại | Camera bị thay đổi nhưng UI không cung cấp khôi phục | Lưu camera trước khi focus; nút Back và lịch sử hoàn tác khôi phục camera |
| Hide/Isolate khó phục hồi | Các nút chỉ áp dụng trạng thái một chiều; hoàn tác không có nút luôn truy cập được | Hide/Show, Isolate/Unisolate; thêm Undo view action và Show all objects; khôi phục trạng thái hiển thị trong một lần cập nhật |
| Hủy xong giao diện còn kẹt | Vòng đời tác vụ nền, quá trình đọc tệp và cờ bận của controller không kết thúc cùng nhau | Nút Cancel task trên thông báo tiến độ; vô hiệu kết quả cũ bằng mã lượt tải/chuyển đổi; dừng worker khi hủy |
| Có thể bấm chuyển đổi nhiều lần khi còn phân tích IFC | Cờ bận được đặt sau bước phân tích | Đặt cờ bận ngay khi bắt đầu và giữ đến khi dựng xong kết quả |
| Không rõ công việc đang làm gì | Thông báo tổng quát, thiếu tiến độ cấu kiện | Hiển thị giai đoạn, số cấu kiện và thời gian đã chạy |
| Đọc FDS lớn làm UI mất phản hồi | Phân tích toàn bộ FDS trên luồng giao diện | Phân tích FDS trong worker; hủy được worker đọc kết quả |
| IFC/FDS chồng lên nhau sai hoặc camera nhìn như mất mô hình | IFC hiển thị tọa độ công trình, FDS đã trừ gốc tọa độ | Đọc IFC_COORDINATE_REBASE và phục hồi tọa độ công trình cho bản hiển thị; giữ nguyên tọa độ của tệp dùng cho solver |
| PyroSim báo Invalid GEOM | Nhánh Legacy thiếu dấu phẩy giữa VERTS và FACES; có tam giác diện tích đúng bằng 0 | Ghi dấu phân cách rõ ràng; bỏ đúng các tam giác không có diện tích; chặn chỉ số tam giác hoặc tọa độ không hợp lệ |
| GEOM mất cạnh nhỏ | Tọa độ GEOM bị làm tròn còn 6 chữ số thập phân | Giữ biểu diễn số binary64 khi xuất VERTS |
| FDS lỗi trên Windows | Dấu ':' trong tên Revit được dùng làm GEOM ID; FDS tạo tên CHID_GEOM_ID.bingeom | Tạo ID phù hợp tên tệp Windows, giữ tên IFC gốc và STEP ID trong thông tin truy vết |
| File hầm mở chậm | Dựng hình lặp với tọa độ thế giới và độ mịn dùng cho kiểm toán | Bản xem trước dùng hình học cục bộ để kernel tái sử dụng hình lặp, sau đó áp placement; độ mịn hiển thị 5 mm |
| Mở lại file vẫn dựng lại hình | Chưa có cache dành riêng cho xem trước | Cache theo SHA-256 nguồn, phiên bản engine và phiên bản thiết lập; kiểm tra checksum trước khi dùng lại |
| Kiểm toán tốn thời gian lặp phép tính | Dựng hình từng cấu kiện riêng và kiểm tra cùng một mesh nhiều lần | Iterator mới trên IFC được mở lại độc lập; tái dùng kết quả kiểm tra tự giao theo toàn bộ byte mesh trong đúng một lượt kiểm toán |
| Backend bật API key thì preview không chạy đầy đủ | Một số yêu cầu preview/payload chưa gửi header xác thực | Đồng bộ header với luồng chuyển đổi |
| Tab trong bảng kiểm toán không chuyển đúng | Controller chỉ đọc data-tab trong khi một số nút được nhận diện bằng ID | Bổ sung đọc tên tab từ ID |

## Số đo thực tế

| Công việc với Ham2Tang.ifc | Trước sửa | Sau sửa |
| --- | ---: | ---: |
| Dựng bản xem trước lần đầu | 83,89 giây | 21,65–24,44 giây |
| Bộ nhớ đỉnh của bước xem trước | 1.627 MB | khoảng 1.123–1.137 MB |
| Mở lại nguồn từ cache xem trước | Chưa có cache | 3,37 giây, khoảng 318 MB bộ nhớ đỉnh |
| Chuyển đổi và kiểm toán, khi cache hình học chuyển đổi đã có | 269,58 giây | 162,44 giây |

Không dùng cache xem trước trong chuyển đổi hoặc kiểm toán. Độ mịn 5 mm chỉ áp dụng cho bản xem trước; trích xuất dùng để chuyển đổi và kiểm toán vẫn giữ thiết lập 0,1 mm. Cache bằng chứng tự giao chỉ tồn tại trong một lượt kiểm toán; thay đổi tọa độ hoặc chỉ số mặt tạo khóa khác. Kết quả UNCERTAIN được tính lại.

Đã đối chiếu kết quả tầng 7: các trạng thái gate và tập phát hiện của kiểm toán được giữ nguyên sau tối ưu. Việc dựng hình cho kiểm toán vẫn dùng tọa độ thế giới trực tiếp từ kernel để giữ chính xác các giá trị hình học trong manifest.

## Kiểm tra đầu ra

- 296 kiểm thử Python chính đạt; 6 kiểm thử vòng đời tác vụ đạt; 2 kiểm thử solver thực tế đạt. Các nhóm HTTP và trình duyệt chưa hoàn tất được nêu riêng bên dưới.
- Kiểm thử JavaScript thực thi trực tiếp các nút Inspector, lịch sử hoàn tác, worker thường và inline, hủy kết quả cũ, truy vết và xuất GEOM.
- FDS 6.11.1 khởi tạo thành công với tệp Legacy tầng 7 sau sửa: exit code 0, T_END=0.
- FDS 6.11.1 khởi tạo thành công với đầu ra chuyển đổi hầm: exit code 0, T_END=0. Đây là kiểm tra thiết lập và khả năng đọc tệp.
- Kiểm thử trình duyệt tự động và một phần kiểm thử HTTP chưa hoàn tất trong môi trường hiện tại: vòng lặp asyncio/socketpair bị kẹt, còn Edge đóng ngay khi khởi tạo. Kiểm thử JavaScript nêu trên không thay thế việc quan sát trực tiếp WebGL và thao tác chuột.
- Chưa xác nhận import trực tiếp bằng ứng dụng PyroSim. Đã sửa các lỗi có thể tái hiện từ ảnh và kiểm tra bằng parser độc lập cùng FDS thực tế.

## Giới hạn nghiệm thu

Ham2Tang.ifc vẫn bị kiểm toán trả về REJECTED vì hình học nguồn không đạt các kiểm tra topology; một số gate chưa thể được nghiệm thu tiếp. Phần mềm phải tiếp tục thể hiện kết quả này. Không đổi REJECTED thành VERIFIED để làm cho luồng UI trông thành công.

Tệp Legacy còn là bản xem trước và không có đầy đủ bằng chứng nghiệm thu ánh xạ. Việc FDS đọc được một tệp không chứng minh đầy đủ hình học, HVAC/PCCC hoặc sự phù hợp của kịch bản cháy.

Sau khi lấy thay đổi: khởi động lại backend, tải lại trang để cập nhật JavaScript và worker, chọn lại IFC, thử Focus/Back, Hide/Show, Isolate/Unisolate và Cancel task. Tạo lại FDS để kiểm tra import; tệp FDS cũ không tự thay đổi.

## Tham khảo kỹ thuật

- [IfcOpenShell: geometry iterator](https://docs.ifcopenshell.org/ifcopenshell/geometry_iterator.html).
- [IfcOpenShell: geometry processing](https://docs.ifcopenshell.org/ifcopenshell-python/geometry_processing.html).
- [PyroSim: obstructions và kiểm tra GEOM](https://www.thunderheadeng.com/docs/2026-1/pyrosim/geometry/obstructions/).
