# 00 — Hồ sơ đề tài và bối cảnh khoa học

## Đề tài phần mềm

Tên làm việc: **Verified IFC-to-FDS Mapping Framework — Traceable Structural and MEP Geometry Conversion**.

Tổ chức: `fire-digital-twin-lab`; repository chính: https://github.com/fire-digital-twin-lab/IFCtoFDS; fork từ https://github.com/ProfRino/IFCtoFDS. Mục tiêu dùng công cụ xử lý mô hình BIM/IFC hiện trạng để tạo **hình học đầu vào có thể kiểm chứng** cho NIST Fire Dynamics Simulator (FDS).

### Mối liên hệ với nghiên cứu lớn

Các cuộc trao đổi ban đầu đề cập nghiên cứu cháy xe máy điện (pin lithium-ion) trong tầng hầm thực, khả năng dùng FDS để khảo sát khói/nhiệt và AI/ML để phân tích các kết quả mô phỏng. **Đây là bối cảnh dài hạn, không phải phạm vi công việc hiện tại của công cụ.** Quyết định gần nhất: **chưa cần kịch bản cháy**; cần ánh xạ kết cấu, HVAC và PCCC chính xác trước. Công cụ phải tổng quát, không viết riêng cho một tầng hầm.

### Ba mức độ mà nhóm phải phân biệt

1. **IFC source completeness:** mọi đối tượng/quan hệ thực có trong IFC phạm vi được ghi nhận và xử lý có lý do.
2. **FDS geometry/semantic fidelity:** hình học/ranh giới, lỗ mở và metadata được chuyển hoặc bảo toàn đúng với chính sách đã công bố.
3. **FDS physical functional fidelity:** quạt chạy, hút khói, đầu phun chữa cháy, detector và các cơ chế vật lý. **Ngoài phạm vi giai đoạn này** trừ khi người dùng phê duyệt riêng.

Một file `.fds` có đầy đủ hình dạng quạt/ống KHÔNG tự xác lập mô phỏng lưu lượng. Một đầu phun có hình học KHÔNG có nghĩa là FDS đã có sprinkler suppression model.

## Mục tiêu thành công

- Một/một nhóm file IFC nguồn được nhập có hash, phiên bản schema, đơn vị và hệ tọa độ.
- Inventory mọi `IfcProduct` theo nguồn, kể cả đối tượng không có geometry; các quan hệ/hệ thống thiết yếu được trích xuất riêng.
- Kết cấu, openings/shafts/ramps, HVAC/PCCC có representation decisions rõ ràng; không mất phần tử âm thầm.
- Sinh `.fds` có thể đọc lại, kèm manifest truy vết IFC → primitive FDS/semantic sidecar.
- Independent audit phát hiện missing/deviated/blocked openings/invalid geometry, báo rõ chưa kiểm chứng.
- Pipeline CLI có thể tái lập, sau đó tích hợp Web viewer hiện có.
- Có bộ benchmark phương pháp A: upstream browser; B: Bonsai+BFDS thủ công; C: hybrid đề xuất (khi điều kiện test cho phép).

## Những điều KHÔNG được kết luận từ context

- Chưa có chứng cứ rằng các IFC tầng hầm thực tế đã được nghiệm thu bằng IFCtoFDS fork.
- Chưa xác nhận số lượng và hiệu năng/giá trị dòng khí quạt, cảm biến CO, ống FP trên IFC cụ thể trong phiên này.
- Không tự động suy ra hình học FDS đầu ra có thể chạy mô phỏng có nghĩa vật lý nếu chưa cấu hình miền tính toán/mesh và điều kiện thích hợp.

## Hành động đầu tiên của agent

Audit repository thực tế, hiện trạng code, nguồn dữ liệu có trong repository, đồng bộ tests và so sánh với mô tả trong gói này. Nêu mọi khác biệt giữa HEAD thực tế và baseline ghi nhận. Không viết lại toàn bộ dự án trước khi hiểu cấu trúc đang có.
