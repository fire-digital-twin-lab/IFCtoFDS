# Fixture IFC4 MEP/PCCC có hình học

`mep-fire-geometry.ifc` là mô hình kiểm thử **tự tạo**, không phải bản vẽ khảo sát hoặc dữ liệu nghiệm thu của công trình thực. File được tạo bằng IfcOpenShell; giấy phép của repository áp dụng cho mã tạo fixture.

| Hệ thống khai báo trong IFC | Phần tử có Body 3D |
| --- | --- |
| VENTILATION | IfcDuctSegment, IfcDuctFitting, IfcFan, IfcAirTerminal |
| FIREPROTECTION | IfcPipeSegment, IfcPipeFitting, IfcValve, IfcFireSuppressionTerminal |

Có tổng cộng **8 phần tử vật lý, 14 port và 6 quan hệ kết nối tường minh**. Hai port đầu mạng chưa nối ra ngoài là đầu vào của fixture; không phải port thiếu chủ sở hữu. Mỗi hệ thống có 4 phần tử và 3 kết nối.

Các phần tử dùng swept solids thực: tiết diện chữ nhật rỗng cho tuyến thông gió, tiết diện tròn rỗng cho ống/phụ kiện/van PCCC và tiết diện tròn đặc cho thân đầu sprinkler. Mô hình đơn giản hóa vỏ/thân thiết bị; không mô tả đầy đủ cấu tạo sản phẩm thương mại. Thể tích tiết diện chữ nhật có công thức giải tích trong file `.expected.json`; test cũng kiểm tra trục giữa ống gió vẫn rỗng sau chuyển đổi.

Các hệ thống, PredefinedType, ownership và port connections được ghi trực tiếp vào IFC. Reader production phải đọc lại các quan hệ này, không tự tạo chúng cho mô hình của người dùng.

Fixture dùng mét và placement 3D. Profile chuyển đổi phù hợp là `geometry-fidelity`: giữ hình học MEP làm đối tượng thụ động. `operational_status` vẫn phải là `NOT_CONFIGURED`; không suy ra lưu lượng, đường đặc tính quạt, hiệu quả sprinkler hoặc thông số cháy. Vật liệu mặc định của exporter không phải thông số vật lý thiết bị đã được nghiệm thu.

Tạo lại fixture trong môi trường phát triển:

```powershell
.venv/Scripts/python.exe -m scripts.generate_mep_geometry_fixture --output examples/mep-fire-geometry.ifc
```

Mỗi lần tạo lại sinh GlobalId mới; IFC và `.expected.json` phải đi cùng nhau. Không dùng việc tạo lại để thay thế IFC gốc của công trình.

Kiểm tra đầu ra bằng [tests/workflows/test_mep_geometry_acceptance.py](../tests/workflows/test_mep_geometry_acceptance.py) và bộ solver thật tại [tests/modules/verification/test_solver_matrix.py](../tests/modules/verification/test_solver_matrix.py).
