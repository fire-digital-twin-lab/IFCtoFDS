"""Run a read-only evidence audit of a persisted IFCtoFDS job.

Usage:
    python scripts/audit_job_acceptance.py /path/to/job --mode scenario

Returns 0 for structurally/integrity-valid data, 2 for invalid or missing
evidence. Does not claim scientific simulation verification.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ifc_to_fds.adapters.jobs.acceptance_audit import audit_persisted_job


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Kiểm toán chỉ đọc hồ sơ đầu ra của một công việc IFCtoFDS"
    )
    parser.add_argument("directory", type=Path, help="Thư mục công việc cần kiểm toán")
    parser.add_argument(
        "--mode",
        choices=("convert", "scenario", "preview", "inventory"),
        required=True,
        help="Loại công việc được khai báo trước khi đọc kết quả",
    )
    args = parser.parse_args()
    report = audit_persisted_job(args.directory, args.mode)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["audit_outcome"] in ("EVIDENCE_VALID", "STRUCTURE_VALID") else 2


if __name__ == "__main__":
    raise SystemExit(main())
