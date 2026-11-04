# R10-06 — CI Quality Gates and Audit Regression Evidence

**Basis:** `Review-Toan-Dien-IFCtoFDS-.docx`, `IFCtoFDS_Audit_2026-11-04.md` findings A-17/M-17, A-18/M-26, A-10/H-9, A-15/M-4, A-16/M-5.

**Base:** stacked on R10-05b PR #27. This is a quality-infrastructure change,
not a claim to have resolved scientific validation or performance regressions.

## 1. Why / Vì sao

The previous workflow validated Python, JavaScript, browser and an actual
pinned FDS solver, but did **not** run lint/type analyzers or collect a
standard coverage report. Earlier review also found increasing function-local
imports, broad/silent exception handling and degenerate-geometry warnings.
A full strict-lint or type gate against every legacy file would currently
mix substantial unrelated cleanup with safety-critical refactor changes.

**Decision:** introduce independently reviewable CI quality jobs and
budget-based debt protection. Never silently count a missing audit or an
unreproduced benchmark as PASS.

## 2. Implemented CI / Các bước đã thêm

| Gate | Scope | Blocking? |
|---|---|---|
| Python bytecode compilation | Entire `ifc_to_fds` + quality scripts | Yes |
| Ruff critical rules E4,E7,E9,F63,F7,F82 | Quality scanner and scenario verdict | Yes |
| Pyright `basic` | Quality scanner + scenario verdict | Yes |
| ESLint `no-unreachable`, `no-dupe-args`, `no-constant-condition` | EV scenario panel | Yes |
| AST source-debt inventory | Entire Python package | Report and artifact |
| Per-changed-file debt vs PR merge base | Function-scope imports, broad/bare/silent except | Yes |
| Python test suite and coverage | All non-browser/non-solver tests | Tests block; coverage is reported, no arbitrary target |
| Existing verified workflow | Python matrix, browser, JS, real FDS | Unchanged |

The AST rule is a non-regression guarantee: a file that already contains
a local import or a broad exception cannot acquire additional ones without
CI failure. It does **not** certify current source as free of debt.
The baseline is derived from Git, not chosen to make findings disappear.

`source-debt.json` and `coverage.xml` are published as review artifacts.
Artifact-upload connectivity failures are not treated as a failure of the
underlying tests; inspect the missing artifact separately before acceptance.

## 3. What is NOT claimed / Chưa được chứng minh

- Ruff/Pyright/ESLint are **not** yet enabled in strict mode across the
  entire historical codebase.
- No branch-independent benchmark speedup or memory improvement is claimed.
- Numerical `RuntimeWarning` and degeneracy findings from A-18 have not
  all been converted into explicit geometry evidence.
- The real-world 5,641-entity IFC audit remains `REJECTED` until independently
  reviewed and rerun on the original source.
- A green quality workflow is not `SIMULATION_VERIFIED`.

## 4. Next closure gates / Điều kiện hoàn thiện

1. Review the generated debt inventory and coverage report; record a
   reproducible versioned baseline and ratchet it downward.
2. Extend Ruff/typing in reviewed modules, fix errors rather than disabling
   categories globally.
3. Profile the same IFC on comparable hardware across revisions using
   `scripts/benchmark-revisions.py`, retaining warmups, failures and
   timeouts. Do not use a one-off GitHub runner time as a regression threshold.
4. Convert selected `RuntimeWarning` cases into domain evidence and negative
   regression tests; use narrowly scoped warning-as-error checks only after
   fixtures are reproduced.
5. Run the full browser and pinned FDS solver CI from `verified.yml`.

## 5. Usage / Sử dụng

```bash
python scripts/quality/source_quality_budget.py --output quality-evidence/source-debt.json
python scripts/quality/source_quality_budget.py --git-base "$(git merge-base HEAD origin/main)"
python -m pytest -q tests/test_source_quality_budget.py
```

**Safety:** This phase introduces no changes to IFC geometry, mapping plans,
FDS serialization, independent source auditing, physical assumptions or
acceptance verdicts.
