from __future__ import annotations
def matching_record_ids(records, keywords):
    matches = []
    for record in records:
        if keywords & record_terms(record):
            matches.append(str(record.get("id", "")))
    return sorted(item for item in matches if item)


def record_terms(record):
    values = [
        str(record.get("title", "")),
        str(record.get("body", "")),
        " ".join(str(tag) for tag in record.get("tags", [])),
    ]
    return set(" ".join(values).lower().replace(",", " ").split())
