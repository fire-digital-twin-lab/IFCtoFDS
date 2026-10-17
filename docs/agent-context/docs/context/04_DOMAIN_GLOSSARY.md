# 04 — Thuật ngữ và mô hình khái niệm IFC ↔ FDS

| Thuật ngữ | Cách hiểu trong project |
|---|---|
| BIM | Mô hình dữ liệu công trình, bao gồm hình học + semantic + quan hệ, không chỉ bản vẽ 3D |
| IFC | Chuẩn dữ liệu trao đổi BIM; chứa sản phẩm, hệ tọa độ, hình học, mối quan hệ, thuộc tính và hệ thống |
| `IfcProduct` | Nhóm đối tượng có thể có placement/representation; inventory vẫn cần ghi cả sản phẩm không có geometry |
| IFC STEP ID | ID nội bộ trong một file IFC; không ổn định khi export lại, không thay thế GlobalId |
| `GlobalId` | Định danh IFC; ở hệ nhiều file cần ghép thêm source file ID; không suy ra cùng object chỉ từ trùng tên |
| `ObjectPlacement` | Phép đặt tương đối/lồng nhau của đối tượng; phải chuẩn hóa cùng hệ tọa độ |
| `IfcMappedItem` | Dùng lại representation map với target transform; chú ý mapping origin nghịch đảo |
| `IfcRelVoidsElement` | Quan hệ host ↔ opening; có thể hiện thực bằng CSG/mesh đã cắt |
| `IfcRelFillsElement` | Quan hệ opening ↔ cửa/cửa sổ/fill; “door” không mặc định là lỗ mở thông khí mở |
| `IfcRelContainedInSpatialStructure` | Quan hệ thuộc tầng/khu; không tương đương phạm vi hình học giao cắt |
| IFC system/port graph | Hệ MEP, thiết bị/ống/ports/connections từ quan hệ nguồn; không đoán từ gần nhau |
| HVAC | Heating Ventilation and Air Conditioning; tập trung hệ thông gió, ống, van, quạt, terminals |
| PCCC / FP | Hệ thống phòng cháy chữa cháy / fire protection; ống, fittings, valves, sprinklers, alarms, pumps, devices |
| FDS | NIST Fire Dynamics Simulator; mô hình CFD cháy, đầu vào qua namelist |
| `OBST` | Vật cản hình hộp thẳng trục trong FDS; phù hợp khi có bằng chứng tương đương |
| `HOLE` | Vùng cắt vật cản theo cú pháp FDS; trình tự/miền và tương tác phải kiểm chứng bằng parser/FDS |
| `GEOM` | Hình học lưới tam giác trong FDS; phải phù hợp yêu cầu phiên bản/cấu hình solver |
| `MESH` | Lưới tính toán FDS; ảnh hưởng hình học hiệu dụng, khác `voxelSize` dùng xấp xỉ exporter |
| `VENT` / `HVAC` / `DEVC` | Đối tượng/quan hệ mô phỏng vật lý FDS; không tự phát từ sự tồn tại MEP IFC |
| IFC fidelity | Mức độ chính xác giữa hình học/semantic IFC gốc và bản trung gian |
| FDS representation fidelity | Mức tương đương giữa bản trung gian được duyệt và FDS serialized |
| Effective geometry | Vật cản/không gian hữu hiệu sau FDS diễn giải với mesh và chế độ hình học |
| Geometric topology | Tính liên thông, biên và lỗ; thông khí qua opening có thể sai dù bbox gần đúng |
| BRep | Boundary representation; topology của mặt/khối |
| Tessellation | Xấp xỉ đối tượng bằng tam giác; có sai số, phải ghi phương pháp và tham số |
| Voxelization | Rời rạc hóa không gian thành ô thể tích; có thể làm hẹp/bít lỗ |
| Source inventory | Danh mục đầy đủ IFC products/relations thuộc phạm vi đã xác định |
| Canonical BIM Model | Dữ liệu chuẩn trong đơn vị mét/hệ tọa độ nhất quán, geometry + semantic + provenance |
| Manifest | Bản đồ nguồn→quyết định→đối tượng đích, với reason codes và kiểm chứng |
| Alias | Tái sử dụng identity/geometry/reference sau khi chứng minh tương đương; không đồng nhất với đơn giản hóa |
| Human-in-the-loop | Chuyển trường hợp không chắc chắn cho kỹ sư duyệt; không tự động hóa phán đoán thiếu chứng cứ |

## Không được nhầm lẫn

- IFC chứa hình học ống gió ≠ FDS tính được lưu lượng ống.
- Viewer hiển thị đúng ≠ exporter serialize đúng ≠ solver sử dụng đúng.
- Full inventory ≠ 100% OBST/GEOM.
- Port không có trong IFC ≠ port chắc chắn không tồn tại trong công trình thực.
- AABB trùng nhau ≠ hình học tương đương.
- Số lượng mesh triangles cao ≠ độ chính xác có bằng chứng.
- `GEOM` mesh manifold ≠ đủ tính đúng đắn FDS; còn solver geometry semantics.
