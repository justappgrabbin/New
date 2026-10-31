# Autonomous semantic agents: initial blueprint

This is an executable research skeleton with production-oriented boundaries, not
a production-ready distributed runtime. It operationalizes ideas inspired by
Klein and Burgess; it does not claim to reproduce their historical formalisms
exactly. No framework can guarantee strictly linear unrestricted reasoning,
arbitrary natural-language understanding, or stability of autonomous agents.

## Boundaries and data flow

```text
 External user / environment
       | Imposition(intent, scope, payload, idempotency key)
       v
 =================== agent A autonomy boundary ===================
 | local policy + active promises + capacity + input budget      |
 |      | decline                    | voluntarily accept       |
 |      v                            v                          |
 | audit event             script parser -> semantic Frame      |
 |                         Boolean memory <-> local reasoning   |
 |                         handler/LLM -> frame validation       |
 |                                      -> same script generator|
 =================================================================
       | voluntary offer                            | observations
       v                                            v
 =================== agent B boundary ======    SST property graph
 | independent admission / reasoning       |    Agent --PROMISES--> Promise
 | no inherited obligation to execute      |    Concept --IS_A----> Concept
 ===========================================    Agent --OBSERVED--> Event
       |                                        Promise --BINDS--> Promise
       +-- membership offer/acceptance --------> SuperAgent (scope, layer)

 Transport / graph adapters deliver messages and persist observations.
 They do not choose an agent's obligations or dictate its next action.
```

The shared graph is an observation and discovery substrate, not an omniscient
controller. Individual agents own their state, policies, credentials, memory,
and execution decisions. A graph database can be operationally centralized
without introducing centralized decision authority; deployment can later shard
it by scope. Agents must tolerate stale discovery data by rechecking promises.
The demo's two calls are a deterministic test fixture, not a production scheduler.

## Promise algebra and voluntary composition

Let `P(a,+b,s,t)` mean agent a promises to provide behavior b in scope s until t.
`P(c,-b,s,u)` means c promises to accept b; it does not force c to execute a handler.
An imposition `I(x,a,b,s,payload)` asks a to consider b and confers no authority.

The implementation uses these restricted composition rules:

1. **Binding:** `P(a,+b,s,t) ⊗ P(c,-b,s,u)` is compatible while both are live,
   their behaviors and scopes match, and a differs from c.
2. **Admission:** local policy AND active provision promise AND capacity AND
   budget permit acceptance. An acceptance is followed by kept, broken, or
   cancelled assessment; a promise is not a guarantee of success.
3. **Aggregation:** a compatible binding plus independent membership consent
   from both endpoints permits a named coalition at a declared scale layer.
4. **Withdrawal:** an issuer can withdraw its own promise. New work is declined;
   already accepted work follows its local cancellation policy.

`compose()` implements a minimal bilateral handshake and records voluntary
membership; a SuperAgent has no command channel. Higher layers can advertise an
aggregate service only through an autonomous representative's own conditional
promise. Nested coalition membership, lease renewal, and automatic repair are
design extensions, not implemented runtime features.

Production stability requires expiring membership leases, explicit dependency
conditions, bounded admission, hysteresis before joining/leaving, periodic local
reassessment, and removal of bindings whose promises expire. A sufficient local
operating condition is sustainable arrival rate below service capacity at each
member, compatible live promises, and bounded retry traffic. This is not a proof
of global convergence under arbitrary policies or network partitions. Never
transfer responsibility for a member's promise to a coalition automatically.

## Semantic spacetime graph

Use typed, namespaced IDs and a property multigraph. Multiple edges preserve
different observations between the same entities. Proposed durable schema:

| Node | Principal properties |
|---|---|
| Agent | identity, policy_version, trust_domain |
| Promise | issuer, behavior/type, polarity, scope, valid_from, expires_at, version |
| Concept | symbol, ontology_version, explicit sparse features |
| Frame | predicate, typed arguments, provenance, confidence category |
| Event | event_id, actor, request_id, local_sequence, timestamp, scope, outcome |
| SuperAgent | scope, scale_layer, membership_policy, lease |
| Artifact | content_hash, media_type, provenance, access_scope |

Qualitative edges: `IS_A`, `HAS_ROLE`, `DENOTES`, `REQUIRES`, `PRODUCES`.
Behavioral edges: `PROMISES`, `BINDS`, `REQUESTED`, `ACCEPTED`, `FULFILLED`.
Spatial/scale edges: `IN_SCOPE`, `VOLUNTARILY_JOINS`, `CONTAINS`.
Temporal/causal edges: `OBSERVED`, `CAUSED_BY`, `NEXT_LOCAL_EVENT`.

Attach validity intervals and provenance to changing relations. An agent's scope
is a visibility/trust boundary; a layer is a coarse-graining scale, not a command
rank. Distances may represent observed communication latency or hop count; keep
these separate from symbolic semantic relations. Causal paths describe actual
execution rather than prescribe a pipeline. A coarse-grained coalition view
summarizes member activity without erasing the underlying causal events.

