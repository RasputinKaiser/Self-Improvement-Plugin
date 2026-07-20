"""Deterministic ready-task scheduling with canonical path compatibility."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .canonical import canonical_path, paths_overlap, task_sets_compatible
from .contracts import TaskSpec
from .dag import TaskGraph, compile_dag


@dataclass(frozen=True)
class ScheduledTask:
    task: TaskSpec
    critical_path: float

    @property
    def task_id(self) -> str:
        return self.task.id


def compatible(left: TaskSpec, right: TaskSpec) -> bool:
    return task_sets_compatible(left.read_set, left.write_set, right.read_set, right.write_set)


class PathLockTable:
    """In-memory path locks used by one controller process.

    Locks are advisory scheduling state; the durable event stream remains the
    authority for task transitions.  Nested paths overlap so a worker writing a
    directory cannot race a worker reading a file beneath it.
    """

    def __init__(self) -> None:
        self._readers: dict[str, set[str]] = {}
        self._writers: dict[str, str] = {}
        self._owned: dict[str, TaskSpec] = {}

    def can_acquire(self, task: TaskSpec, owner: str | None = None) -> bool:
        for path, holders in self._readers.items():
            if any(paths_overlap(path, requested) for requested in task.write_set):
                if any(holder != owner for holder in holders):
                    return False
        for path, holder in self._writers.items():
            if holder == owner:
                continue
            if any(paths_overlap(path, requested) for requested in (*task.read_set, *task.write_set)):
                return False
        # A requested read can also conflict with a reader? no.  Writes against
        # existing readers are covered above, including parent/child paths.
        return True

    def acquire(self, owner: str, task: TaskSpec) -> bool:
        held = self._owned.get(owner)
        if held is not None:
            # One owner maps to one durable task attempt. Silently replacing
            # it would strand the first task's path locks.
            return held == task
        if not self.can_acquire(task, owner):
            return False
        for path in task.read_set:
            self._readers.setdefault(str(canonical_path(path)), set()).add(owner)
        for path in task.write_set:
            self._writers[str(canonical_path(path))] = owner
        self._owned[owner] = task
        return True

    def release(self, owner: str) -> None:
        task = self._owned.pop(owner, None)
        if task is None:
            return
        for path in task.read_set:
            key = str(canonical_path(path))
            holders = self._readers.get(key)
            if holders:
                holders.discard(owner)
                if not holders:
                    self._readers.pop(key, None)
        for path in task.write_set:
            key = str(canonical_path(path))
            if self._writers.get(key) == owner:
                self._writers.pop(key, None)

    def held_by(self, owner: str) -> TaskSpec | None:
        return self._owned.get(owner)


def schedule_ready(
    graph: TaskGraph | Iterable[TaskSpec],
    completed: Iterable[str] = (),
    running: Iterable[str] = (),
    concurrency: int | None = None,
    locks: PathLockTable | None = None,
) -> tuple[ScheduledTask, ...]:
    compiled = graph if isinstance(graph, TaskGraph) else compile_dag(graph)
    lock_table = locks or PathLockTable()
    selected: list[ScheduledTask] = []
    running_ids = set(running)
    for task in compiled.ready(completed, running):
        if concurrency is not None and len(selected) >= max(0, concurrency):
            break
        if not lock_table.can_acquire(task):
            continue
        if any(not compatible(task, item.task) for item in selected):
            continue
        selected.append(ScheduledTask(task, compiled.critical_path_weight(task.id)))
        running_ids.add(task.id)
    return tuple(selected)


def deterministic_ready_order(
    graph: TaskGraph | Iterable[TaskSpec], completed: Iterable[str] = (), running: Iterable[str] = ()
) -> tuple[str, ...]:
    return tuple(item.task_id for item in schedule_ready(graph, completed, running))
