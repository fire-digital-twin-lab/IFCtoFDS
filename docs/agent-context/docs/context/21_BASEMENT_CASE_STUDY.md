# 21 — Ca nghiên cứu lịch sử: mô hình tầng hầm B1/B2

**Trạng thái:** `HISTORICAL_CONTEXT — REVALIDATION_REQUIRED`. Nội dung từ trao đổi trước và một tài liệu Markdown đã lưu trong Library. **Các file IFC/FDS nguồn của công trình không nằm trong ZIP IFCtoFDS v0.1.0 hiện tại.** Không biến các số liệu này thành hardcoded fixtures hay khẳng định địa điểm/chức năng công trình.

## Mục đích của ca

Người dùng nghiên cứu một công trình có hai tầng hầm B1/B2, đề cập nguy cơ cháy xe máy điện và hệ thống thông gió/PCCC. Trong các lượt trước, muốn **bỏ phần vỉa hè phía trước và tầng 1**, chỉ dựng hình học cần thiết cho hầm; sau đó thấy đổi tên file và có dấu hiệu thiếu các ống/ống FP. Vì vậy, case làm bài kiểm thử thực tế cho: scope, geometry preservation, MEP completeness, traceability và hiệu quả audit.

## Số liệu từng được nêu (không phải kết quả kiểm tra mới)

| Thông số | Giá trị ước tính/lịch sử, CHƯA ĐỐI CHIẾU LẠI |
|---|---:|
| Bao ngoài hầm (dài × rộng) | khoảng 99,90 × 17,80 m |
| Cao độ sàn B1 | khoảng −4,20 m |
| Cao độ sàn B2 | khoảng −8,70 m |
| Chênh cao độ B1↔B2 | khoảng 4,50 m |
| Đáy sàn B2 từng được mô tả | khoảng −8,91 m |
| Diện tích hình học tấm sàn B1/B2 từng được tính | khoảng 1.412 / 1.602 m² |
| Độ dày sàn hầm từng mô tả | khoảng 210 mm |

Các giá trị này có thể phụ thuộc hệ tọa độ, cấu kiện được chọn và phiên bản IFC/FDS đã dùng trong những phiên trước; không được dùng làm `expected` trong CI cho công trình thật cho đến khi kiểm tra lại file gốc bằng hash.

## Đặc điểm từng được mô tả

- Hai tầng hầm có ram xe, cầu thang, cửa và lỗ mở.
- Dầm, sàn, cột, vách bê tông và một số vùng trần hạ thấp (có thể dưới vỉa hè).
- Có thảo luận về ducts, fans, dampers, air terminals, CO sensors, FP pipes và sprinkler.
- Tên, công năng chính xác và số lượng/vị trí/công suất quạt hoặc CO sensors **chưa được xác nhận đáng tin cậy trong gói này**.

## Kiểm thử case khi người dùng cung cấp IFC/FDS mới

1. Hash, schema, coordinate/frame, source model alignment cho kiến trúc/kết cấu và HVAC/PCCC.
2. Per-storey inventory B1, B2, elements crossing boundary, ngoài scope.
3. Opening locations, ram/shafts connections, trần thấp, ceiling/floor boundary.
4. Enumerate ducts/fittings/dampers/fans/terminals và FP pipes/fittings/sprinklers/devices thực có; phân biệt detection/human verification.
5. IFC→FDS mapping by GUID, geometry deviations, missing/excluded/semantic-only.
6. Check effective air paths; test FDS parser/static/solver nếu môi trường hỗ trợ.
7. Đánh giá ảnh hưởng của việc loại vỉa hè/tầng trên; không xóa cấu kiện biên cần thiết.

## Yêu cầu tổng quát hóa

Dù case tập trung B1/B2, chương trình phải hỗ trợ số tầng/khu vực bất kỳ và multi-IFC; B1/B2 chỉ là benchmark case, không phải tên biến mặc định trong core.
