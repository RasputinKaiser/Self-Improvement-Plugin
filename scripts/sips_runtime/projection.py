"""Immutable graph receipt projection and bounded Markdown rendering."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .canonical import canonical_hash, canonical_json


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ValueError("receipt JSON object keys must be strings")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        raise ValueError("receipt values must use JSON arrays, not sets")
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ValueError("receipt JSON object keys must be strings")
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _canonical(value: Any) -> str:
    return canonical_json(value)


def _stable_sequence(values: Sequence[Any]) -> list[Any]:
    return sorted(list(values), key=_canonical)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _answer_units(answer: Any) -> list[str]:
    if answer is None:
        return []
    if isinstance(answer, (list, tuple)):
        values = [str(item).strip() for item in answer]
    else:
        values = [part.strip() for part in str(answer).splitlines()]
    return [value for value in values if value]


def _markdown(data: Mapping[str, Any], answer_units: Sequence[str], omissions: Sequence[Any], max_chars: int) -> str:
    lines = [f"# Graph receipt: {data.get('run_id', 'unknown')}", "", f"Status: {data.get('status', 'unknown')}", ""]
    if answer_units:
        lines += ["## Answer", ""] + [f"- {unit}" for unit in answer_units]
    claims = data.get("claims", ())
    if claims:
        lines += ["", "## Claims", ""]
        for claim in claims:
            if isinstance(claim, Mapping):
                lines.append(f"- `{claim.get('id', '')}`: {claim.get('text', claim.get('claim', _canonical(claim)))}")
            else:
                lines.append(f"- {claim}")
    artifacts = data.get("artifacts", ())
    if artifacts:
        lines += ["", "## Artifacts", ""]
        for artifact in artifacts:
            if isinstance(artifact, Mapping):
                lines.append(f"- `{artifact.get('id', '')}` ({artifact.get('digest', '')})")
            else:
                lines.append(f"- {artifact}")
    if omissions:
        lines += ["", "## Omissions", ""] + [f"- {item}" for item in omissions]
    rendered = "\n".join(lines).rstrip() + "\n"
    if len(rendered) <= max_chars:
        return rendered
    # Keep the receipt valid Markdown and leave a visible indication that the
    # structured receipt still contains the complete payload.
    suffix = "\n\n...[markdown capped; see structured content]"
    if max_chars <= len(suffix):
        return suffix[:max_chars]
    return rendered[: max(0, max_chars - len(suffix))].rstrip() + suffix


@dataclass(frozen=True)
class GraphReceipt:
    """Frozen top-level receipt; nested structures are immutable projections."""

    run_id: str
    status: str
    structured: Mapping[str, Any] = field(default_factory=dict)
    markdown: str = ""
    digest: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "structured", _freeze(dict(self.structured)))
        computed = canonical_hash(_thaw(self.structured))
        if self.digest and self.digest != computed:
            raise ValueError("receipt digest does not match structured content")
        object.__setattr__(self, "digest", computed)

    def to_dict(self) -> dict[str, Any]:
        value = {
            "run_id": self.run_id,
            "status": self.status,
            "structured": _thaw(self.structured),
            "markdown": self.markdown,
            "digest": self.digest,
        }
        for key in ("revision", "event_digest", "generated_at"):
            if key in self.structured:
                value[key] = _thaw(self.structured[key])
        return value

    @property
    def content(self) -> Mapping[str, Any]:
        return self.structured

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)


def make_graph_receipt(
    content: Mapping[str, Any] | None = None,
    *,
    run_id: str = "",
    status: str = "",
    answer: Any = None,
    claims: Sequence[Any] | None = None,
    artifacts: Sequence[Any] | None = None,
    gates: Any = None,
    omissions: Sequence[Any] | None = None,
    max_chars: int = 8_000,
    max_answer_units: int = 12,
    max_omissions: int = 5,
) -> GraphReceipt:
    """Build a full structured receipt and a bounded human projection."""
    supplied = dict(content or {})
    max_chars = min(8_000, max(1, int(max_chars)))
    max_answer_units = min(12, max(0, int(max_answer_units)))
    max_omissions = min(5, max(0, int(max_omissions)))
    if not run_id:
        run_id = str(supplied.get("run_id", supplied.get("id", "")))
    status = str(status or supplied.get("status", "complete"))
    answer_values = _answer_units(answer if answer is not None else supplied.get("answer", supplied.get("answer_units", ())))
    markdown_answer_values = answer_values[: max(0, int(max_answer_units))]
    omission_values = _stable_sequence(
        list(omissions if omissions is not None else supplied.get("omissions", ()))
    )
    bounded_omissions = omission_values[: max(0, int(max_omissions))]
    structured = {
        **supplied,
        "schema": "sips.runtime.graph-receipt.v1",
        "schema_version": 1,
        "run_id": run_id,
        "status": status,
        "answer_units": answer_values,
        "answer_unit_count": len(answer_values),
        "markdown_answer_units": markdown_answer_values,
        "claims": _stable_sequence(
            list(claims if claims is not None else supplied.get("claims", ()))
        ),
        "artifacts": _stable_sequence(
            list(artifacts if artifacts is not None else supplied.get("artifacts", ()))
        ),
        "gates": gates if gates is not None else supplied.get("gates", {}),
        "omissions": omission_values,
        "omission_count": len(omission_values),
        "projection_limits": {"max_chars": int(max_chars), "max_answer_units": int(max_answer_units), "max_omissions": int(max_omissions)},
    }
    if supplied.get("generated_at"):
        structured["generated_at"] = supplied["generated_at"]
    markdown = _markdown(structured, markdown_answer_values, bounded_omissions, max_chars)
    return GraphReceipt(run_id=run_id, status=status, structured=structured, markdown=markdown)


def project_receipt(content: Mapping[str, Any] | GraphReceipt, **kwargs: Any) -> GraphReceipt:
    if isinstance(content, GraphReceipt):
        return content
    return make_graph_receipt(content, **kwargs)


receipt_projection = project_receipt
build_receipt = make_graph_receipt

__all__ = ["GraphReceipt", "make_graph_receipt", "build_receipt", "project_receipt", "receipt_projection"]
