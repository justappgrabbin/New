"""In-memory typed property multigraph; replace with transactional storage in production."""
from dataclasses import dataclass
from threading import RLock
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class Event:
    id: str
    tick: int
    kind: str
    actor: str
    scope: str
    request_id: str | None
    detail: str


class SemanticSpacetimeGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[tuple[str, str, str, dict[str, Any]]] = []
        self._events: list[Event] = []
        self._lock = RLock()

    def node(self, key: str, kind: str, **properties: Any) -> None:
        with self._lock:
            old = self._nodes.get(key)
            if old and old["kind"] != kind:
                raise ValueError("node type cannot change")
            self._nodes[key] = {**(old or {}), **properties, "kind": kind}

    def relate(self, source: str, relation: str, target: str, **properties: Any) -> None:
        with self._lock:
            if source not in self._nodes or target not in self._nodes:
                raise KeyError("both endpoints must exist")
            self._edges.append((source, relation, target, properties))

    def record(self, kind: str, actor: str, scope: str,
               request_id: str | None = None, detail: str = "") -> Event:
        with self._lock:
            event = Event(str(uuid4()), len(self._events), kind, actor,
                          scope, request_id, detail)
            self._events.append(event)
            self.node("event:" + event.id, "Event", tick=event.tick,
                      event_kind=kind, scope=scope, request_id=request_id,
                      detail=detail)
            if actor in self._nodes:
                self.relate(actor, "OBSERVED", "event:" + event.id)
            return event

    def events(self) -> tuple[Event, ...]:
        with self._lock:
            return tuple(self._events)

    def snapshot(self) -> dict[str, Any]:
        from copy import deepcopy
        with self._lock:
            return deepcopy({"nodes": self._nodes, "edges": self._edges})
