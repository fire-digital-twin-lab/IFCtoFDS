# R10-10 — Hợp đồng bản xem phân trang phát hiện

## Vấn đề

Endpoint `GET /api/jobs/{jid}/result?offset=...&limit=...` trước đây
thay `findings` của kết quả đã được xác thực bằng một lát cắt nhưng vẫn
trả toàn bộ `findings_count` của báo cáo gốc, không có nhãn cho biết
đây chỉ là **bản xem phân trang**. Với `scenario` và các mode không có
`findings`, endpoint còn tạo thêm danh sách rỗng không có trong báo cáo.

## Hợp đồng được thực hiện

- `GET /result` **không có tham số phân trang** luôn trả đúng kết quả
  đầy đủ do `JobRepository` đọc và kiểm tra bằng chứng. Không thêm trường
  `result_view` hay `findings_page`.
- Với `convert`, nếu có `offset > 0` hoặc `limit`, endpoint trả
  bản sao nông của kết quả đã xác thực, ghi `result_view=FINDINGS_PAGE`
  và `findings_page` gồm `offset`, `limit`, `returned`, `total`,
  `has_more`, `canonical_result_complete=false`.
- Giữ `findings_offset`, `findings_limit` để tương thích giao diện
  đã dùng các trường cũ. `findings_count` vẫn là tổng số phát hiện
  của báo cáo gốc, **không phải số phát hiện trong trang**.
- Các trường verdict của báo cáo đã được xác minh giữ nguyên. Không
  ghi lại `result.json`, không tạo lại chỉ mục hash.
- Với `scenario`, `preview`, `inventory`, yêu cầu phân trang finding
  trả HTTP 422 thay vì dựng danh sách `findings=[]` giả.
- Nếu danh sách gốc và `findings_count` không nhất quán, bản xem bị từ
  chối. Điều này không thay thế hợp đồng JSON hoặc kiểm tra checksum.

## Kiểm thử nghiệm thu

- Kiểm thử dữ liệu 3 phát hiện: offset 1/limit 1, trang cuối, trang rỗng.
- Kiểm tra tổng số phát hiện không thay đổi và verdict `REJECTED` không
  bị nâng thành `MAPPING_VERIFIED` hoặc `SIMULATION_VERIFIED`.
- Không phân trang được kết quả không thuộc mode chuyển đổi.
- Test FastAPI trên ca chuyển đổi IFC nhỏ có thật và ca EV Scenario,
  nhằm phân biệt bản xem trang với kết quả gốc.
- Không xem response `FINDINGS_PAGE` là bằng chứng độc lập rằng báo cáo
  đầy đủ đã được đọc. Muốn nghiệm thu, người dùng phải đọc kết quả gốc
  cùng manifest, report và evidence index.

## Giới hạn

Đây là chuẩn hóa dữ liệu HTTP, không thay đổi hình học, mapper, solver
hay thuật toán khoa học. Không đóng các finding A-03, A-04, A-18, A-25
chưa có thử nghiệm thực tế. Chỉ được đánh dấu nghiệm thu giai đoạn này
sau khi CI chuyển đổi và chất lượng cùng thành công trên HEAD của PR.
