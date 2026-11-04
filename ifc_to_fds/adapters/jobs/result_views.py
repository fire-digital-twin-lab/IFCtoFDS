"""HTTP-only result views. A findings page is not a persisted acceptance report.

The source result was validated against its complete contract before reaching
this module. Pagination never modifies or re-seals the on-disk evidence.
"""

from __future__ import annotations

from typing import Any, TypedDict


class FindingsPageMetadata(TypedDict):
    offset: int
    limit: int | None
    returned: int
    total: int
    has_more: bool
    canonical_result_complete: bool


def make_findings_page(
    result: dict[str, Any], *, mode: str, offset: int, limit: int | None
) -> dict[str, Any]:
    """Create a marked, non-canonical page from a verified conversion result.

    `findings_count` intentionally remains the total from the original
    acceptance report; the `findings_page` field gives the number actually
    returned. This view must not be mistaken for a full ResultContract.
    """
    if mode != "convert":
        raise ValueError("Finding pagination is only supported for conversion jobs")
    findings = result.get("findings")
    if not isinstance(findings, list):
        raise ValueError("Conversion result does not contain a findings list")
    total = len(findings)
    if result.get("findings_count") != total:
        raise ValueError("Canonical result findings_count is inconsistent")
    if offset < 0 or (limit is not None and limit < 1):
        raise ValueError("Invalid findings pagination parameters")

    end = total if limit is None else min(total, offset + limit)
    page_items = findings[offset:end]
    metadata: FindingsPageMetadata = {
        "offset": offset,
        "limit": limit,
        "returned": len(page_items),
        "total": total,
        "has_more": end < total,
        "canonical_result_complete": False,
    }
    view = dict(result)
    view["result_view"] = "FINDINGS_PAGE"
    view["findings"] = page_items
    view["findings_offset"] = offset  # retained for existing UI consumers
    view["findings_limit"] = limit
    view["findings_page"] = metadata
    return view
