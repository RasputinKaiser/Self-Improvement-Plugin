"""Leases and monotonic fencing for worker task execution."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable

from .contracts import validate_safe_identifier


LEASE_TTL_SECONDS = 90.0
HEARTBEAT_INTERVAL_SECONDS = 15.0
ATTEMPT_CEILING_SECONDS = 900.0


class LeaseError(RuntimeError):
    pass


class StaleLeaseError(LeaseError):
    pass


@dataclass(frozen=True)
class Lease:
    task_id: str
    owner: str
    fencing_token: int
    acquired_at: float
    last_heartbeat: float
    expires_at: float

    @property
    def token(self) -> int:
        return self.fencing_token

    @property
    def valid_until(self) -> float:
        return self.expires_at

    def heartbeat_due(self, now: float) -> bool:
        return now - self.last_heartbeat >= HEARTBEAT_INTERVAL_SECONDS

    def is_expired(self, now: float) -> bool:
        return now >= self.expires_at

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "owner": self.owner,
            "fencing_token": self.fencing_token,
            "acquired_at": self.acquired_at,
            "last_heartbeat": self.last_heartbeat,
            "expires_at": self.expires_at,
        }


class LeaseManager:
    def __init__(
        self,
        *,
        ttl_seconds: float = LEASE_TTL_SECONDS,
        heartbeat_interval: float = HEARTBEAT_INTERVAL_SECONDS,
        attempt_ceiling: float = ATTEMPT_CEILING_SECONDS,
        clock: Callable[[], float] | None = None,
    ) -> None:
        durations = (ttl_seconds, heartbeat_interval, attempt_ceiling)
        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            or value <= 0
            for value in durations
        ):
            raise ValueError("lease durations must be positive")
        self.ttl_seconds = float(ttl_seconds)
        self.heartbeat_interval = float(heartbeat_interval)
        self.attempt_ceiling = float(attempt_ceiling)
        # Epoch time remains comparable across CLI/MCP processes and host
        # restarts. Fencing tokens, not the clock, provide monotonic authority.
        self._clock = clock or time.time
        self._next_token = 0
        self._leases: dict[str, Lease] = {}

    @property
    def next_fencing_token(self) -> int:
        return self._next_token + 1

    def _now(self, now: float | None) -> float:
        value = self._clock() if now is None else now
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            raise ValueError("lease clock value must be finite")
        return float(value)

    def acquire(
        self,
        task_id: str,
        owner: str,
        now: float | None = None,
        fencing_token: int | None = None,
    ) -> Lease:
        validate_safe_identifier(task_id, label="task_id")
        if (
            not isinstance(owner, str)
            or not owner.strip()
            or owner != owner.strip()
        ):
            raise ValueError("owner must be a non-empty trimmed string")
        current_time = self._now(now)
        current = self._leases.get(task_id)
        if current is not None and not current.is_expired(current_time):
            raise LeaseError(f"task {task_id} is already leased")
        if fencing_token is None:
            self._next_token += 1
        else:
            if (
                not isinstance(fencing_token, int)
                or isinstance(fencing_token, bool)
                or fencing_token < 1
            ):
                raise LeaseError("fencing token must be a positive integer")
            if fencing_token <= self._next_token:
                raise LeaseError("fencing token must increase monotonically")
            self._next_token = fencing_token
        lease = Lease(
            task_id=task_id,
            owner=owner,
            fencing_token=self._next_token,
            acquired_at=current_time,
            last_heartbeat=current_time,
            expires_at=current_time + self.ttl_seconds,
        )
        self._leases[task_id] = lease
        return lease

    def get(self, task_id: str) -> Lease | None:
        return self._leases.get(task_id)

    def valid(self, task_id: str, owner: str, fencing_token: int, now: float | None = None) -> bool:
        lease = self._leases.get(task_id)
        return bool(
            lease
            and lease.owner == owner
            and lease.fencing_token == fencing_token
            and not lease.is_expired(self._now(now))
        )

    def require(self, task_id: str, owner: str, fencing_token: int, now: float | None = None) -> Lease:
        lease = self._leases.get(task_id)
        current_time = self._now(now)
        if lease is None or lease.owner != owner or lease.fencing_token != fencing_token:
            raise StaleLeaseError(f"stale fencing token for task {task_id}")
        if lease.is_expired(current_time):
            raise StaleLeaseError(f"expired lease for task {task_id}")
        if current_time - lease.acquired_at >= self.attempt_ceiling:
            raise StaleLeaseError(f"attempt ceiling exceeded for task {task_id}")
        return lease

    def heartbeat(
        self, task_id: str, owner: str, fencing_token: int, now: float | None = None
    ) -> Lease:
        current_time = self._now(now)
        lease = self.require(task_id, owner, fencing_token, current_time)
        updated = Lease(
            task_id=lease.task_id,
            owner=lease.owner,
            fencing_token=lease.fencing_token,
            acquired_at=lease.acquired_at,
            last_heartbeat=current_time,
            expires_at=min(current_time + self.ttl_seconds, lease.acquired_at + self.attempt_ceiling),
        )
        self._leases[task_id] = updated
        return updated

    def release(
        self, task_id: str, owner: str, fencing_token: int, now: float | None = None
    ) -> None:
        self.require(task_id, owner, fencing_token, now)
        self._leases.pop(task_id, None)

    def expire(self, now: float | None = None) -> tuple[str, ...]:
        current_time = self._now(now)
        expired = tuple(sorted(task_id for task_id, lease in self._leases.items() if lease.is_expired(current_time)))
        for task_id in expired:
            self._leases.pop(task_id, None)
        return expired
