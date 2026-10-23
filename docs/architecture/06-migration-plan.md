# 06 - Trạng thái triển khai

Khảo sát đầu ở tài liệu 11, đợt refactor đầu ở 12; kế hoạch đợt tiếp theo ở 13 và kết quả P00–P10 ở [14](14-ket-qua-to-chuc-ma.md).

| Phase | Kết quả triển khai |
| --- | --- |
| P00 | Chụp working tree trước thay đổi; baseline; tái hiện và sửa vòng import ở worker mới |
| P01 | Ownership ADR, dependency policy và facade registry; positive/negative import tests |
| P02 | Artifacts/workspace sở hữu I/O, checkpoint payload qua contract |
| P03 | BIM tách native IFC/MEP I/O và so graph thuần |
| P04 | Geometry tách algorithms/native/cache/payload/package orchestration |
| P05 | Simulation policies, FDS serializer/parser và implementation digest đúng owner |
| P06 | Verification/Reference tách application và adapters; giữ engine active và audit độc lập |
| P07 | Jobs inject store/process/retention/clock; supervision tick kiểm tra được không cần SQLite |
| P08 | Workflows/ports/CLI/routes/adapters và shared helpers về đúng trách nhiệm |
| P09 | Frontend bootstrap/shell/features/API clients; dọn listener, worker và viewer khi destroy |
| P10 | Tests chia theo owner; README từng module; CI/lifecycle/browser checks và packaging |

[Migration manifest](module-layout-migration.json) ghi 51 implementation moves cùng source/target hashes và bằng chứng; [test layout](test-layout.json) ghi đường dẫn test trước/sau. Model Pydantic vẫn có một định nghĩa; chưa chuyển engine sang runner/checkers hoặc bỏ import tương thích.

HTTP, Chromium và FDS thật đã chạy được ở đợt này. Nghiệm thu dữ liệu nghiên cứu riêng còn thiếu IFC/reference thực tế; số đo công khai không thay thế nghiệm thu dự án. Không thay snapshot/thuật toán để che sai lệch. Báo cáo 14 phân biệt PASS, lỗi kế thừa và phần chưa chạy.
