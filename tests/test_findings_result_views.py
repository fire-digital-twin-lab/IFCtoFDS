"""Trang phát hiện là bản xem HTTP, không phải báo cáo nghiệm thu đầy đủ."""

import pytest

from ifc_to_fds.adapters.jobs.result_views import make_findings_page


def _canonical_result():
    return {
        "status": "REJECTED",
        "mapping_status": "REJECTED",
        "simulation_status": "REJECTED",
        "findings": [
            {"code": "A-01", "severity": "P1"},
            {"code": "A-02", "severity": "P2"},
            {"code": "A-03", "severity": "P1"},
        ],
        "findings_count": 3,
        "blocker_count": 2,
    }


def test_page_is_explicitly_noncanonical_and_source_is_unchanged():
    full = _canonical_result()
    page = make_findings_page(full, mode="convert", offset=1, limit=1)
    assert page["result_view"] == "FINDINGS_PAGE"
    assert page["findings_page"] == {
        "offset": 1,
        "limit": 1,
        "returned": 1,
        "total": 3,
        "has_more": True,
        "canonical_result_complete": False,
    }
    assert page["findings"] == [{"code": "A-02", "severity": "P2"}]
    assert page["findings_count"] == 3
    assert page["blocker_count"] == 2
    assert page["status"] == "REJECTED"
    assert "result_view" not in full
    assert len(full["findings"]) == 3


def test_end_of_page_and_empty_page_preserve_original_totals():
    full = _canonical_result()
    last = make_findings_page(full, mode="convert", offset=2, limit=2)
    assert last["findings_page"]["returned"] == 1
    assert last["findings_page"]["has_more"] is False
    assert last["findings_count"] == 3

    empty = make_findings_page(full, mode="convert", offset=100, limit=3)
    assert empty["findings"] == []
    assert empty["findings_page"]["returned"] == 0
    assert empty["findings_page"]["total"] == 3
    assert empty["findings_page"]["canonical_result_complete"] is False


@pytest.mark.parametrize("mode", ["scenario", "preview", "inventory", "unknown"])
def test_nonconversion_modes_reject_findings_pagination(mode):
    with pytest.raises(ValueError, match="only supported for conversion"):
        make_findings_page(
            {"status": "COMPLETED", "findings": []},
            mode=mode, offset=0, limit=1,
        )


@pytest.mark.parametrize("offset,limit", [(-1, 1), (0, 0), (0, -1)])
def test_invalid_page_parameters_are_rejected(offset, limit):
    with pytest.raises(ValueError, match="Invalid findings pagination"):
        make_findings_page(
            _canonical_result(), mode="convert", offset=offset, limit=limit
        )


def test_mismatched_full_findings_count_is_not_treated_as_a_page():
    full = _canonical_result()
    full["findings_count"] = 99
    with pytest.raises(ValueError, match="inconsistent"):
        make_findings_page(full, mode="convert", offset=0, limit=1)


def test_missing_findings_is_not_fabricated():
    full = _canonical_result()
    del full["findings"]
    with pytest.raises(ValueError, match="does not contain"):
        make_findings_page(full, mode="convert", offset=0, limit=1)
