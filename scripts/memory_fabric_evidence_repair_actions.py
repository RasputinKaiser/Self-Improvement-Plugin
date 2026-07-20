from __future__ import annotations
from pathlib import Path
from typing import Any


def repair_action(
    warning: dict[str, Any],
    *,
    receipt: Path | None,
    allowed_root: Path | None,
    create_indexes: bool,
) -> dict[str, Any]:
    base = base_action(warning)
    if warning["code"] != "evidence_missing":
        return manual_review(base)
    evidence = Path(str(warning["evidence_path"])).expanduser()
    blocked = blocked_action(base, receipt, evidence, allowed_root)
    if blocked:
        return blocked
    if not create_indexes:
        return would_create(base, receipt)
    return create_index(base, warning, evidence, receipt)


def base_action(warning: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": warning["id"],
        "title": warning["title"],
        "code": warning["code"],
        "evidence_path": warning["evidence_path"],
    }


def manual_review(base: dict[str, Any]) -> dict[str, Any]:
    return {
        **base,
        "action": "manual_review",
        "reason": "Only missing local evidence paths can be repaired with receipt indexes.",
    }


def blocked_action(
    base: dict[str, Any],
    receipt: Path | None,
    evidence: Path,
    allowed_root: Path | None,
) -> dict[str, Any]:
    if not receipt:
        return {**base, "action": "blocked_missing_receipt", "reason": "Provide --receipt-path."}
    if not receipt.exists():
        return {**base, "action": "blocked_receipt_absent", "receipt_path": str(receipt)}
    if allowed_root and not path_is_within(evidence, allowed_root):
        return {
            **base,
            "action": "blocked_outside_allowed_root",
            "allowed_root": str(allowed_root),
        }
    return {}


def would_create(base: dict[str, Any], receipt: Path | None) -> dict[str, Any]:
    return {
        **base,
        "action": "would_create_receipt_index",
        "receipt_path": str(receipt),
    }


def create_index(
    base: dict[str, Any],
    warning: dict[str, Any],
    evidence: Path,
    receipt: Path | None,
) -> dict[str, Any]:
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(receipt_index_text(warning, receipt), encoding="utf-8")
    return {
        **base,
        "action": "created_receipt_index",
        "receipt_path": str(receipt),
    }


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def receipt_index_text(warning: dict[str, Any], receipt: Path | None) -> str:
    return "\n".join(
        [
            "# Evidence Repair Receipt Index",
            "",
            "This file was created by `memory_fabric.py evidence-repair`.",
            "",
            "It is a pointer to a newer durable receipt, not proof that this path",
            "contained the original evidence when the memory record was written.",
            "",
            f"- memory_id: `{warning['id']}`",
            f"- memory_title: `{warning['title']}`",
            f"- replacement_receipt: `{receipt}`",
            "",
        ]
    )
