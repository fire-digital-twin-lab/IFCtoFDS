# 02 — Quyết định kiến trúc

Một ứng dụng, một bản phân phối; module có API/contracts và kiểm thử riêng. Phát triển riêng nghĩa là thay đổi qua hợp đồng ổn định, chưa phải phát hành từng module thành dịch vụ.

| Bounded context | Quyền sở hữu |
| --- | --- |
| BIM | Nguồn, identity, units, placement, inventory, quan hệ MEP |
| Simulation | Scope, simulation domain, vai trò, biểu diễn, MappingPlan |
| Verification | Findings, evidence, gates và kết luận độc lập |
| Reference | Candidate, approval, integrity, intentional deltas, parity |

Geometry, FDS, Artifacts và Jobs là module kỹ thuật; không bắt mỗi module có aggregate/repository/domain event. HVAC/PCCC thuộc BIM trong phạm vi ánh xạ hiện tại, chưa có context mô phỏng vận hành riêng.

SOLID được thực hiện bằng tách điều phối khỏi lưu trữ/serialization/kiểm chứng, inject dependency và giữ port nhỏ đúng lời gọi. Adapter thay thế phải giữ semantics lỗi, hủy, lifecycle và kết quả. Hàm thuần vẫn có thể là hàm; không thêm abstraction chỉ để tăng số tầng.

Giữ Pydantic, schema, thuật toán, rounding, ID allocator và acceptance. Frontend giữ IIFE và file://, chưa đổi framework/bundler. CanonicalModel không phải transaction aggregate cho cả công trình. Các model hiện vẫn mutable; kiểm tra/copy/finalize bảo vệ từng bước sử dụng.
