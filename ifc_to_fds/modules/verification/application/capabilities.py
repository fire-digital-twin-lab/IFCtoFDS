"""Declared evidence scope; capability availability never grants a passing gate."""


def verification_capabilities():
    return {
        "schema_version": "1.0",
        "solver_versions": ["6.11.1"],
        "mapping": {
            "evidence": "REREAD_IFC_AND_SAVED_FDS_ARTIFACTS",
            "operational_mep": "NOT_VERIFIED",
        },
        "effective_obst": {
            "supported": True,
            "conditions": [
                "Uniform Cartesian grids with unambiguous nearest-grid rounding",
                "Single mesh or adjacent equal-cell meshes tiling one axis",
                "No unsupported dynamic obstruction or opening operators",
                "Boundary clearances and air component correspondence preserved",
                "Rectilinear air partition within adapter resource budget",
            ],
        },
        "effective_openings": {
            "supported": True,
            "conditions": [
                "One uniform Cartesian mesh",
                "Static grid-aligned OBST and HOLE",
                "Planar exterior OPEN vents with clear adjacent cells",
                "Cell occupancy within adapter resource budget",
            ],
        },
        "geom_surfaces": {
            "supported": True,
            "evidence": "SOLVER_STATIC_BINGEOM_WITH_TRIANGLE_SURFACE_BINDING",
            "cut_cell_occupancy": "NOT_VERIFIED",
        },
        "geom_cut_cells": {
            "supported": False,
            "reason": "Complete solver gas volumes and face connectivity evidence unavailable",
        },
        "editor_import": {
            "evidence": "HUMAN_REVIEW_WITH_HASH_BOUND_ARTIFACTS",
            "gui_automated": False,
            "required_artifacts": ["original_fds", "reexport_fds", "project_psm", "diagnostics"],
        },
        "simulation_physics": "NOT_VERIFIED",
    }
