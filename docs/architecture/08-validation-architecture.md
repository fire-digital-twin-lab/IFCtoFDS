# 08 — Validation Architecture: Independent Gate Checkers

## 1. Modular Validation Pipeline
Rather than executing all validation in a monolithic multi-hundred-line procedure, the validation suite decomposes into single-responsibility checkers:

```text
ValidationContext
       │
       ├──> SourceCoverageChecker        (verifies IFC sources and entity accounting)
       ├──> ScopeChecker                 (verifies spatial inclusion / exclusion boundaries)
       ├──> GeometryChecker              (audits topology, degenerate faces, bounds)
       ├──> OpeningChecker               (measures void subtraction and residual passages)
       ├──> MEPChecker                   (audits system connectivity and port alignment)
       ├──> ProvenanceChecker            (verifies bidirectional IFC-FDS entity keys)
       ├──> BoundaryChecker              (audits cross-boundary elements and solver proofs)
       ├──> FdsSyntaxChecker             (validates FDS namelist grammar and face indices)
       ├──> SolverChecker                (verifies FDS execution when solver is present)
       └──> GoldenParityChecker          (evaluates parity against approved reference cases)
       │
       ▼
GateResult[]
       │
       ▼
AcceptanceEvaluator ──> Immutable AcceptanceReport
```

## 2. Checker Contract — `[IMPLEMENTED]`
Every checker implements the same protocol defined in `ifc_to_fds/domain/validation/checkers/base.py`:
```python
@runtime_checkable
class GateChecker(Protocol):
    name: str

    def check(self, context: ValidationContext) -> CheckerOutcome:
        ...
```
`ValidationContext` carries the model, fds_text, manifest, config, and a lazy `parsed` FDS parser property so shared parse artifacts are not repeatedly recalculated.

## 3. Evaluator Fail-Safe & Immutability — `[IMPLEMENTED]`
- **Fail-Safe Principle**: `AcceptanceEvaluator` initializes all unexecuted gates to `GateStatus.NOT_RUN`. A gate only transitions to `PASS` when its corresponding checker successfully validates all assertions.
- **Immutability**: Checkers **never mutate** the `AcceptanceReport` directly. Outcomes return isolated `findings`, `metrics`, and `evidence`. `AcceptanceEvaluator` constructs the finalized report.
