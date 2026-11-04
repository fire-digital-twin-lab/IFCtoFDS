# IFCtoFDS — Ghi chú thay đổi tiếng Việt

Tài liệu này ghi các thay đổi tái cấu trúc R10 bằng tiếng Việt.
Lịch sử phát hành trước đây vẫn nằm trong
[CHANGELOG.md](CHANGELOG.md).

## [Chưa phát hành] — R10-01 (04/11/2026)

### Đã bổ sung
- Hợp đồng sự kiện chẩn đoán trung lập ngôn ngữ, schema 1.0, mã `IFCFDS.*`.
- Hai từ điển tiếng Anh và tiếng Việt cùng bài kiểm tra tham số đồng nhất.
- Mỗi tác vụ sinh `events.jsonl` chuẩn và hai bản `events.en.log`,
  `events.vi.log`.
- Hàm tái tạo hai bản log hiển thị từ chuỗi sự kiện chuẩn.
- Sự kiện lỗi worker có loại lỗi và giai đoạn, không sao chép stack trace nhạy cảm.
- Kiểm thử hồi quy ngôn ngữ, cấu trúc tiến độ cũ và lỗi worker.

### Tương thích và giới hạn
- Không thay đổi `progress.json`, `diagnostics.json`, JSON API, các trạng thái
  nghiệm thu hoặc thuật toán IFC → FDS.
- Log đã dịch là nhật ký vận hành, không thay thế bằng chứng kiểm định độc lập.
- Chưa dịch đầy đủ giao diện, mọi lỗi API hoặc log FDS solver.

[English](CHANGELOG.en.md) · [Hướng dẫn kỹ thuật](docs/vi/observability.md)

## [Chưa phát hành] — R10-03 (04/11/2026)

### Tái cấu trúc
- Tạo cổng ConversionWorkspace và factory lưu trữ cục bộ quản lý bản nháp FDS, MappingPlan, manifest, kiểm kê và trạng thái audit.
- Tách logic tạo inventory gọn và bỏ đường dẫn máy cục bộ khỏi `ConvertVerifiedUseCase`.
- Giữ nguyên việc đọc FDS từ ổ đĩa và kiểm định nguồn IFC độc lập, với checkpoint `NOT_RUN` trước kiểm định.
- Giữ tương thích hàm khởi tạo cũ qua cầu nối chuyển tiếp độc lập.

### Kiểm thử
- Thêm test định dạng checkpoint, điều kiện niêm phong fail-closed, DI, và cấm I/O trực tiếp trong use case.
- Baseline A–F và kiểm thử solver FDS vẫn là điều kiện bắt buộc trước khi merge.

## [Chưa phát hành] — R10-04 (04/11/2026)

### Đã tái cấu trúc
- Tách bước hậu kiểm tính toàn vẹn nguồn IFC, hình học, vị trí, manifest và provenance thành `audit_integrity.py` mà không đổi quyết định gate.
- Tách đối chiếu đồ thị MEP đã lưu và thống kê coverage thành `audit_mep_coverage.py`, giữ bắt buộc đọc lại nguồn IFC độc lập.
- Bổ sung bộ đối chiếu kết quả `engine`/`runner` theo nguyên tắc fail-closed; không thay bộ kiểm định đang có thẩm quyền hoặc gọi thêm solver.
- Thêm test bảo vệ preflight NOT_RUN, lỗi MEP, thay đổi gate/verdict/evidence và thứ tự audit.

### Điều kiện an toàn
- Không thay trích xuất IFC, xuất FDS, ngưỡng khoa học, solver hoặc quyết định nghiệm thu.
- Chưa được chuyển hẳn sang `ValidationRunner` khi chưa chứng minh tương đương đầy đủ gate/bằng chứng/solver.


## [Chưa phát hành] — R10-05 (04/11/2026)

### Tính đúng đắn / An toàn
- Không còn nâng lưới `PASS` thành kết luận nghiệm thu khi mô phỏng CFD độc lập vẫn `NOT_RUN`.
- Worker trả `verdict` fail-closed kèm `verdict_reason`, giữ riêng trạng thái mesh và physics.
- Giao diện EV không suy diễn `PASS` từ HTTP 200, `COMPLETED` hoặc kết quả PASS cũ thiếu chứng cứ.
- Bổ sung kiểm thử hồi quy cho dữ liệu thiếu chứng cứ, lỗi gate, PASS giả và lỗi trạng thái hàng đợi.

### Tương thích
- Giữ các trường JSON có sẵn và phép tính khoa học; không thay thuật toán IFC/FDS hoặc solver.
- Đặc tả hợp đồng bằng chứng tại `docs/architecture/15-r10-05-scenario-verdict-contract.md`.

## [Chưa phát hành] — R10-06 (04/11/2026)

### Hạ tầng chất lượng
- Bổ sung CI riêng để kiểm tra biên dịch Python, Ruff/Pyright có phạm vi kiểm soát, ESLint, test Python và bằng chứng coverage.
- Thêm công cụ AST đo nợ kỹ thuật và cổng Git merge-base theo từng file để chặn import cục bộ, exception rộng/bare và nuốt lỗi mới.
- Coverage mới được đo và lưu bằng chứng, chưa áp ngưỡng tùy ý; hiệu năng và cảnh báo số học vẫn cần baseline thực nghiệm.
- Giữ nguyên CI Python matrix, browser và solver FDS đã được ghim phiên bản.

Chi tiết tại `docs/architecture/17-r10-06-quality-gates.md`.
