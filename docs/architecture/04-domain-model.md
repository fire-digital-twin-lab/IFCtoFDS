# 04 — Model và từ vựng

Domain giữ định nghĩa Pydantic duy nhất; các context công bố contracts bằng re-export.

| Chủ sở hữu | Model/khái niệm |
| --- | --- |
| BIM | SourceIdentity/Metadata, CanonicalElement/Model, Opening/StoreyReference, MEPGraph/System/Connection, PortReference |
| Simulation | SpatialScope, ScopeDecision, MappingStrategy/Decision/Plan, simulation domain |
| Verification | Finding, Severity, GateStatus/Result, AuditConfig, AcceptanceReport |
| Reference | GoldenReference, ReferenceApproval, IntentionalDelta, ReferenceParityResult, bundle đã kiểm tra |
| Geometry/FDS | BoundingBox, TriangleMesh, SerializationResult, primitive references |

SourceIdentity hiện tạo entity_key từ `source_id:step_id`. Không dùng GlobalId đơn lẻ làm khóa duy nhất giữa nhiều nguồn.

- Scope lựa chọn, simulation domain và clipping viewer là ba khái niệm khác nhau.
- MappingPlan giữ ý định; primitive IDs thuộc serialization result. Serializer kiểm tra lại plan với quyền biểu diễn, phạm vi và bounds.
- Gate chưa chạy không được suy thành PASS. Mapping verified không tự trở thành simulation verified.
- Candidate tham chiếu không tự được phê duyệt; checksum không thay thế kiểm tra nội dung/quan hệ.
- Có thiết bị/ống trong IFC không có nghĩa đã mô hình hóa vật lý vận hành.

Model không đồng loạt frozen. AcceptanceReport được hoàn thiện rồi serialize, không phải object Python immutable. Các model Reference khai báo từ vựng không thay thế bộ kiểm tra bundle thực thi.
