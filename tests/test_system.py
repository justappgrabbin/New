import asyncio
import unittest
from time import monotonic

from semantic_agents.agent import AutonomousAgent, compose
from semantic_agents.demo import simulate
from semantic_agents.graph import SemanticSpacetimeGraph
from semantic_agents.memory import Frame, MetaLinguisticMemory, Script
from semantic_agents.promise import Imposition, Polarity, Promise


class MemoryTests(unittest.TestCase):
    def test_inheritance_and_no_upward_truth_leakage(self):
        m = MetaLinguisticMemory()
        m.concept("animal", {"alive"})
        m.concept("bird", {"feathered"})
        m.inherit("bird", "animal")
        self.assertEqual(m.lookup({"alive", "feathered"}), {"bird"})
        self.assertEqual(m.ancestors("bird"), {"animal"})
        self.assertEqual(m.descendants("animal"), {"bird"})
        self.assertNotIn("feathered", m.effective_features("animal"))
        with self.assertRaises(ValueError):
            m.inherit("animal", "bird")

    def test_shared_notation_roundtrip(self):
        m = MetaLinguisticMemory()
        m.add_script(Script("likes", ("likes",), ("subject", "object")))
        frame = Frame("likes", ("alice", "tea"))
        self.assertEqual(m.parse(m.generate(frame)), frame)
        with self.assertRaises(ValueError):
            m.parse("likes alice")


class AgentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.graph = SemanticSpacetimeGraph()
        self.memory = MetaLinguisticMemory()
        self.memory.add_script(Script("task", ("task",), ("topic",)))
        self.calls = 0

        async def handler(frame):
            self.calls += 1
            return frame

        self.agent = AutonomousAgent("a", self.graph, self.memory, handler,
                                     lambda r: r.sender == "trusted")
        self.agent.publish(Promise("p", "a", "task", Polarity.PROVIDE,
                                   "lab", monotonic() + 60))

    def request(self, **changes):
        values = dict(id="r", sender="trusted", recipient="a", intent="task",
                      scope="lab", payload="task topic")
        return Imposition(**(values | changes))

    async def test_concurrent_duplicate_only_runs_once(self):
        results = await asyncio.gather(*(self.agent.consider(self.request()) for _ in range(5)))
        self.assertTrue(all(r.status == "kept" for r in results))
        self.assertEqual(self.calls, 1)
        with self.assertRaises(ValueError):
            await self.agent.consider(self.request(payload="task other"))

    async def test_declines_and_withdrawal(self):
        for change in ({"sender": "stranger"}, {"scope": "other"}, {"intent": "command"}):
            self.assertEqual((await self.agent.consider(self.request(**change))).status, "declined")
        self.agent.withdraw("p")
        self.assertEqual((await self.agent.consider(self.request())).status, "declined")
        self.assertEqual(self.calls, 0)

    async def test_expiry_and_timeout(self):
        self.agent.publish(Promise("p", "a", "task", Polarity.PROVIDE, "lab", monotonic() - 1))
        self.assertEqual((await self.agent.consider(self.request())).status, "declined")
        self.agent.publish(Promise("p", "a", "task", Polarity.PROVIDE, "lab", monotonic() + 60))
        async def slow(frame):
            await asyncio.sleep(1)
            return frame
        self.agent._handler = slow
        self.agent.timeout = .001
        self.assertEqual((await self.agent.consider(self.request())).status, "broken")

    async def test_simulation(self):
        results, graph = await simulate()
        self.assertEqual(results[-1], "review promises unverified")
        self.assertEqual([e.kind for e in graph.events()], ["accepted", "kept", "accepted", "kept"])


if __name__ == "__main__":
    unittest.main()
