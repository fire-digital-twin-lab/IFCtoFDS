# FDS 6.11.1 scientific parser contract — P2

## Scope

The Python Verified Core parser deliberately supports a reviewed subset of FDS, not the entire FDS grammar. P2 adds the namelists needed by later thermal-material, detection/suppression, instrumentation and scientific-output work packages: MATL, PART, PROP, SLCF, BNDF and ISOF.

It also extends the already-supported SURF, DEVC, REAC and HVAC field subsets needed by those work packages. Unknown fields remain fail-closed in ParsedFDS.unsupported; they are not silently treated as valid physics.

## Authoritative references

The contract was checked against the pinned/current FDS release 6.11.1 and official firemodels/NIST source/verification inputs:

1. NIST FDS-SMV manuals page — current release FDS 6.11.1 / SMV 6.11.2:
   https://pages.nist.gov/fds-smv/manuals.html
2. FDS verification Controls/device_test.fds — PART, detector/sprinkler PROP, DEVC→PROP and SLCF:
   https://github.com/firemodels/fds/blob/master/Verification/Controls/device_test.fds
3. FDS verification Sprinklers_and_Sprays/water_fuel_sprays.fds — PART, PROP, spray fields and thermal MATL:
   https://github.com/firemodels/fds/blob/master/Verification/Sprinklers_and_Sprays/water_fuel_sprays.fds
4. FDS verification Heat_Transfer/ht3d_energy_conservation.fds — thermal MATL and BNDF:
   https://github.com/firemodels/fds/blob/master/Verification/Heat_Transfer/ht3d_energy_conservation.fds
5. FDS validation UMD_SBI/FDS_Input_Files/UMD_SBI_1_cm.fds — REAC.RADIATIVE_FRACTION, SLCF, BNDF and ISOF:
   https://github.com/firemodels/fds/blob/master/Validation/UMD_SBI/FDS_Input_Files/UMD_SBI_1_cm.fds
6. FDS source Source/hvac.f90 — authoritative NAMELIST /HVAC/ field list:
   https://github.com/firemodels/fds/blob/master/Source/hvac.f90
7. Temperature-dependent material examples with CONDUCTIVITY_RAMP and SPECIFIC_HEAT_RAMP:
   https://github.com/firemodels/fds/blob/master/Validation/NIST_NRC_Corner_Effects/FDS_Input_Files/cabinet_01.fds

## Contract policy

The parser validates syntax/reference integrity only. It does not infer that a syntactically accepted record is physically appropriate.

Required fields in this supported subset: MATL.ID, PART.ID, PROP.ID, SLCF.QUANTITY, BNDF.QUANTITY, ISOF.QUANTITY and ISOF.VALUE.

References are checked after the whole file is parsed, so namelist ordering does not affect meaning:

- DEVC.PROP_ID → PROP.ID
- PROP.PART_ID → PART.ID
- SURF.MATL_ID → MATL.ID
- SURF.PART_ID → PART.ID
- SLCF.PART_ID → PART.ID
- BNDF.PART_ID → PART.ID
- BNDF.MATL_ID → MATL.ID

Indexed FDS field forms such as MATL_ID(1,:) and QUANTITIES(1:3) are checked using their base field name while preserving the original serialized key.

## Evidence level

Target for this work package: E2 — software verification.

A pinned FDS 6.11.1 solver fixture is added as a syntax oracle. Solver acceptance of the fixture does not constitute model validation, numerical verification or application validation.
