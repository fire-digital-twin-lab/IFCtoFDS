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
