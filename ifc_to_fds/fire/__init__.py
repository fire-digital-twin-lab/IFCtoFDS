"""EV fire scenario physics: preset library and scenario emission."""

from ifc_to_fds.fire.ev_library import (
    EVPreset,
    EV_LIBRARY_VERSION,
    Citation,
    SpeciesYields,
    library_digest,
    library_dir,
    list_ev_presets,
    load_ev_preset,
)

__all__ = [
    "EVPreset",
    "EV_LIBRARY_VERSION",
    "Citation",
    "SpeciesYields",
    "library_digest",
    "library_dir",
    "list_ev_presets",
    "load_ev_preset",
]
