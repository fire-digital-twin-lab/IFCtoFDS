# START PROMPT — Đưa cho Coding Agent trong repository IFCtoFDS

Bạn đang làm việc với fork chính thức `https://github.com/fire-digital-twin-lab/IFCtoFDS`, upstream `ProfRino/IFCtoFDS`. Nhiệm vụ là **thực hiện** master prompt chuyển đổi thành Verified IFC-to-FDS Mapping Framework, bắt đầu bằng kiểm toán và triển khai từng giai đoạn; không chỉ viết kế hoạch.

**Trước khi sửa bất cứ tệp code nào:**

1. Đọc toàn bộ `AGENTS.md` và `README.md` của gói context này.
2. Đọc toàn bộ các file `docs/context/00_PROJECT_BRIEF.md` đến `docs/context/25_DELIVERABLES.md` theo thứ tự.
3. Đọc `docs/MASTER_PROMPT_IFCtoFDS_IfcOpenShell_End_to_End.md` cùng tài liệu audit và plan trong `docs/reference/`.
4. Kiểm tra HEAD, working tree, remote/fork/upstream, source code thật, test scripts, dependencies và các khác biệt so với docs.
5. Thực hiện Phase 0 và report trực tiếp source paths, SHA, test commands/evidence. Giữ nguyên working tree nếu đang bẩn; làm branch/worktree riêng.
6. Phân rã PR có acceptance gates, rồi **bắt đầu triển khai trực tiếp** vertical slice IFC → Canonical → FDS → independent validation theo lộ trình; sau mỗi PR phải có test và audit độc lập.

**Phạm vi chính:** kết cấu/kiến trúc, HVAC, PCCC, IFC entities/relationships/geometry, traceability, domain scopes, geometry openings, effective FDS geometry. **Chưa làm:** HRR, kịch bản cháy, AI/ML, mô phỏng vận hành quạt/sprinkler, Digital Twin realtime.

**Quy tắc bất biến:** không mất source entity im lặng, không tự bịa MEP/geometry/connectivity, không đổi tên/tự sửa IFC gốc, không khẳng định 100% chính xác nếu thiếu dữ liệu/công cụ nghiệm thu, không tự merge main. Giữ AGPL/copyright.

Nếu không có quyền GitHub, source IFC công trình hoặc FDS solver, hãy hoàn thành phần có thể chạy bằng fixtures và báo cụ thể `BLOCKED/NOT_RUN`; không che giấu. Khi thiếu quyết định của kỹ sư (tolerance, domain scope, MEP geometry purpose), dùng conservative `REVIEW_REQUIRED`/`INCONCLUSIVE` thay vì chế biến kết quả.

**Đầu ra vòng đầu tiên:** `docs/audit/00-baseline.md`, `docs/architecture/as-is.md`, `docs/architecture/target.md`, `docs/roadmap.md`, risk register, regression fixtures/reproducer và một PR nhỏ có test thực tế. Sau đó tiếp tục đến khi CLI/Web verified có thể chạy end-to-end trong phạm vi đã kiểm chứng.
