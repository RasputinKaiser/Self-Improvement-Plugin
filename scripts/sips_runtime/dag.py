"""Strict AND dependency graph compilation and ready-set operations."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable, Mapping

from .contracts import TaskSpec


class DAGError(ValueError):
    pass


@dataclass(frozen=True)
class TaskGraph:
    tasks: Mapping[str, TaskSpec]
    children: Mapping[str, tuple[str, ...]]
    critical_paths: Mapping[str, float]

    @property
    def critical_path_weights(self) -> Mapping[str, float]:
        return self.critical_paths

    @property
    def nodes(self) -> Mapping[str, TaskSpec]:
        return self.tasks

    @classmethod
    def compile(cls, tasks: Iterable[TaskSpec | Mapping[str, object]]) -> "TaskGraph":
        parsed = [task if isinstance(task, TaskSpec) else TaskSpec.from_dict(task) for task in tasks]
        if not parsed:
            raise DAGError("task graph must contain at least one task")
        by_id: dict[str, TaskSpec] = {}
        for task in parsed:
            if task.id in by_id:
                raise DAGError(f"duplicate task id: {task.id}")
            if not isinstance(task.merge_contract, Mapping):
                raise DAGError(f"task {task.id} merge contract must be an object")
            merge_strategy = str(task.merge_contract.get("strategy", "")).strip()
            if merge_strategy != "deterministic":
                raise DAGError(
                    f"task {task.id} merge strategy must be deterministic, "
                    f"got {merge_strategy or 'missing'}"
                )
            for raw_path in (*task.read_set, *task.write_set):
                value = str(raw_path).replace("\\", "/")
                if (
                    not value
                    or any(character in value for character in "*?[]")
                    or ".." in PurePosixPath(value).parts
                ):
                    raise DAGError(
                        f"task {task.id} has unresolved or escaping path: {raw_path!r}"
                    )
            by_id[task.id] = task
        children: dict[str, list[str]] = {task_id: [] for task_id in by_id}
        for task in parsed:
            seen: set[str] = set()
            for dependency in task.depends_on:
                if dependency not in by_id:
                    raise DAGError(f"task {task.id} depends on unknown task {dependency}")
                if dependency == task.id:
                    raise DAGError(f"task {task.id} depends on itself")
                if dependency in seen:
                    raise DAGError(f"task {task.id} has duplicate dependency {dependency}")
                seen.add(dependency)
                children[dependency].append(task.id)
        frozen_children = {task_id: tuple(sorted(items)) for task_id, items in children.items()}

        # A Kahn pass gives a strict cycle check and avoids relying on recursion
        # depth for a large generated graph.
        indegree = {task_id: len(task.depends_on) for task_id, task in by_id.items()}
        queue = sorted(task_id for task_id, degree in indegree.items() if degree == 0)
        visited: list[str] = []
        while queue:
            current = queue.pop(0)
            visited.append(current)
            for child in frozen_children[current]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
                    queue.sort()
        if len(visited) != len(by_id):
            remaining = sorted(task_id for task_id, degree in indegree.items() if degree > 0)
            raise DAGError("dependency cycle detected: " + " -> ".join(remaining))

        critical: dict[str, float] = {}
        for task_id in reversed(visited):
            children_weight = max((critical[child] for child in frozen_children[task_id]), default=0.0)
            critical[task_id] = float(by_id[task_id].weight) + children_weight
        return cls(tasks=dict(by_id), children=frozen_children, critical_paths=critical)

    def critical_path_weight(self, task_id: str) -> float:
        try:
            return self.critical_paths[task_id]
        except KeyError as exc:
            raise KeyError(f"unknown task: {task_id}") from exc

    def critical_path(self, task_id: str) -> float:
        return self.critical_path_weight(task_id)

    def ready(self, completed: Iterable[str] = (), running: Iterable[str] = ()) -> tuple[TaskSpec, ...]:
        completed_set = set(completed)
        running_set = set(running)
        ready = [
            task
            for task in self.tasks.values()
            if task.id not in completed_set
            and task.id not in running_set
            and all(dep in completed_set for dep in task.depends_on)
        ]
        # Stable scheduler contract: priority, critical path, value/token
        # density, estimated cost, source insertion ordinal, then id.
        def key(task: TaskSpec) -> tuple[float, float, float, float, int, str]:
            density = (
                task.expected_value / task.estimated_tokens
                if task.estimated_tokens not in (None, 0)
                else task.expected_value
            )
            estimated = task.estimated_tokens if task.estimated_tokens is not None else 2**63 - 1
            return (
                -task.priority,
                -self.critical_paths[task.id],
                -density,
                float(estimated),
                task.insertion_ordinal,
                task.id,
            )

        ready.sort(key=key)
        return tuple(ready)

    def ready_ids(self, completed: Iterable[str] = (), running: Iterable[str] = ()) -> tuple[str, ...]:
        return tuple(task.id for task in self.ready(completed, running))

    def to_dict(self) -> dict[str, object]:
        return {
            "tasks": [self.tasks[task_id].to_dict() for task_id in sorted(self.tasks)],
            "critical_path_weights": {task_id: self.critical_paths[task_id] for task_id in sorted(self.tasks)},
        }


def compile_dag(tasks: Iterable[TaskSpec | Mapping[str, object]]) -> TaskGraph:
    return TaskGraph.compile(tasks)


def ready_tasks(
    graph: TaskGraph | Iterable[TaskSpec | Mapping[str, object]],
    completed: Iterable[str] = (),
    running: Iterable[str] = (),
) -> tuple[TaskSpec, ...]:
    compiled = graph if isinstance(graph, TaskGraph) else compile_dag(graph)
    return compiled.ready(completed, running)


# Alias kept deliberately small for callers that call this operation a plan.
validate_dag = compile_dag
