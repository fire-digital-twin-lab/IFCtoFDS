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

**Đính chính (M0, 2026-11-14).** Bản đầu của phần này kết luận "phần lớn lỗi còn lại là chồng lấn thật ≥ 1 mm giữa khung và kính".
Kết luận đó **sai**: phép đo dùng độ sâu `max` của hai chiều, trong khi tam giác lớn luôn cắt mặt phẳng của tam giác nhỏ rất sâu
nên mọi cặp chạm mép đều trông như xuyên sâu. Sau khi sửa (lấy `min`, xem `geometry/mesh.py`) và dọn cache hình học cũ,
các phần tử đó là tiếp xúc, không phải chồng lấn. Bảng độ sâu witness trước đây đã bị bỏ.

## 5.4 Hợp nhất thành phần chồng lấn (`geometry/component_union.py`)

Hợp nhất (Manifold union) các thành phần chồng lấn của cùng một cấu kiện, chỉ chấp nhận khi có bằng chứng không dựa vào kernel Boolean:
mỗi thành phần là thể tích kín; kết quả là solid hợp lệ không tự giao cắt; `max(V_i) ≤ V(union) ≤ Σ V_i`;
và oracle lấy mẫu bằng generalized winding number (Jacobson 2013) khớp giữa "trong union" và "trong bất kỳ thành phần".
Lỗi bất kỳ → giữ mesh gốc, cấu kiện vẫn bị chặn và lý do ghi trong `geometry_diagnostics.component_union`.
`passage_metrics` giờ chứng minh hai tập vật cản bằng nhau (cùng byte, hộp trục, hoặc phân hoạch mặt phẳng) trước khi dùng Boolean.

| Mô hình | DEVIATED (đầu Giai đoạn 5 → nay) | MATCHED | Verdict |
|---|---|---|---|
| FZK-Haus | 16 → 0 | 63 → 79 | REJECTED (1 UNSUPPORTED, 2 REVIEW_REQUIRED) |
| Duplex | 36 → 0 | 117 → 148 | REJECTED (43 UNSUPPORTED, 24 REVIEW_REQUIRED) |
| Institute | 283 → 0 | 149 → 432 | REJECTED (4 UNSUPPORTED, 265 REVIEW_REQUIRED) |

Lỗi còn lại hầu hết là hình học nguồn không phải solid hợp lệ (UNSUPPORTED) hoặc phần tử chờ duyệt (REVIEW_REQUIRED), không còn do chồng lấn.
Đã giải quyết: finding `representation` chập chờn ở Duplex do cache hình học cũ (chữ ký cache không gồm mã xử lý); nay chữ ký có dấu vân tay mã (`cache.code_fingerprint`).
