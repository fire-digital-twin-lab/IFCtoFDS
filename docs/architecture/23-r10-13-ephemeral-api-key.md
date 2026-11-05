# R10-13 — Khoá API tạm thời, không lưu trong trình duyệt

## Mối nguy M-6b

Workbench trước đây ưu tiên `localStorage.ifcfds_api_key` khi lập HTTP
`x-api-key`. Đây là lưu trữ dài hạn có thể bị JavaScript cùng origin đọc,
không có thời gian hết hạn; XSS sẽ làm lộ khoá qua các phiên.

## Hợp đồng mới

- Trường mật khẩu trong Verified Mapping nhập API key chỉ dành cho tab đang mở.
- `setApiKey` giữ khoá trong closure JavaScript; không gọi localStorage,
  sessionStorage hay gửi khoá vào URL/query string.
- `authFetch` và EV scenario panel dùng cùng header `x-api-key`.
- Giữ tương thích cấu hình `window.IFCFDS_API_KEY` chỉ trong bộ nhớ, để
  không phá vỡ các môi trường đã cung cấp khoá theo cách đó.
- Reload tab buộc nhập lại khoá. Đây là đánh đổi có chủ đích.

## Bằng chứng và giới hạn

`scripts/test-ephemeral-api-key.js` chạy trong CI, giả lập browser
storage và ném lỗi nếu mã cố đọc/ghi thông tin xác thực bền vững.

Thay đổi này **không** thay thế HTTPS, chống XSS/CSP, quản lý danh tính,
phân quyền theo người dùng, rotate token hoặc cơ chế tải artifact có
header xác thực. Không đóng toàn bộ finding bảo mật sản phẩm.
