"""Prefer explicit IFC type/system semantics to names."""

HVAC_TYPES = {
    "IFCDUCTSEGMENT",
    "IFCDUCTFITTING",
    "IFCAIRTERMINAL",
    "IFCAIRTERMINALBOX",
    "IFCDUCTSILENCER",
    "IFCFAN",
    "IFCDAMPER",
}
MEP_TYPES = HVAC_TYPES | {
    "IFCFLOWMOVINGDEVICE",
    "IFCFLOWCONTROLLER",
    "IFCPIPESEGMENT",
    "IFCPIPEFITTING",
    "IFCVALVE",
    "IFCPUMP",
    "IFCFIRESUPPRESSIONTERMINAL",
    "IFCFLOWSEGMENT",
    "IFCFLOWFITTING",
    "IFCFLOWTERMINAL",
    "IFCUNITARYEQUIPMENT",
    "IFCSENSOR",
    "IFCALARM",
    "IFCFLOWINSTRUMENT",
    "IFCDISTRIBUTIONCONTROLELEMENT",
}


def classify_mep_element(
    ifc_type,
    name,
    system_name="",
    predefined_type="",
    type_class="",
    property_sets=None,
    system_categories=(),
):
    t = (type_class or ifc_type or "").upper()
    if t.endswith("TYPE"):
        t = t[:-4]
    p = str(predefined_type or "").upper()
    if t == "IFCFIRESUPPRESSIONTERMINAL":
        return "FIRE_SUPPRESSION", True
    enum_categories = {
        "FIRE_SUPPRESSION": {
            "FIREPROTECTION",
            "FIRE PROTECTION",
            "FIRE_SUPPRESSION",
            "SPRINKLER",
            "FIREHYDRANT",
        },
        "SMOKE_EXTRACT": {
            "SMOKEEXHAUST",
            "SMOKE EXTRACT",
            "SMOKECONTROL",
            "PRESSURISATION",
            "PRESSURIZATION",
        },
        "VENTILATION": {"VENTILATION", "AIRCONDITIONING", "EXHAUST"},
        "PLUMBING": {
            "DOMESTICCOLDWATER",
            "DOMESTICHOTWATER",
            "DRAINAGE",
            "SEWAGE",
            "WATERSUPPLY",
        },
    }

    def result(category):
        # A duct/fan class cannot establish a water/fire-suppression function.
        if t in HVAC_TYPES and category in ("FIRE_SUPPRESSION", "PLUMBING"):
            return "UNRESOLVED", False
        return category, category in ("FIRE_SUPPRESSION", "SMOKE_EXTRACT")

    for category, values in enum_categories.items():
        if p in values:
            return result(category)
    def resolve_category(cat):
        if cat in enum_categories:
            return cat
        for enum_cat, values in enum_categories.items():
            if cat in values:
                return enum_cat
        return cat

    categories = {
        resolve_category(x)
        for x in system_categories
        if x not in ("OTHER", "UNRESOLVED")
    }
    if len(categories) > 1:
        return "UNRESOLVED", False
    if categories:
        return result(next(iter(categories)))
    explicit_property_values = []
    for properties in (property_sets or {}).values():
        if isinstance(properties, dict):
            explicit_property_values.extend(
                str(value).upper()
                for key, value in properties.items()
                if key.replace(" ", "").lower()
                in ("systemtype", "systemclassification", "servicetype")
            )
    categories = {
        category
        for category, values in enum_categories.items()
        if any(v in values for v in explicit_property_values)
    }
    if len(categories) > 1:
        return "UNRESOLVED", False
    if categories:
        return result(next(iter(categories)))
    if t in HVAC_TYPES:
        return "VENTILATION", False
    return "UNRESOLVED", False
