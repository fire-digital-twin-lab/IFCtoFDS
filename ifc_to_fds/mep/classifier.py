"""Prefer explicit IFC type/system semantics to names."""

HVAC_TYPES = {
    "IFCDUCTSEGMENT",
    "IFCDUCTFITTING",
    "IFCAIRTERMINAL",
    "IFCAIRTERMINALBOX",
    "IFCDUCTSILENCER",
    "IFCFAN",
    "IFCDAMPER",
    "IFCFLOWMOVINGDEVICE",
    "IFCFLOWCONTROLLER",
}
MEP_TYPES = HVAC_TYPES | {
    "IFCPIPESEGMENT",
    "IFCPIPEFITTING",
    "IFCVALVE",
    "IFCPUMP",
    "IFCFIRESUPPRESSIONTERMINAL",
    "IFCFLOWSEGMENT",
    "IFCFLOWFITTING",
    "IFCFLOWTERMINAL",
    "IFCUNITARYEQUIPMENT",
}


def classify_mep_element(
    ifc_type,
    name,
    system_name="",
    predefined_type="",
    type_class="",
    property_sets=None,
):
    t = (type_class or ifc_type or "").upper()
    if t.endswith("TYPE"):
        t = t[:-4]
    sys = str(system_name or "").upper()
    p = str(predefined_type or "").upper()
    n = str(name or "").upper()
    explicit_property_values = []
    for properties in (property_sets or {}).values():
        if isinstance(properties, dict):
            explicit_property_values.extend(
                str(value).upper()
                for key, value in properties.items()
                if key.replace(" ", "").lower()
                in ("systemtype", "systemclassification", "servicetype")
            )
    if any(
        value in ("FIREPROTECTION", "FIRE PROTECTION", "FIRE_SUPPRESSION", "SPRINKLER")
        for value in explicit_property_values
    ):
        return "FIRE_SUPPRESSION", True
    if any(
        value in ("SMOKEEXHAUST", "SMOKE EXTRACT", "SMOKECONTROL")
        for value in explicit_property_values
    ):
        return "SMOKE_EXTRACT", True
    if any(
        value in ("VENTILATION", "AIRCONDITIONING", "EXHAUST")
        for value in explicit_property_values
    ):
        return "VENTILATION", False
    if p in ("SMOKEEXHAUST", "SMOKECONTROL", "PRESSURISATION") or any(
        w in sys for w in ("SMOKE", "HUT_KHOI", "TANG_AP", "PRESSURIZATION")
    ):
        return "SMOKE_EXTRACT", True
    if (
        t == "IFCFIRESUPPRESSIONTERMINAL"
        or p in ("FIREPROTECTION", "SPRINKLER", "FIREHYDRANT")
        or any(w in sys for w in ("PCCC", "FIRE", "SPRINKLER", "CHUA_CHAY"))
    ):
        return "FIRE_SUPPRESSION", True
    if p in ("VENTILATION", "AIRCONDITIONING", "EXHAUST") or t in HVAC_TYPES:
        return "VENTILATION", False
    if t in ("IFCPIPESEGMENT", "IFCPIPEFITTING"):
        return "PLUMBING", False
    if "SMOKE" in n:
        return "SMOKE_EXTRACT", True
    if "SPRINKLER" in n:
        return "FIRE_SUPPRESSION", True
    return "OTHER", False
