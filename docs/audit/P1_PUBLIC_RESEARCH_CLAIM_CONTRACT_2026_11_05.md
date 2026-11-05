# P1 — Ngăn metadata nghiên cứu công bố verdict khoa học mâu thuẫn

**Ngày:** 05/11/2026. **Phạm vi:** JSON trả về từ `validate_job_result("convert", ...)` và endpoint persisted job result.

## Finding P1-SCI-PUBLIC

`ConversionResult.research` là dictionary linh hoạt và trước thay đổi này không có ràng buộc nhất quán với `profile`, `mapping_status` và `golden_reference_parity`. Result có thể mang `research.research_acceptance=MAPPING_VERIFIED` hoặc `research.parity_status=PASS` ngay cả khi kết quả khoa học cuối cùng là `INCONCLUSIVE`, không có golden gate, hoặc golden gate đã FAIL.

Đặc biệt, profile `research-basement` yêu cầu bộ tham chiếu độc lập có phê duyệt, nhưng public result có thể trình bày `mapping_status=MAPPING_VERIFIED` mà không cần có `golden_reference_parity`. Điều này là lỗ hổng contract ở trust boundary, không phải kết quả thực nghiệm.

## Khắc phục

- Nếu metadata có `profile`, giá trị phải khớp profile cấp cao.
- Nếu có `research_acceptance`: profile research-basement bắt buộc bằng final `mapping_status`; các profile khác chỉ được `NOT_RUN`.
- Metadata không được tự khai báo những trường khoa học khác như `scientific_acceptance`, `simulation_status`, `verdict`, `verified` hay `acceptance_status`.
- `parity_status` phải phù hợp trạng thái `golden_reference_parity`; không thể khai `PASS` khi thiếu golden gate và không thể báo `NOT_RUN` để che giấu FAIL. Trường hợp research case chưa chọn vẫn giữ `golden=INCONCLUSIVE` và parity metadata `NOT_RUN` vì đó là trạng thái hợp lệ.
- `research-basement` chỉ được `MAPPING_VERIFIED` khi có `golden_reference_parity` bắt buộc và PASS.
- Giữ hợp lệ các trạng thái mapping `MAPPING_VERIFIED` với case đã duyệt, và research thiếu tham chiếu `INCONCLUSIVE` thực chất.

`tests/test_job_result_contract.py` có positive/negative cases cho giả mạo nested verdict, thiếu golden, giữ FAIL bị che giấu và research case chưa có reference.

## Chưa được nghiệm thu

- Contract validation **không** tự chứng thực danh tính reviewer, nguồn dữ liệu golden hoặc mô phỏng CFD.
- SHA-256 đúng chỉ chứng minh consistency nội bộ, không phải chữ ký số hay physical ground truth.
- Cần dữ liệu IFC thực, source-authenticated reference, thẩm định công khai sai số/hội tụ, calibration, V&V vật lý và chuyên gia độc lập mới có thể nâng G09/G10.
- CI của PR và production readiness là hai trạng thái khác nhau. **G09/G10=INCONCLUSIVE**, **NOT_PRODUCTION_READY**.
