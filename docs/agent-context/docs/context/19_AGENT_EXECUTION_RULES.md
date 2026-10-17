# 19 — Quy tắc thi hành Coding Agent + Independent Auditor

## Roles và quyền

- **Coding agent:** thiết kế, code, test, tài liệu hóa và chuẩn bị PR.
- **Auditing agent:** truy xuất repo/test artifacts độc lập, cố gắng tái hiện lỗi và đánh giá evidence; không tự chấm dựa trên tường thuật của coding agent.
- **Human engineer:** duyệt những quyết định geometry simplification, ambiguous multi-IFC alignment và MEP physical representation ngoài phạm vi quyết định tự động.

## Git safety

```bash
git status --short
git branch --show-current
git rev-parse HEAD
git remote -v
git fetch --all --tags
```

- Xác nhận đúng `fire-digital-twin-lab/IFCtoFDS`, `ProfRino/IFCtoFDS` upstream, license.
- Nếu working tree bẩn, không phá thay đổi; dùng worktree/branch tách biệt. Không force push/merge main tự động.
- Mỗi PR mô tả liên kết requirement IDs, findings IDs và tests IDs.
- Lưu source input checksum trước test, tránh git add các IFC công trình riêng khi chưa được phép.

## Test/report command policy

- Chạy `node --check` cho JS, smoke worker scripts, các test hiện có sau mỗi đổi nguồn JS.
- Chạy `node scripts/generate-inline-parse-worker.js` và `node scripts/generate-inline-export-worker.js` nếu thay nguồn tương ứng; kiểm tra diff bundle.
- Chạy Python unit/integration, lints/type-check khi có package.
- Benchmark chỉ với fixture có thể chia sẻ, môi trường khóa; source IFC private dùng local artifact không push.
- Mọi command report exit code, timestamp và commit. Không claim “tested” từ code reading.

## Evidence report template

```markdown
# Engineering Progress Report — <phase>
- Repo/branch/HEAD/worktree: ...
- Implemented: <module/functions> ...
- Requirements: REQ-xxx...
- Baseline bug reproducibility: ...
- Tests actually run: command | exit | elapsed | environment
- Metrics observed (raw): ...
- Blocked/not run: ...
- New/remaining P0/P1/P2: ...
- Artifacts and SHA-256: ...
- PR link: ...
- Recommended next phase + acceptance status: ...
```

## Chủ động xử lý lỗi

- `UNSUPPORTED` có description/IfcClass/schema/placement/geometryRef thay vì hidden skip.
- `INCONCLUSIVE` có minimal reproduction/data request.
- Khi thiếu solver, FDS geometry static validation vẫn thực hiện; solver stage NOT_RUN.
- Một patch chỉ sửa UI không được đóng P0 geometry.

## An toàn dependencies

- Pin runtime/library versions (IfcOpenShell, Python, Node, FastAPI nếu dùng), không cargo-cult install/unpinned CDN.
- Dữ liệu file IFC/FDS là đầu vào không đáng tin cậy; kiểm soát kích thước, loop/mesh explosion, memory/timeouts, path traversal, file/zip bombs và log injection.
- Verify AGPL/LGPL và licensing của assets/models/tests trước public push.

## Quy tắc “stop-the-line”

Dừng nghiệm thu hoặc việc gắn nhãn Verified nếu phát hiện: mất opening quan trọng; sai hệ tọa độ; source inventory drop im lặng; HVAC/PCCC source count mâu thuẫn; traceability đứt; validator dùng lại output giả làm ground truth; solver geometry lỗi fatal chưa được xử lý trong gate bắt buộc.
