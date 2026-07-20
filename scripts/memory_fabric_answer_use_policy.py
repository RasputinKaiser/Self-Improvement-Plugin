from __future__ import annotations
from collections import Counter
from typing import Any

from memory_fabric_answer_use_policy_reasons import blocked_record_ids, global_verify_reasons
from memory_fabric_answer_use_policy_records import record_policy


CLAIM_BOUNDARY = "Answer-use policy ranks selected memory for citation; it does not prove external truth."


def answer_use_policy(
    selected: list[dict[str, Any]],
    brief: dict[str, Any],
    graph: dict[str, Any],
    hypotheses: dict[str, Any],
    claims: dict[str, Any],
    checks: list[str],
) -> dict[str, Any]:
    blocked = blocked_record_ids(graph)
    global_reasons = global_verify_reasons(brief, graph, hypotheses, claims, checks)
    records = [record_policy(record, blocked, global_reasons) for record in selected]
    counts = Counter(item["answer_use"] for item in records)
    ok = answer_use_ready(records, counts)
    return {
        "ok": ok,
        "status": "answer_use_ready" if ok else "answer_use_needs_verification",
        "claim_boundary": CLAIM_BOUNDARY,
        "record_count": len(records),
        "answer_use_counts": dict(sorted(counts.items())),
        "required_citations": record_values(records, "cite", "evidence_path"),
        "verify_record_ids": record_values(records, "verify_before_citing", "id"),
        "blocked_record_ids": record_values(records, "do_not_cite", "id"),
        "global_verify_reasons": global_reasons,
        "records": records,
    }


def answer_use_ready(records: list[dict[str, Any]], counts: Counter) -> bool:
    return bool(records) and not blocked_answer_use(counts)


def blocked_answer_use(counts: Counter) -> bool:
    return bool(counts.get("do_not_cite") or counts.get("verify_before_citing"))


def record_values(records: list[dict[str, Any]], answer_use: str, field: str) -> list[str]:
    return [item[field] for item in records if item["answer_use"] == answer_use]
