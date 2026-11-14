# Giai đoạn 5: phân loại tô-pô nguồn (đo ngày 2026-11-14)

Mốc trước/sau trên ba IFC mẫu (`scripts/verdict-snapshot.py`). Verdict tổng cả ba vẫn **REJECTED**.

| Mô hình | Phần tử DEVIATED trước → sau | Witness trước → sau |
|---|---|---|
| FZK-Haus | 16 → 16 | TRIANGLE_CROSSING 10 + COPLANAR 6 → TRIANGLE_CROSSING 16 |
| Duplex | 36 → 31 | TRIANGLE_CROSSING 32 + COPLANAR 4 → TRIANGLE_CROSSING 31 |
| Institute | 283 → 283 | TRIANGLE_CROSSING 142 + COPLANAR 141 → TRIANGLE_CROSSING 283 |

Tác động thực tế của 5.1:
- Solid **lỗ mở** gồm các hộp chạm mặt không còn bị coi là tự giao cắt: 14 finding
  "Invalid saved opening … Self-intersecting solid" biến mất ở FZK Erdgeschoss (47 → 31 finding).
- Duplex: 5 phần tử xuyên tam giác chỉ ở mức nhiễu CAD (độ sâu < 1e-5 m) nay là `numerical_contact`.
- Phần tử có nhãn COPLANAR trước đây thực ra còn có xuyên tam giác thật, nên chúng vẫn bị chặn (nhãn đổi sang TRIANGLE_CROSSING).

Đặc trưng của witness còn lại (cặp tam giác xuyên đầu tiên của mỗi phần tử):

| Mô hình | Cùng thành phần | Khác thành phần | Độ sâu < 1e-6 m | 1e-6..1e-3 m | ≥ 1e-3 m |
|---|---|---|---|---|---|
| FZK (18) | 0 | 18 | 0 | 2 | 16 (trung vị 2,5 cm) |
| Duplex (58, trước khi lọc) | 0 | 58 | 36 | 0 | 22 |

Kết luận: phần lớn lỗi còn lại là **các thành phần của cùng một cấu kiện chồng lấn thật** (khung và kính cửa, thanh lan can),
không phải nhiễu số. Muốn hết bị từ chối cần hợp nhất (union) các thành phần chồng lấn trước khi so sánh và xuất,
hoặc duyệt từng ca bằng `accepted_source_defects` (5.2). Việc hợp nhất là bước 5.4 trong roadmap.

Giới hạn đã biết: giao thể tích giữa các thành phần qua Manifold trả 0 cho 15/18 phần tử FZK dù độ sâu xuyên ≥ 1 mm
(các thành phần không phải `is_volume`); phép đo này không dùng được làm bằng chứng không chồng lấn.
