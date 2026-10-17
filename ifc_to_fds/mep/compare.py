"""Entity-addressed differences in saved versus source-rebuilt MEP relations."""

from ifc_to_fds.core.compare import normalize


def graph_differences(expected, actual):
    differences = []
    for group, identity in (("systems", "system_id"), ("connections", "connection_id")):
        left = {
            x.get(identity): x
            for x in expected.get(group, [])
            if x.get(identity) is not None
        }
        right = {
            x.get(identity): x
            for x in actual.get(group, [])
            if x.get(identity) is not None
        }
        for key in sorted(set(left) | set(right), key=str):
            before, after = left.get(key, {}), right.get(key, {})
            if normalize(before) == normalize(after):
                continue
            related = set()
            for value in (before, after):
                related.update(value.get("element_keys", []))
                related.update(
                    value.get(field)
                    for field in ("source_element_id", "target_element_id")
                    if value.get(field)
                )
            differences.append(
                dict(
                    relation_key=key,
                    entities=sorted(related, key=str),
                    expected=before,
                    actual=after,
                )
            )
    if not differences and normalize(expected) != normalize(actual):
        differences.append(
            dict(
                relation_key="coverage/orphans",
                entities=expected.get("isolated_element_ids", []),
                expected=expected.get("coverage"),
                actual=actual.get("coverage"),
            )
        )
    return differences
