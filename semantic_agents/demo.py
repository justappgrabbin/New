import asyncio
from time import monotonic

from .agent import AutonomousAgent, compose
from .graph import SemanticSpacetimeGraph
from .memory import Frame, MetaLinguisticMemory, Script
from .promise import Imposition, Polarity, Promise


async def simulate() -> tuple[list[str], SemanticSpacetimeGraph]:
    graph = SemanticSpacetimeGraph()

    def memory() -> MetaLinguisticMemory:
        m = MetaLinguisticMemory()
        m.add_script(Script("research", ("research",), ("topic",)))
        m.add_script(Script("finding", ("finding",), ("topic", "claim")))
        m.add_script(Script("review", ("review",), ("topic", "verdict")))
        return m

    async def research(frame: Frame) -> Frame:
        return Frame("finding", (frame.arguments[0], "needs_evidence"))

    async def review(frame: Frame) -> Frame:
        return Frame("review", (frame.arguments[0], "unverified"))

    policy = lambda request: request.scope == "lab"
    researcher = AutonomousAgent("researcher", graph, memory(), research, policy)
    reviewer = AutonomousAgent("reviewer", graph, memory(), review, policy)
    expiry = monotonic() + 60
    researcher.publish(Promise("research", "researcher", "research", Polarity.PROVIDE, "lab", expiry))
    researcher.publish(Promise("findings", "researcher", "finding", Polarity.PROVIDE, "lab", expiry))
    reviewer.publish(Promise("receive", "reviewer", "finding", Polarity.ACCEPT, "lab", expiry))
    reviewer.publish(Promise("review", "reviewer", "finding", Polarity.PROVIDE, "lab", expiry))
    assert compose(researcher, reviewer, "research-cell", "lab")
    # Fixture injects a stimulus; the researcher voluntarily offers its result to its peer.
    initial = Imposition.request("user", "researcher", "research", "lab", "research promises")
    finding = await researcher.consider(initial)
    assert finding.result is not None
    offer = Imposition.request("researcher", "reviewer", "finding", "lab", finding.result)
    verdict = await reviewer.consider(offer)
    assert verdict.result is not None
    return [finding.result, verdict.result], graph


if __name__ == "__main__":
    results, graph = asyncio.run(simulate())
    print("\n".join(results))
    print("events:", ", ".join(event.kind for event in graph.events()))