`SemanticSpacetimeGraph` implements thread-protected typed nodes, multi-edges,
and append-only events. Its tick is only a single-process observation sequence,
not physical time or distributed causality. Promise deadlines use a local
monotonic clock and cannot be persisted or compared across machines. A durable
adapter needs UTC lease timestamps with clock-skew policy, local monotonic
timers, causal correlation IDs, transactionally maintained event links, indexed
scope/intent/validity queries, and uniqueness constraints. The extended schema
above is a blueprint; the prototype implements its Agent/Promise/Event/coalition
subset. It does not yet persist all impositions, artifacts, or semantic frames.

## Discrete cognition and memory

`Frame(predicate, arguments)` is the common semantic notation. Concepts are
discrete symbols, and explicit feature sets are sparse Boolean vectors. The
inverse `feature -> concepts` postings index is the vector transpose. `IS_A`
inheritance has both parent and child indexes: descendants inherit generic
features; a query can travel upward to abstractions and downward to examples.
Reverse navigation never promotes a child's feature into a universal parent
fact. Cycles are rejected. Multiple inheritance is permitted; the prototype
supports positive Boolean facts only, so negation, defaults, exceptions, and
contradiction handling require a separate truth-maintenance policy.

A `Script(predicate, literal_prefix, ordered_roles)` defines both text parsing
and text generation. Example:

```python
Script('finding', ('finding',), ('topic', 'claim'))
# finding promises needs_evidence
# <-> Frame('finding', ('promises', 'needs_evidence'))
```

The state machine is `idle -> admitted -> parsed -> evaluated -> generated ->
assessed -> idle`; refusal returns directly from admission. The same script
describes the surface realization and its semantic roles in both directions.
Current scripts are controlled-language templates with atomic role values.
They encode relational structure, not a complete world-knowledge inference
engine. A next step is bounded Horn-style transitions over the same Frames:
`finding(topic, needs_evidence) -> review(topic, unverified)`, with fixed fan-out
and a per-request step budget. The demo implements that transition in a handler.
Arbitrary recursive rule evaluation is deliberately outside the linear contract.

Linear-time claims apply only to splitting a bounded text, first-token script
dispatch, deterministic parsing, and generation: O(input/output length), with
fixed script shape and no ambiguity or backtracking. Graph closure costs
O(visited vertices + visited edges). Boolean retrieval costs visited posting and
descendant entries, including overlap; it is not O(text length). Precomputing
feature closure trades faster lookup for update cost and potentially quadratic
storage. LLM calls have their own cost and no linear-time guarantee. Enforce
limits for text bytes, token count, graph visits, rule steps, output size, and
wall-clock time before claiming bounded end-to-end operation.

## Modules and deployment boundary

* `promise.py`: immutable declarations, polarities, scope/lease compatibility,
  and impositions with idempotency keys.
* `agent.py`: issuer-owned publication/withdrawal, local admission, private busy
  state, timeout, outcome assessment, in-process deduplication and composition.
* `graph.py`: replaceable typed graph/event storage seam.
* `memory.py`: symbolic Frames, sparse features, inheritance, reversible scripts.
* `demo.py`: deterministic two-agent research simulation, requiring no API keys.

An LLM adapter implements the async `Frame -> Frame` handler. Supply only scoped
retrieved facts and typed output constraints; validate the returned predicate,
role types, provenance, and permitted tool effects locally. A generated claim
does not become a trusted fact automatically. In production, enforce request
and frame types against each intent's input/output schema. The skeleton checks
the input predicate against the admitted intent and output against its script;
it does not implement complete intent-specific output contracts.

Before deployment, add authenticated sender identities (the prototype trusts
sender strings), per-scope authorization, durable inbox/outbox transactions,
bounded queues and deduplication retention, retry/backoff, distributed tracing,
encrypted persistence, schema migrations, and process isolation for blocking or
untrusted tools. Async timeouts cannot interrupt a blocking handler. Holding a
local lock serializes one agent; it is not a distributed lock. Cached outcomes
cover only this process lifetime, not exactly-once external effects. Handlers
need effect-level idempotency. Never execute generated code in the agent process.
Graph writes and local outcomes are not transactionally atomic in this skeleton.
Composition is not an atomic distributed membership transaction and needs a
lease-based protocol before remote use. Full payloads are omitted from audit
events; production metadata still needs access and retention policies.

## Run and test

Requires Python 3.11 or later, with no runtime dependencies:

```bash
cd /workspace/semantic_agents
python -m unittest discover -s tests -v
python -m semantic_agents.demo
```

Expected simulation output:

```text
finding promises needs_evidence
review promises unverified
events: accepted, kept, accepted, kept
```

The research agent and reviewer publish compatible promises, independently
consent to the coalition, consider a scoped research request, and exchange a
finding. The verdict intentionally preserves lack of evidence. Six tests cover
round-trip notation, inheritance direction and cycles, concurrent duplicate
suppression, conflicting idempotency keys, policy/scope/intent refusal,
withdrawal, expiry, timeout, and the full simulation.

For the next integration stage, run each peer in its own process with durable
transport. Inject duplicate delivery, delayed events, expired membership,
crashes after external effects, partitions, contradictory facts, and malformed
LLM frames. Verify that each peer retains refusal authority, no silent fact
promotion occurs, causal traces remain reconstructable, and retries do not
duplicate effects. Measure graph visits and parser work separately; benchmark
growing controlled-language inputs rather than claiming generic linear cognition.
