# 10 — Tái lập và baseline

Commit nền của lần refactor: `f0c6d9c02342312266f2cfb8f9102833640061c3`. Fixture/snapshot trong tests/baseline được giữ nguyên; test đối chiếu kiểm tra hash nguồn và dữ liệu semantic. Không tự ghi lại snapshot khi có lỗi.

Các trường thời gian hoặc đường dẫn chỉ được normalize khi đã xác định không thuộc hợp đồng. Quyết định mapping, FDS, primitive identity, openings, graph MEP, gate status và bằng chứng không được bỏ qua để làm parity đạt.

Provenance hiện được ghi trong `report.metrics.execution_provenance`: phiên bản Python, platform/system/machine và một số dependency. Source hash và schema nằm trong các model/manifest. Sự tồn tại của model ExecutionEnvironment không có nghĩa mọi trường của model đã được điền vào mọi run.

Engine JavaScript được so trực tiếp với source của commit nền trên ba IFC công khai: inventory JSON và FDS hybrid/GEOM phải giống chính xác. Worker thường/inline cùng một nguồn mã; generator chuẩn hóa newline để LF/CRLF cho cùng bundle.

CSS manifest ghi hash của chuỗi khai báo trước khi tách; ghép các tệp theo đúng thứ tự phải giữ nguyên hash. Kiểm tra wheel ngoài checkout để phát hiện tài nguyên chỉ tồn tại trong source tree.

Ghi riêng phiên bản thư viện, cấu hình cache, số luồng và điều kiện môi trường khi đo hiệu năng hoặc chạy solver. Không tuyên bố nhanh hơn chỉ từ việc chia thư mục.
