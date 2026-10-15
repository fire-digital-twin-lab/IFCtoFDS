"""MEP and Fire Safety System Semantic Classifier.

Categorizes building services into Ventilation, Smoke Extraction,
Fire Protection, and general distribution systems.
"""

from typing import Tuple


HVAC_TYPES = {
    "IFCDUCTSEGMENT",
    "IFCDUCTFITTING",
    "IFCAIRTERMINAL",
    "IFCAIRTERMINALBOX",
    "IFCFLOWCONTROLLER",
    "IFCFLOWMOVINGDEVICE",
    "IFCDUCTSILENCER",
}

FP_TYPES = {
    "IFCFIRESUPPRESSIONTERMINAL",
    "IFCPIPESEGMENT",
    "IFCPIPEFITTING",
    "IFCVALVE",
}


def classify_mep_element(ifc_type: str, name: str, system_name: str = "") -> Tuple[str, bool]:
    """Classifies an element into system category and fire-safety criticality.

    Returns:
        (category, is_fire_safety_critical)
        category in {"VENTILATION", "SMOKE_EXTRACT", "FIRE_SUPPRESSION", "PLUMBING", "OTHER"}
    """
    type_upper = ifc_type.upper()
    name_upper = (name or "").upper()
    sys_upper = (system_name or "").upper()

    # 1. Fire Suppression & Sprinklers
    if (
        type_upper == "IFCFIRESUPPRESSIONTERMINAL"
        or "SPRINKLER" in name_upper
        or "PCCC" in sys_upper
        or "FIRE" in sys_upper
        or "CHUA_CHAY" in sys_upper
    ):
        return "FIRE_SUPPRESSION", True

    # 2. Smoke Extraction & Pressurization
    if (
        "SMOKE" in sys_upper
        or "SMOKE" in name_upper
        or "HUT_KHOI" in sys_upper
        or "TANG_AP" in sys_upper
        or "PRESSURIZATION" in sys_upper
    ):
        return "SMOKE_EXTRACT", True

    # 3. Ventilation & Ductwork
    if type_upper in HVAC_TYPES or "DUCT" in name_upper or "THONG_GIO" in sys_upper:
        return "VENTILATION", False

    # 4. Pipework / Plumbing
    if type_upper in {"IFCPIPESEGMENT", "IFCPIPEFITTING"}:
        return "PLUMBING", False

    return "OTHER", False
