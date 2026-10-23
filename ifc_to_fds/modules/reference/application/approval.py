"""Validate local review declarations; no reviewer authentication or approval writes."""


def has_review_evidence(document):
    if not isinstance(document, dict):
        return False
    if not all(isinstance(document.get(k), str) and document[k].strip()
               for k in ("reviewer", "rationale")):
        return False
    evidence = document.get("evidence")
    return (isinstance(evidence, list) and bool(evidence)
            and all(isinstance(item, str) and item.strip() for item in evidence))


def is_approved_reference(document):
    return has_review_evidence(document) and document.get("status") == "APPROVED"
