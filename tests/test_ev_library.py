import re
import pytest

from ifc_to_fds.fire.ev_library import (
    EV_LIBRARY_VERSION,
    EVPreset,
    library_digest,
    list_ev_presets,
    load_ev_preset,
)


def _sample_valid_data():
    return {
        "version": EV_LIBRARY_VERSION,
        "vehicle_class": "auto",
        "chemistry": "NMC",
        "pack_kwh_range": (40.0, 100.0),
        "peak_hrr_mw_range": (2.0, 7.0),
        "t_alpha_s": (150.0, 600.0),
        "growth": "t-squared",
        "yields": {
            "co": (0.05, 0.2),
            "soot": (0.08, 0.2),
            "hf": (0.01, 0.05),
        },
        "citations": [{"source": "Test Source", "detail": "Test detail"}],
        "confidence": "medium",
        "notes": "Test notes",
    }


def test_load_ebike_lfp_preset_has_ranges_and_citation():
    p = load_ev_preset("e-bike", "LFP")
    assert p.pack_kwh_range == (0.5, 3.0)
    assert p.confidence in ("low", "medium", "high")
    assert isinstance(p.citations, list)


def test_load_auto_nmc_preset_peak_and_confidence():
    p = load_ev_preset("auto", "NMC")
    assert p.peak_hrr_mw_range == (2.0, 7.0)
    assert p.confidence == "medium"
    assert isinstance(p.citations, list)


def test_list_ev_presets_contains_both():
    assert {"e-bike-lfp", "auto-nmc"} <= set(list_ev_presets())


def test_unknown_preset_raises():
    with pytest.raises(ValueError, match="Unknown EV preset"):
        load_ev_preset("e-bike", "NMC")


def test_preset_id_property():
    p = load_ev_preset("e-bike", "LFP")
    assert p.preset_id == "e-bike-lfp"
    p2 = load_ev_preset("Auto", "NMC")
    assert p2.preset_id == "auto-nmc"


def test_library_digest_returns_sha256_hex():
    d = library_digest()
    assert isinstance(d, str)
    assert len(d) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", d) is not None
    assert library_digest() == d


def test_library_digest_empty_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("IFCFDS_EV_LIBRARY_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="EV library is empty"):
        library_digest()


def test_check_assumption_policy_version_mismatch():
    data = _sample_valid_data()
    data["version"] = "9.9.9"
    with pytest.raises(ValueError, match="Unsupported EV library version"):
        EVPreset.model_validate(data)


def test_check_assumption_policy_unknown_chemistry_non_low_confidence():
    data = _sample_valid_data()
    data["chemistry"] = "unknown"
    data["confidence"] = "medium"
    with pytest.raises(ValueError, match="unknown-origin preset must use confidence 'low'"):
        EVPreset.model_validate(data)


def test_check_assumption_policy_empty_citations_medium_confidence():
    data = _sample_valid_data()
    data["citations"] = []
    data["confidence"] = "medium"
    with pytest.raises(ValueError, match="Preset without citations must use confidence 'low'"):
        EVPreset.model_validate(data)


def test_check_assumption_policy_empty_citations_high_confidence():
    data = _sample_valid_data()
    data["citations"] = []
    data["confidence"] = "high"
    with pytest.raises(ValueError, match="Preset without citations must use confidence 'low'"):
        EVPreset.model_validate(data)


def test_check_assumption_policy_empty_citations_low_confidence_allowed():
    data = _sample_valid_data()
    data["citations"] = []
    data["confidence"] = "low"
    preset = EVPreset.model_validate(data)
    assert preset.confidence == "low"
    assert preset.citations == []


def test_load_ev_preset_corrupt_json_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("IFCFDS_EV_LIBRARY_DIR", str(tmp_path))
    corrupt_file = tmp_path / "auto-broken.json"
    corrupt_file.write_text("{ not valid json: ", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid EV preset JSON"):
        load_ev_preset("auto", "broken")


def test_load_ev_preset_path_traversal_guard():
    with pytest.raises(ValueError, match="Path traversal detected"):
        load_ev_preset("../outside", "nmc")
    with pytest.raises(ValueError, match="Path traversal detected"):
        load_ev_preset("auto", "../../outside")


@pytest.mark.parametrize(
    "field,bad_range",
    [
        ("pack_kwh_range", (-1.0, 50.0)),
        ("pack_kwh_range", (50.0, 10.0)),
        ("peak_hrr_mw_range", (-0.5, 2.0)),
        ("peak_hrr_mw_range", (5.0, 1.0)),
        ("t_alpha_s", (-10.0, 100.0)),
        ("t_alpha_s", (300.0, 100.0)),
    ],
)
def test_preset_range_validation(field, bad_range):
    data = _sample_valid_data()
    data[field] = bad_range
    with pytest.raises(ValueError):
        EVPreset.model_validate(data)


@pytest.mark.parametrize(
    "yield_key,bad_range",
    [
        ("co", (-0.01, 0.2)),
        ("co", (0.3, 0.1)),
        ("soot", (-0.05, 0.2)),
        ("soot", (0.5, 0.1)),
        ("hf", (-0.001, 0.05)),
        ("hf", (0.1, 0.01)),
    ],
)
def test_species_yields_range_validation(yield_key, bad_range):
    data = _sample_valid_data()
    data["yields"][yield_key] = bad_range
    with pytest.raises(ValueError):
        EVPreset.model_validate(data)
