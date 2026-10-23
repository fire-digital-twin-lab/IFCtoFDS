# 05 - Ports và adapters

Đường dẫn tương đối với `ifc_to_fds/`; tên port giữ contract đã công bố.

| Port / seam | Implementation mặc định |
| --- | --- |
| IfcReaderPort / InventoryReaderPort | `modules/bim/infrastructure/ifc/reader.py:IfcOpenShellReader` |
| ModelPreparationPort | `application/workflows/prepare_model.py:ModelPreparer` |
| FdsExporterPort | `modules/fds/infrastructure/exporter.py:FdsExporter` |
| ValidationEnginePort | `modules/verification/infrastructure/engine_adapter.py:IndependentValidationEngine` |
| ConversionWorkspacePort | `modules/artifacts/infrastructure/conversion_workspace.py:LocalConversionWorkspaces` |
| ArtifactRepositoryPort | `modules/artifacts/infrastructure/filesystem_repository.py:LocalFilesystemArtifactRepository` |
| ReferenceRepositoryPort | `modules/reference/infrastructure/filesystem_repository.py:FilesystemReferenceRepository` |
| JobStore | `modules/jobs/infrastructure/sqlite_repository.py` |
| WorkerProcesses | `modules/jobs/infrastructure/worker_process.py` |
| JobRetention | `modules/jobs/infrastructure/retention.py` |
| Solver runner callable | `modules/verification/infrastructure/fds/solver_process.py` |
| Reference reader callable | Reference public API `inspect_case` |

Container inject reader/exporter/workspace/engine/reference reader vào workflows. Validation adapter inject solver; factory Jobs nối store/process/retention/clock. Constructor/function cũ giữ default qua bốn compatibility bridge trong policy. Khi đã cung cấp dependencies giả, Jobs không tạo SQLite/process thật.

FdsExporterPort nhận `model`, `cell_size=None`, `mapping_plan=None`, trả tuple FDS/manifest. Policy được xử lý trước serializer. InspectIfcUseCase nhận model preparer, không import helper qua module audit.

Workspace nhận `CheckpointPayload` thay vì import helper application. Workspace sở hữu thư mục tạm hoặc thư mục caller cung cấp, ghi checkpoint NOT_RUN và đọc lại artifact cho audit. Owner temporary geometry package được giữ tới khi kết quả hết sử dụng. Geometry package service dùng protocol payload store; checksum/seal thuần nằm trong algorithms.

HTTP factory nhận JobManager thay được và quản lý shutdown. Frontend viewer nhận geometry client; features nhận jobs/artifacts clients cùng state/callback cần dùng. Không tạo abstraction cho mọi phép tính mesh thuần.
