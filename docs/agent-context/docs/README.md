# IFCtoFDS — Bộ ngữ cảnh đầy đủ cho coding agent

**Phiên bản context:** 2026-10-16 · **Ngôn ngữ chính:** Tiếng Việt; giữ thuật ngữ chuẩn tiếng Anh khi cần.  
**Repository:** https://github.com/fire-digital-twin-lab/IFCtoFDS  
**Upstream:** https://github.com/ProfRino/IFCtoFDS  
**Tác vụ:** nâng cấp bản fork thành **Verified IFC-to-FDS Mapping Framework**.

## Bắt đầu từ đây

1. Đọc `AGENTS.md` (quy tắc thi hành an toàn và ưu tiên chứng cứ).
2. Đọc `docs/context/00_PROJECT_BRIEF.md`, `01_REQUIREMENTS.md`, `02_SCOPE_AND_NON_GOALS.md`.
3. Đọc `docs/context/05_AS_IS_CODEBASE.md`, `06_CONFIRMED_AUDIT_FINDINGS.md`, `07_TARGET_ARCHITECTURE.md`.
4. Đọc `docs/context/08_CANONICAL_DATA_MODEL.md` tới `17_ACCEPTANCE_GATES.md` trước khi sửa exporter hoặc IFC parser.
5. Đọc `docs/context/18_IMPLEMENTATION_ROADMAP.md`, `19_AGENT_EXECUTION_RULES.md`, `20_SOURCE_EVIDENCE_REGISTER.md`.
6. Đọc lại **`docs/MASTER_PROMPT_IFCtoFDS_IfcOpenShell_End_to_End.md`** được giữ nguyên từ yêu cầu trước.
7. Đối chiếu với repository *thực tế*; bắt đầu Phase 0; không khẳng định các kết quả chưa chạy lại.

## Danh mục tài liệu

| Tệp | Chủ đề |
|---|---|
| `AGENTS.md` | Chỉ dẫn bắt buộc cho coding agent |
| `docs/context/00_PROJECT_BRIEF.md` | Tóm tắt đề tài, mục tiêu, nguồn chứng cứ |
| `docs/context/01_REQUIREMENTS.md` | Yêu cầu có ID, thứ tự ưu tiên và tính kiểm thử |
| `docs/context/02_SCOPE_AND_NON_GOALS.md` | Trong/ngoài phạm vi, giới hạn khoa học |
| `docs/context/03_HISTORY_AND_DECISIONS.md` | Chuỗi trao đổi, quyết định, phân biệt lịch sử và xác nhận |
| `docs/context/04_DOMAIN_GLOSSARY.md` | Khái niệm IFC, FDS, HVAC/PCCC, geometry, validation |
| `docs/context/05_AS_IS_CODEBASE.md` | Cấu trúc fork/upstream và chức năng đang có |
| `docs/context/06_CONFIRMED_AUDIT_FINDINGS.md` | Các phát hiện code audit và điều kiện tái hiện |
| `docs/context/07_TARGET_ARCHITECTURE.md` | Thiết kế hybrid Python/JavaScript + kiến trúc module |
| `docs/context/08_CANONICAL_DATA_MODEL.md` | Schema dữ liệu chuẩn và quan hệ định danh |
| `docs/context/09_GEOMETRY_AND_FDS_MAPPING.md` | Quy tắc biến đổi hình học, OBST/GEOM/HOLE |
| `docs/context/10_MEP_HVAC_PCCC.md` | Phân tích semantic và hệ thống MEP |
| `docs/context/11_MULTIFILE_FEDERATION_SCOPE.md` | Nhiều IFC, tọa độ và lọc phạm vi mô hình |
| `docs/context/12_PROVENANCE_AND_ALIAS.md` | GlobalId, manifest, hash, alias, audit trail |
| `docs/context/13_VALIDATION_METHODS.md` | Kiểm toán độc lập và sai số đo lường |
| `docs/context/14_UI_AND_WORKFLOWS.md` | Hành trình người dùng và thiết kế giao diện |
| `docs/context/15_API_AND_INTEGRATION.md` | CLI → FastAPI → Web, integration contract |
| `docs/context/16_TEST_AND_BENCHMARK.md` | Bộ fixture, test matrix, benchmark nghiên cứu |
| `docs/context/17_ACCEPTANCE_GATES.md` | Definition of Done, severity, cổng nghiệm thu |
| `docs/context/18_IMPLEMENTATION_ROADMAP.md` | PR/giai đoạn phụ thuộc, yêu cầu evidence |
| `docs/context/19_AGENT_EXECUTION_RULES.md` | Git workflow, kiểm thử, báo cáo và giới hạn quyền |
| `docs/context/20_SOURCE_EVIDENCE_REGISTER.md` | Dữ liệu đã thấy, chưa có, nguồn tham khảo |
| `docs/context/21_BASEMENT_CASE_STUDY.md` | Ca B1/B2 lịch sử: không dùng số liệu làm ground truth |
| `docs/context/22_RESEARCH_METHOD.md` | Câu hỏi/đóng góp nghiên cứu và benchmark |
| `docs/context/23_RISKS_AND_OPEN_QUESTIONS.md` | Các rủi ro, giả định cần xác minh, quyết định còn mở |
| `docs/context/24_TRACEABILITY_MATRIX.md` | Requirement → module → test → bằng chứng |
| `docs/context/25_DELIVERABLES.md` | Artifacts mỗi lần chạy và mỗi release |
| `docs/MASTER_PROMPT_IFCtoFDS_IfcOpenShell_End_to_End.md` | Nguyên văn master prompt trước, đóng gói để agent đọc offline |
| `docs/reference/CODE_AUDIT_2026-10-15.md` | Bản audit gốc, snapshot lịch sử |
| `docs/reference/IMPLEMENTATION_PLAN_PREVIOUS.md` | Kế hoạch v0.2.0 đã lập trước |

## Quy tắc đọc và thứ tự ưu tiên

1. **Yêu cầu trực tiếp mới nhất từ người dùng**, nếu có, ưu tiên hơn bản context này.
2. Những **quyết định đã chốt** và ranh giới phạm vi ở `01`, `02`, `03` ưu tiên hơn ý tưởng khám phá cũ.
3. Các **phát hiện mã nguồn có chứng cứ** có độ tin cậy cao hơn các giả thuyết từ trao đổi trước; phải xác minh lại theo HEAD đang làm việc.
4. Các **số liệu B1/B2 lịch sử** không thay thế dữ liệu IFC/FDS thực tế hiện hành.
5. Tài liệu này là **ngữ cảnh và đặc tả để phát triển**, KHÔNG chứng minh bản fork hiện đã đáp ứng các yêu cầu.

## Cách sử dụng

Giữ `AGENTS.md`, `README.md` và thư mục `docs/` của bộ này trong repository; không đè `README.md` gốc mà không merge nội dung. Có thể đặt bản này vào `docs/agent-context/` rồi dẫn chiếu bằng một đoạn ngắn trong README/AGENTS hiện có. Nếu đã có `AGENTS.md`, phải rà soát và hợp nhất thay vì ghi đè tự động.

**Chỉ thị khởi động:** “Đọc AGENTS.md, README của gói ngữ cảnh và master prompt. Thực hiện Phase 0 trong nhánh/worktree sạch, viết baseline report có bằng chứng trước khi thay đổi code.”
