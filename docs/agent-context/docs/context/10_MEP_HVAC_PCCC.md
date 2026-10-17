# 10 — HVAC/PCCC: bảo toàn hình học và đồ thị semantic

## Bài toán của người dùng

Các lần ánh xạ trước xuất hiện nguy cơ **thiếu đường ống thông gió**, **thiếu ống FP của hệ PCCC**, thiếu fittings/valves, đổi tên làm mất khả năng nhận diện. Yêu cầu bắt buộc là trích xuất, kiểm kê, đối chiếu **tất cả các bộ phận thực có trong IFC** thuộc phạm vi; không tự vẽ bổ sung phần không có.

## Những nhóm cần kiểm kê

### HVAC/Mechanical

- Duct segments, duct fittings, flexible duct nếu IFC có; dampers/fire dampers, air terminals, diffusers/louvers.
- Fans, mechanical equipment, distribution elements và ports.
- Đường xuyên tường/sàn, ống giao cắt kết cấu, ranh giới hút/cấp không khí.
- System membership, thành viên có system thiếu/không hợp lệ, flow direction từ IFC khi có.

### FP/PCCC

- Pipe segments, pipe fittings, valves, pumps, sprinkler heads, fire alarm devices/detectors, controllers nếu IFC có.
- Mạng ống, cách gắn sprinkler/terminal/valves và quan hệ hệ thống.
- Sensor metadata (CO/smoke/heat) chỉ đúng loại nguồn; không đổi cảm biến CO thành smoke detector hoặc ngược lại.

## Phân loại theo IFC version

Không dựa độc nhất vào chuỗi tên `FP`, `SPR`, `DUCT`, `PIPE`; cần phân tích class + `PredefinedType`, entity typing, system assignment, psets và ports. IFC2x3 có thể dùng các class `IfcFlowSegment`, `IfcFlowFitting`, `IfcFlowTerminal`, `IfcFlowController`; IFC4 có các class chuyên biệt như `IfcDuctSegment`/`IfcPipeSegment` khi schema có. Khả năng thực tế phải test theo schema.

## MEP graph model

```text
System
  ↳ Element (equipment / segment / fitting / terminal)
      ↳ Port (source-ifc-port-id)
          ⇄ Connection (IfcRelConnectsPorts / equivalent)
```

Nguồn relations quan trọng: `IfcRelAssignsToGroup`, `IfcRelContainedInSpatialStructure`, `IfcRelConnectsPorts`, quan hệ gắn port–element (phụ thuộc schema như nesting/port-to-element), `IfcRelDefinesByType`, psets.

Ghi mọi edge một trong: `EXPLICIT_IFC`, `SPATIALLY_SUGGESTED_UNCONFIRMED`, `HUMAN_CONFIRMED`. Chỉ nhóm đầu là bằng chứng nguồn IFC; nhóm hai KHÔNG tự được nâng thành verified.

## MEP coverage và readiness

| Dimension | Điều được xác nhận | Điều KHÔNG được xác nhận |
|---|---|---|
| `SOURCE_INVENTORY_COVERAGE` | Mọi phần tử nguồn được ghi nhận | Không nói về xuất FDS |
| `MEP_GEOMETRY_COVERAGE` | Hình học được bảo toàn/xuất theo policy | Không nói quạt/sprinkler chạy |
| `MEP_CONNECTIVITY_FIDELITY` | Quan hệ explicit được giữ đúng/được báo lỗi | Không chứng minh lưu lượng thực tế |
| `MEP_FUNCTIONAL_READINESS` | Có/thiếu metadata để mô hình hóa chức năng sau này | Không tự gán chức năng |

## Quy tắc biểu diễn FDS

- Ống dẫn có hai loại bề mặt: **vỏ ống vật cản** và **thể tích luồng khí bên trong**. Chuyển toàn ống thành khối OBST đặc có thể bít dòng khí một cách sai; chỉ dùng khi policy vật lý phù hợp.
- Ống FP/đầu phun có thể không quan trọng cho miền CFD ở độ phân giải cụ thể; vẫn giữ semantic và geometry provenance, có reason nếu lược bỏ vật cản nhỏ.
- Thiết bị quạt/van không tự động biến thành `VENT`/FDS HVAC network. Thông số nguồn nếu có chỉ được lưu lại, không tự xem là đã kích hoạt mô phỏng.
- MEP geometry có thể xuất kiểu reference/sidecar riêng để hoàn thiện tính đầy đủ dữ liệu mà không gây tác động vật lý giả trên FDS.

## Báo cáo cần có theo hệ thống

Cho mỗi `systemKey`: input elements by type, no-geometry, exported-geometry, semantic-only, approved excluded, unsupported, connectivity edges, orphan ports, orphan segments, source metadata completeness, missing/deviation findings.

## Test bắt buộc

- Complete duct path nhiều phụ kiện qua tường; đúng centerline, sections, hierarchy.
- Pipe FP sprinkler có nhánh và end devices, flow controller/valve.
- No-port IFC → `UNKNOWN_CONNECTIVITY` thay vì tự thêm edge.
- Two adjacent unconnected pipes → không báo nối explicit.
- Missing source fan/sensor → `MISSING_SOURCE_DATA` nếu requirement case đòi có; không tạo phỏng đoán.
- Aliased/repeated fittings → định danh riêng với geometry reuse hợp lệ.
