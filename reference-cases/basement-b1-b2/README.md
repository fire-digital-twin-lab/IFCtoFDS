# Basement B1/B2 — DRAFT, not accepted ground truth

This tracked bundle is an empty intake template bound to the supplied IFC hash.
`expected-inventory.json` is intentionally empty: it does not assert that the
building contains zero entities. No manual FDS baseline has been supplied.
The approval state is DRAFT. Do not change it merely to make tests pass.

The private IFC and detailed inventory remain outside Git. An inventory-only
candidate has 5,641 IfcProduct entities, 180 proxies, 2,392 distribution ports and
1,068 explicit connection relations. The source uses FOOT (0.3048 metres).
These are full-file counts, not verified basement or FP counts.

Regenerate a private intake with:

```powershell
python scripts/prepare-basement-reference.py <external-source.ifc> --output .local-reference-cases/basement-new-intake
```

Map the SHA256 in sources.json to a local path in a `*.source-map.local.json` file
and run `python -m ifc_to_fds reference-resolve reference-cases/basement-b1-b2 --source-map <map>`.
The resolver rejects missing or changed files; it never guesses a filename match.

Before a geometry candidate can become a reviewed reference:

1. Review source-qualified building/storey groups. The IFC contains repeated B1/B2 names.
2. Establish the simulation domain from actual structural/air-space evidence. Storey elevations alone are insufficient.
3. Review structural boundaries, openings, ramps, stairs, exclusions and MEP roles.
4. Obtain the historical accepted FDS and decisions, or author and review a new baseline.
5. Generate geometry and independent audit artifacts; review all pending decisions.
6. Record reviewer, rationale and evidence in approval.json, binding approval to the full bundle digest printed by reference-check.
7. Record differences from any historical baseline explicitly. Never silently overwrite an approved reference.

No automatic approval command is provided. Content checksums bind a local review
record to a revision; they are not cryptographic proof of reviewer identity.

Current blockers: domain not approved; scope groups not approved; geometry not
processed; historical baseline unavailable; boundary solver evidence unavailable.
This case must report INCONCLUSIVE under the research-basement profile.
