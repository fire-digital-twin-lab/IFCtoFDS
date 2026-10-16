# 22 — Phương pháp nghiên cứu và chứng minh đóng góp

## Câu hỏi nghiên cứu đề xuất

- **RQ1:** Cách áp dụng IFC geometry kernel + canonical mapping policy có cải thiện độ bảo toàn hình học và openings so với importer/exporter gốc không?
- **RQ2:** Có thể bảo toàn và kiểm toán đầy đủ cấu kiện HVAC/PCCC và IFC system/port graph qua IFC→FDS+semantic sidecar không?
- **RQ3:** Independent validator có phát hiện hiệu quả việc thiếu/sai cấu kiện/lỗ mở/sai hệ tọa độ trước khi mô hình được dùng trong FDS không?
- **RQ4 (phụ):** Chi phí tính toán (thời gian, RAM, primitive count) đổi như thế nào khi tăng geometry fidelity/MEP coverage?

RQ là gợi ý hợp lý để đóng góp bài báo; nhóm nghiên cứu có thể điều chỉnh sau khi literature review, nhưng không đổi ngưỡng/số liệu hậu nghiệm để tô đẹp kết quả.

## Đóng góp có thể bảo vệ được

1. Semantic-aware structural/MEP mapping chứ không chỉ polygon geometry conversion.
2. Truy vết IFC→FDS bằng manifest có lý do xử lý và quan hệ hệ thống.
3. Independent three-level validation (source/canonical/serialized/effective FDS) và mutation test.
4. Reproducible benchmark trên IFC samples và mô hình thực tế có license sử dụng.

Chỉ **fork** và thêm dependency IfcOpenShell không tự tạo tính mới khoa học.

## Experimental protocol

- Freeze source commits, IFC hashes, settings/tolerances, versions, hardware; viết pre-registered metrics.
- Baseline A: upstream IFCtoFDS release; B: Bonsai+BFDS (nếu có nguồn lực, đo manual effort); C: hybrid verified.
- Cùng IFC/geometry scope, run nhiều lần, so thời gian+RAM+coverage+IoU+openings+MEP edge precision/recall+traceability+errors caught.
- Separate conversion accuracy vs FDS solver physical fidelity; không trộn hai thước đo.
- Với hình học hở/mesh non-manifold, không tính volumetric IoU như thể tích đáng tin cậy.
- Bổ sung ablation: C without MEP graph, C without independent validation, geometry fallback approaches; thể hiện đóng góp thành phần.

## Đánh giá thiên lệch và ngoại suy

- Bộ ba IFC mẫu nhỏ có thể thiếu MEP thực, không đủ khẳng định full HVAC/PCCC.
- BFDS cần thao tác con người nên metric time phải ghi setup/rework, không chỉ export click.
- IfcOpenShell mạnh về IFC geometry nhưng không tự bảo đảm accuracy của FDS `OBST/GEOM` hoặc vật lý quạt.
- Hạn chế khả năng tổng quát hóa được báo theo IFC schema, element types và model complexity đã thử.
- Nêu cả failure cases và vùng model validator trả `INCONCLUSIVE`.
