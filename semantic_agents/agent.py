import asyncio
from dataclasses import dataclass
from time import monotonic
from typing import Awaitable, Callable

from .graph import SemanticSpacetimeGraph
from .memory import Frame, MetaLinguisticMemory
from .promise import Imposition, Polarity, Promise, compatible


@dataclass(frozen=True)
class Outcome:
    status: str
    result: str | None = None


class AutonomousAgent:
    def __init__(self, identity: str, graph: SemanticSpacetimeGraph,
                 memory: MetaLinguisticMemory,
                 handler: Callable[[Frame], Awaitable[Frame]],
                 policy: Callable[[Imposition], bool], *, timeout: float = 5,
                 max_payload: int = 4096) -> None:
        self.identity, self.graph, self.memory = identity, graph, memory
        self._handler, self._policy = handler, policy
        self.timeout, self.max_payload = timeout, max_payload
        self._promises: dict[str, Promise] = {}
        self._outcomes: dict[str, tuple[Imposition, Outcome]] = {}
        self._lock = asyncio.Lock()
        self._busy = False
        graph.node(identity, "Agent")

    def publish(self, promise: Promise) -> None:
        if promise.issuer != self.identity:
            raise ValueError("only the issuer can publish its promise")
        self._promises[promise.id] = promise
        key = "promise:" + promise.id
        self.graph.node(key, "Promise", intent=promise.intent,
                        polarity=promise.polarity.value, scope=promise.scope,
                        expires_at=promise.expires_at)
        self.graph.relate(self.identity, "PROMISES", key)

    def withdraw(self, promise_id: str) -> None:
        promise = self._promises.pop(promise_id)
        self.graph.record("withdrawn", self.identity, promise.scope, detail=promise_id)

    def promises(self) -> tuple[Promise, ...]:
        return tuple(self._promises.values())

    def can_keep(self, request: Imposition) -> bool:
        return (request.recipient == self.identity and not self._busy
                and len(request.payload) <= self.max_payload
                and any(p.polarity == Polarity.PROVIDE
                        and p.intent == request.intent
                        and p.active(monotonic(), request.scope)
                        for p in self._promises.values())
                and self._policy(request))

    async def consider(self, request: Imposition) -> Outcome:
        # The lock protects local admission and idempotency; it grants no external authority.
        async with self._lock:
            cached = self._outcomes.get(request.id)
            if cached:
                if cached[0] != request:
                    raise ValueError("idempotency key reused with different request")
                return cached[1]
            try:
                admitted = self.can_keep(request)
            except Exception:
                admitted = False
            if not admitted:
                self.graph.record("declined", self.identity, request.scope, request.id)
                return Outcome("declined")
            self._busy = True
            self.graph.record("accepted", self.identity, request.scope, request.id)
            try:
                frame = self.memory.parse(request.payload)
                if frame.predicate != request.intent:
                    raise ValueError("payload predicate does not match admitted intent")
                async with asyncio.timeout(self.timeout):
                    result = await self._handler(frame)
                rendered = self.memory.generate(result)
                self.memory.frames.append(result)
                outcome = Outcome("kept", rendered)
            except asyncio.CancelledError:
                self._outcomes[request.id] = (request, Outcome("cancelled"))
                self.graph.record("cancelled", self.identity, request.scope, request.id)
                raise
            except Exception as error:
                outcome = Outcome("broken", type(error).__name__)
            finally:
                self._busy = False
            self._outcomes[request.id] = (request, outcome)
            self.graph.record(outcome.status, self.identity, request.scope, request.id)
            return outcome

    def join(self, coalition: str, scope: str, layer: int) -> None:
        """Only this local policy decision issues this agent's membership promise."""
        request = Imposition("join:" + coalition, coalition, self.identity,
                             "membership", scope, coalition)
        if not self._policy(request):
            raise ValueError("membership declined by local policy")
        self.graph.node(coalition, "SuperAgent", layer=layer, scope=scope)
        self.graph.relate(self.identity, "VOLUNTARILY_JOINS", coalition,
                          scope=scope, layer=layer)


def compose(provider: AutonomousAgent, consumer: AutonomousAgent,
            coalition: str, scope: str, layer: int = 1) -> bool:
    """A bilateral handshake, not a scheduler. No execution follows from composition."""
    if provider.graph is not consumer.graph:
        raise ValueError("prototype requires a shared graph")
    pairs = [(p, c) for p in provider.promises() for c in consumer.promises()
             if compatible(p, c, monotonic()) and p.scope == scope]
    if not pairs:
        return False
    # Each endpoint independently consents before recording either membership.
    for agent in (provider, consumer):
        offer = Imposition("join:" + coalition, coalition, agent.identity,
                           "membership", scope, coalition)
        if not agent._policy(offer):
            return False
    provider.join(coalition, scope, layer)
    consumer.join(coalition, scope, layer)
    for p, c in pairs:
        provider.graph.relate("promise:" + p.id, "BINDS", "promise:" + c.id,
                              scope=scope)
    return True
