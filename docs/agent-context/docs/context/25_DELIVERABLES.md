# 25 — Đầu ra bắt buộc của phần mềm và của coding agent

## Cấu trúc mỗi run (đề xuất, chưa tồn tại tự động trong upstream)

```text
outputs/<run-id>/
├── converted.fds
├── source-files.json
├── source-inventory.json
├── canonical-index.json
├── geometry/                      # sidecar/chunks nếu cần
├── mep-systems.json
├── mep-connectivity.json
├── scope-decisions.json
├── mapping-manifest.json
├── geometry-comparison.csv
├── findings.csv
├── acceptance.json
├── acceptance-report.html
├── conversion-config.json
└── run-metadata.json
```

## Mỗi file phải có ít nhất

| File | Hợp đồng |
|---|---|
| `.fds` | FDS syntax hợp lệ trong mức có thể xác thực; có source comment hợp lệ nếu hỗ trợ |
| `source-files.json` | filename, sha, schema, coord/unit transform, warnings |
| `source-inventory.json` | mọi phần tử đã xác định + reason/mapping status |
| `mep-systems.json`, `mep-connectivity.json` | system members, ports/edges explicit/unknown |
| `scope-decisions.json` | chính sách lọc và phần tử giao biên |
| `mapping-manifest.json` | IFC source key ↔ FDS primitives ↔ policy + provenance |
| `geometry-comparison.csv` | per object geometry metrics cùng đơn vị/dung sai |
| `findings.csv` | finding ID, severity, status, evidence, remediation |
| `acceptance.json` | ACCEPTED/REJECTED/BLOCKED cùng nguyên nhân, gate statuses |
| `acceptance-report.html` | bản dễ đọc cho BIM/FDS engineer |
| `conversion-config.json` | snapshot settings, scope, solver/cell size và approval |
| `run-metadata.json` | commit/tool versions/OS/input-output hashes, timings, method versions |

## Mỗi PR / Phase phải bàn giao

- PR description nêu requirement IDs, design, files changed, code/test coverage.
- Changelog/architecture/ADR updates và limitations.
- Test commands + run logs actual, tests blocked lý do.
- Report audit độc lập P0/P1 và status nghiệm thu đúng giai đoạn.
- Không tự merge main khi review chưa xong.

## Bàn giao cuối phạm vi project

- Fork Web vẫn hoạt động Quick mode và Verified mode thực.
- Python CLI và package có requirements lock + installation guide Windows/Linux.
- Artifact set sinh được end-to-end trên fixture nguồn và bộ ca công trình khi có.
- Unit/integration/benchmark suite, technical reference, usage docs, reproducibility docs.
- Bảng so sánh upstream, hybrid, BFDS nếu có dữ liệu thực nghiệm; không bịa số.
- Báo cáo giới hạn, source coverage, unsupported types, remaining risk và future scope (simulation fire/AI không thực hiện trong phase này).

## Những gì không nên copy vào git

Không tự đưa IFC công trình nhạy cảm/private, FDS công trình chưa được phép công bố, dữ liệu cá nhân, credentials, logs/paths máy tính lên public repository. Chỉ xuất artifacts có quyền chia sẻ rõ.
