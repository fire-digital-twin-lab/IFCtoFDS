# Kiến trúc IFCtoFDS

Cập nhật 23/10/2026: Modular Monolith + DDD có chọn lọc + SOLID, dùng ports/adapters ở ranh giới kỹ thuật.

| Tài liệu | Nội dung |
| --- | --- |
| [01](01-current-architecture.md) | Bản đồ mã đang chạy |
| [02](02-target-architecture.md) | Context và quyết định thiết kế |
| [03](03-dependency-rules.md) | Quy tắc dependency |
| [04](04-domain-model.md) | Model, thuật ngữ và ownership |
| [05](05-ports-and-adapters.md) | Ports và wiring |
| [06](06-migration-plan.md) | Trạng thái triển khai |
| [07](07-artifact-model.md) | Artifacts và checkpoint |
| [08](08-validation-architecture.md) | Kiểm chứng độc lập |
| [09](09-legacy-vs-verified.md) | Hai đường chuyển đổi |
| [10](10-reproducibility.md) | Baseline và tái lập |
| [11](11-ke-hoach-refactor-module-va-giao-dien.md) | Khảo sát trước triển khai |
| [12](12-trien-khai-modular-ddd-solid.md) | Báo cáo thực hiện và kiểm tra |
| [13](13-review-va-ke-hoach-to-chuc-ma.md) | Review cấu trúc, tham khảo repo mẫu và kế hoạch tổ chức mã tiếp theo |
| [14](14-ket-qua-to-chuc-ma.md) | Kết quả triển khai P00–P10, kiểm chứng và giới hạn nghiệm thu |
| [15](15-danh-gia-chat-luong-dau-ra.md) | Đánh giá từng chức năng, chất lượng đầu ra thực tế và khoảng trống nghiệm thu |
| [16](16-ket-qua-sua-hinh-hoc-va-kiem-chung.md) | Kết quả sửa hình học/timeout Institute, fixture MEP 3D, solver/PyroSim và tests nghiệm thu |
| [17](17-nghiem-thu-module-verification.md) | Sửa lưới/log solver, kiểm chứng HOLE/OPEN và surface GEOM native, bàn giao PyroSim và điều kiện nghiệm thu còn thiếu |
| [18](18-sua-loi-review-verification.md) | Sửa bốn phát hiện review: khe biên và topology, dung sai xuyên workflow, gán SURF theo tam giác, checksum tái lập sau checkout |
| [19](19-nghiem-thu-module-reference.md) | Củng cố Reference: phê duyệt thống nhất, integrity xuyên bundle/payload, registry và audit từ artifacts đã lưu |
| [20](20-nghiem-thu-module-artifacts.md) | Củng cố Artifacts: kiểm geometry staging, khóa publication, rollback/payload, inspector checksum và checkpoint an toàn |

01–10 mô tả mã hiện tại; 11–13 giữ bối cảnh khảo sát, đợt đầu và kế hoạch tiếp theo; 14 ghi kết quả tổ chức mã; 15 đánh giá chất lượng trước sửa; 16 ghi đợt sửa hình học; 17 ghi đợt hoàn thiện kiểm chứng trước review; 18 ghi kết quả sửa Verification; 19 ghi đợt củng cố Reference; 20 ghi đợt củng cố Artifacts và giới hạn nghiệm thu.

Kế hoạch 13 đã triển khai trong working tree. [Migration manifest](module-layout-migration.json) ghi 51 implementation moves; [dependency policy](dependency-policy.json), [facade registry](compatibility-imports.json) và [ADR ownership](decisions/0001-module-ownership.md) được kiểm tra bằng tests kiến trúc.
