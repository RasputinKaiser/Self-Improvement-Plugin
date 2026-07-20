"""Fail-closed, multi-dimensional runtime budget reservations.

Model tokens retain the historical 60k soft/120k hard profile.  The other
dimensions are independently capped so a cheap prompt cannot hide an
unbounded retrieval, tool, delegation, repair, wall-time, or memory plan.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


DEFAULT_SOFT_LIMIT = 60_000
DEFAULT_HARD_LIMIT = 120_000
TRANCHE_PERCENTAGES = (30, 35, 35)
RESOURCE_DIMENSIONS = (
    "model_tokens",
    "retrieval_tokens",
    "output_tokens",
    "delegations",
    "tool_calls",
    "repairs",
    "wall_time_seconds",
    "memory_bytes",
)
DEFAULT_RESOURCE_LIMITS = {
    "model_tokens": DEFAULT_HARD_LIMIT,
    "retrieval_tokens": 32_000,
    "output_tokens": 64_000,
    "delegations": 64,
    "tool_calls": 1_024,
    "repairs": 64,
    "wall_time_seconds": 28_800,
    "memory_bytes": 64 * 1024 * 1024,
}


class BudgetError(RuntimeError):
    pass


class UnknownCostError(BudgetError):
    """A reservation without a measured cost cannot be admitted."""


class HardBudgetExceeded(BudgetError):
    pass


class TrancheNotReleased(BudgetError):
    """The reservation fits the hard cap but exceeds the released tranche."""


@dataclass(frozen=True)
class BudgetReservation:
    reservation_id: str
    subject: str
    tokens: int
    soft_exceeded: bool = False
    committed: bool = False
    resources: Mapping[str, int] | None = None

    @property
    def amount(self) -> int:
        return self.tokens

    def to_dict(self) -> dict[str, Any]:
        resources = dict(self.resources or {"model_tokens": self.tokens})
        return {
            "reservation_id": self.reservation_id,
            "subject": self.subject,
            "tokens": self.tokens,
            "soft_exceeded": self.soft_exceeded,
            "committed": self.committed,
            "resources": {key: resources[key] for key in sorted(resources)},
        }


class BudgetLedger:
    def __init__(
        self,
        soft_limit: int = DEFAULT_SOFT_LIMIT,
        hard_limit: int = DEFAULT_HARD_LIMIT,
        resource_limits: Mapping[str, int] | None = None,
        released_tranches: int = 1,
    ) -> None:
        if (
            not isinstance(soft_limit, int)
            or isinstance(soft_limit, bool)
            or not isinstance(hard_limit, int)
            or isinstance(hard_limit, bool)
        ):
            raise ValueError("soft_limit and hard_limit must be integers")
        if soft_limit < 0 or hard_limit < soft_limit:
            raise ValueError("require 0 <= soft_limit <= hard_limit")
        self.soft_limit = int(soft_limit)
        self.hard_limit = int(hard_limit)
        limits = dict(DEFAULT_RESOURCE_LIMITS)
        supplied_limits = {str(key): value for key, value in dict(resource_limits or {}).items()}
        if any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in supplied_limits.values()
        ):
            raise ValueError("resource limits must be integers")
        if "model_tokens" in supplied_limits and supplied_limits["model_tokens"] != self.hard_limit:
            raise ValueError("model_tokens resource limit must equal hard_limit")
        limits.update(supplied_limits)
        limits["model_tokens"] = self.hard_limit
        unknown = sorted(set(limits) - set(RESOURCE_DIMENSIONS))
        if unknown:
            raise ValueError(f"unknown resource dimensions: {', '.join(unknown)}")
        if any(value < 0 for value in limits.values()):
            raise ValueError("resource limits must be non-negative")
        self.resource_limits = limits
        if not isinstance(released_tranches, int) or isinstance(released_tranches, bool):
            raise ValueError("released_tranches must be an integer")
        if released_tranches < 1 or released_tranches > len(TRANCHE_PERCENTAGES):
            raise ValueError(
                f"released_tranches must be between 1 and {len(TRANCHE_PERCENTAGES)}"
            )
        self._released_tranches = released_tranches
        self._reserved: dict[str, BudgetReservation] = {}
        self._spent = 0
        self._spent_resources = {key: 0 for key in RESOURCE_DIMENSIONS}
        self._counter = 0

    @property
    def reserved_tokens(self) -> int:
        return sum(item.tokens for item in self._reserved.values() if not item.committed)

    @property
    def committed_tokens(self) -> int:
        return self._spent

    @property
    def total_tokens(self) -> int:
        return self.reserved_tokens + self._spent

    @property
    def reserved_resources(self) -> dict[str, int]:
        totals = {key: 0 for key in RESOURCE_DIMENSIONS}
        for item in self._reserved.values():
            if item.committed:
                continue
            for key, value in dict(item.resources or {"model_tokens": item.tokens}).items():
                totals[key] += int(value)
        return totals

    @property
    def total_resources(self) -> dict[str, int]:
        reserved = self.reserved_resources
        return {key: self._spent_resources[key] + reserved[key] for key in RESOURCE_DIMENSIONS}

    @property
    def soft_exceeded(self) -> bool:
        return self.total_tokens > self.soft_limit

    @property
    def remaining_soft(self) -> int:
        return max(0, self.soft_limit - self.total_tokens)

    @property
    def remaining_hard(self) -> int:
        return max(0, self.hard_limit - self.total_tokens)

    @property
    def tranche_limits(self) -> tuple[int, ...]:
        limits: list[int] = []
        released = 0
        for percentage in TRANCHE_PERCENTAGES:
            released += round(self.hard_limit * percentage / 100)
            limits.append(min(self.hard_limit, released))
        return tuple(limits)

    @property
    def released_tranches(self) -> int:
        return self._released_tranches

    @property
    def released_token_limit(self) -> int:
        return self.tranche_limits[self._released_tranches - 1]

    def release_next_tranche(self) -> bool:
        """Release one additional token tranche; return false at the hard cap."""
        if self._released_tranches >= len(TRANCHE_PERCENTAGES):
            return False
        self._released_tranches += 1
        return True

    def can_reserve(self, tokens: int | None, resources: Mapping[str, int] | None = None) -> bool:
        if (
            tokens is None
            or not isinstance(tokens, int)
            or isinstance(tokens, bool)
            or tokens <= 0
        ):
            return False
        try:
            requested = self._normalize_resources(tokens, resources)
        except UnknownCostError:
            return False
        totals = self.total_resources
        return (
            totals["model_tokens"] + requested["model_tokens"] <= self.released_token_limit
            and all(
                totals[key] + requested[key] <= self.resource_limits[key]
                for key in RESOURCE_DIMENSIONS
            )
        )

    def _normalize_resources(
        self, tokens: int | None, resources: Mapping[str, int] | None
    ) -> dict[str, int]:
        if tokens is None:
            raise UnknownCostError("unknown model token cost")
        if not isinstance(tokens, int) or isinstance(tokens, bool) or tokens <= 0:
            raise UnknownCostError("invalid model token cost")
        supplied = {str(key): value for key, value in dict(resources or {}).items()}
        unknown = sorted(set(supplied) - set(RESOURCE_DIMENSIONS))
        if unknown:
            raise UnknownCostError(f"unknown resource dimensions: {', '.join(unknown)}")
        supplied.setdefault("model_tokens", tokens)
        # Direct legacy callers may reserve tokens alone. Runtime dispatchers
        # pass all dimensions explicitly and therefore remain fully bounded.
        if any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in supplied.values()
        ):
            raise UnknownCostError("resource estimates must be integers")
        normalized = {key: supplied.get(key, 0) for key in RESOURCE_DIMENSIONS}
        if normalized["model_tokens"] != tokens:
            raise UnknownCostError("model_tokens must match token reservation")
        if any(value < 0 for value in normalized.values()):
            raise UnknownCostError("resource estimates must be non-negative integers")
        return normalized

    def reserve(
        self,
        subject: str,
        tokens: int | None,
        resources: Mapping[str, int] | None = None,
    ) -> BudgetReservation:
        try:
            requested = self._normalize_resources(tokens, resources)
        except UnknownCostError as exc:
            raise UnknownCostError(f"{exc} for {subject}") from exc
        totals = self.total_resources
        exceeded = [
            key
            for key in RESOURCE_DIMENSIONS
            if totals[key] + requested[key] > self.resource_limits[key]
        ]
        if exceeded:
            detail = ", ".join(
                f"{key}={totals[key] + requested[key]}>{self.resource_limits[key]}" for key in exceeded
            )
            raise HardBudgetExceeded(f"hard resource budget exceeded: {detail}")
        requested_total = totals["model_tokens"] + requested["model_tokens"]
        if requested_total > self.released_token_limit:
            raise TrancheNotReleased(
                "model token reservation exceeds released tranche: "
                f"{requested_total}>{self.released_token_limit} "
                f"({self._released_tranches}/{len(TRANCHE_PERCENTAGES)} released)"
            )
        self._counter += 1
        reservation_id = f"r{self._counter:08d}"
        reservation = BudgetReservation(
            reservation_id=reservation_id,
            subject=str(subject),
            tokens=tokens,
            soft_exceeded=self.total_tokens + tokens > self.soft_limit,
            resources=requested,
        )
        self._reserved[reservation_id] = reservation
        return reservation

    def get(self, reservation_id: str) -> BudgetReservation:
        try:
            return self._reserved[reservation_id]
        except KeyError as exc:
            raise BudgetError(f"unknown reservation: {reservation_id}") from exc

    def commit(
        self,
        reservation_id: str,
        actual_tokens: int | None = None,
        actual_resources: Mapping[str, int] | None = None,
    ) -> BudgetReservation:
        reservation = self.get(reservation_id)
        if reservation.committed:
            return reservation
        if actual_tokens is None:
            raise UnknownCostError(f"unknown actual token cost for {reservation.subject}")
        if not isinstance(actual_tokens, int) or isinstance(actual_tokens, bool) or actual_tokens < 0:
            raise UnknownCostError(f"invalid actual token cost for {reservation.subject}")
        reserved = dict(reservation.resources or {"model_tokens": reservation.tokens})
        measured = dict(actual_resources or {})
        # Provider-unknown dimensions are charged at their enforceable
        # reservation. They are never rewritten to zero merely because a
        # provider reported model tokens alone.
        reconciled = {
            key: measured.get(
                key,
                actual_tokens if key == "model_tokens" else reserved.get(key, 0),
            )
            for key in RESOURCE_DIMENSIONS
        }
        actual = self._normalize_resources(actual_tokens, reconciled)
        exceeded = [key for key in RESOURCE_DIMENSIONS if actual[key] > int(reserved.get(key, 0))]
        if exceeded:
            raise HardBudgetExceeded("actual usage exceeds reservation: " + ", ".join(exceeded))
        self._spent += actual_tokens
        for key, value in actual.items():
            self._spent_resources[key] += value
        updated = BudgetReservation(**{**reservation.__dict__, "committed": True})
        self._reserved[reservation_id] = updated
        return updated

    def release(self, reservation_id: str) -> None:
        reservation = self.get(reservation_id)
        if reservation.committed:
            raise BudgetError("cannot release a committed reservation")
        self._reserved.pop(reservation_id, None)

    def snapshot(self) -> dict[str, Any]:
        return {
            "soft_limit": self.soft_limit,
            "hard_limit": self.hard_limit,
            "reserved_tokens": self.reserved_tokens,
            "committed_tokens": self.committed_tokens,
            "total_tokens": self.total_tokens,
            "soft_exceeded": self.soft_exceeded,
            "resource_limits": dict(self.resource_limits),
            "reserved_resources": self.reserved_resources,
            "committed_resources": dict(self._spent_resources),
            "total_resources": self.total_resources,
            "tranche_percentages": list(TRANCHE_PERCENTAGES),
            "tranche_limits": list(self.tranche_limits),
            "released_tranches": self.released_tranches,
            "released_token_limit": self.released_token_limit,
            "reservations": [
                self._reserved[key].to_dict() for key in sorted(self._reserved)
            ],
        }
