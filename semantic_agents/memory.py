from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Frame:
    predicate: str
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class Script:
    """A deterministic reversible grammar: literal prefix followed by atomic roles."""
    predicate: str
    prefix: tuple[str, ...]
    roles: tuple[str, ...]

    def parse(self, words: tuple[str, ...]) -> Frame:
        if (words[:len(self.prefix)] != self.prefix
                or len(words) != len(self.prefix) + len(self.roles)):
            raise ValueError("text does not match script")
        return Frame(self.predicate, words[len(self.prefix):])

    def generate(self, frame: Frame) -> str:
        if frame.predicate != self.predicate or len(frame.arguments) != len(self.roles):
            raise ValueError("frame does not match script")
        if any(not value or any(c.isspace() for c in value) for value in frame.arguments):
            raise ValueError("roles must be nonempty atomic tokens")
        return " ".join(self.prefix + frame.arguments)


class MetaLinguisticMemory:
    """Sparse Boolean vectors are sets; postings are their transposed index."""
    def __init__(self) -> None:
        self.features: dict[str, frozenset[str]] = {}
        self.postings: dict[str, set[str]] = defaultdict(set)
        self.parents: dict[str, set[str]] = defaultdict(set)
        self.children: dict[str, set[str]] = defaultdict(set)
        self.scripts: dict[str, Script] = {}
        self.dispatch: dict[str, Script] = {}
        self.frames: list[Frame] = []

    def concept(self, name: str, features: set[str]) -> None:
        for feature in self.features.get(name, ()):
            self.postings[feature].discard(name)
        self.features[name] = frozenset(features)
        for feature in features:
            self.postings[feature].add(name)

    def inherit(self, child: str, parent: str) -> None:
        if child not in self.features or parent not in self.features:
            raise KeyError("declare concepts first")
        if child == parent or child in self.ancestors(parent):
            raise ValueError("inheritance must be acyclic")
        self.parents[child].add(parent)
        self.children[parent].add(child)

    def ancestors(self, name: str) -> set[str]:
        return self._closure(name, self.parents)

    def descendants(self, name: str) -> set[str]:
        return self._closure(name, self.children)

    @staticmethod
    def _closure(name: str, adjacency: dict[str, set[str]]) -> set[str]:
        seen: set[str] = set()
        todo = list(adjacency.get(name, ()))
        while todo:
            current = todo.pop()
            if current not in seen:
                seen.add(current)
                todo.extend(adjacency.get(current, ()))
        return seen

    def effective_features(self, name: str) -> frozenset[str]:
        if name not in self.features:
            raise KeyError(name)
        return frozenset().union(*(self.features[n] for n in {name} | self.ancestors(name)))

    def lookup(self, required: set[str]) -> set[str]:
        """Descendant expansion retrieves inherited features without upward truth leakage."""
        if not required:
            return set(self.features)
        candidates = []
        for feature in required:
            matches: set[str] = set()
            for owner in self.postings.get(feature, ()):
                matches.add(owner)
                matches.update(self.descendants(owner))
            candidates.append(matches)
        return set.intersection(*candidates)

    def add_script(self, script: Script) -> None:
        if not script.prefix or script.predicate in self.scripts or script.prefix[0] in self.dispatch:
            raise ValueError("scripts require unique predicates and first-token dispatch")
        self.scripts[script.predicate] = script
        self.dispatch[script.prefix[0]] = script

    def parse(self, text: str) -> Frame:
        words = tuple(text.split())
        if not words or words[0] not in self.dispatch:
            raise ValueError("unknown script")
        return self.dispatch[words[0]].parse(words)

    def generate(self, frame: Frame) -> str:
        return self.scripts[frame.predicate].generate(frame)
