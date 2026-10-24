from ifc_to_fds.fire.ev_library import list_ev_presets, load_ev_preset


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
    import pytest

    with pytest.raises(ValueError):
        load_ev_preset("e-bike", "NMC")
