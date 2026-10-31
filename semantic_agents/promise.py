from dataclasses import dataclass
from enum import Enum
from uuid import uuid4


class Polarity(str, Enum):
    PROVIDE = "+"
    ACCEPT = "-"


@dataclass(frozen=True)
class Promise:
    id: str
    issuer: str
    intent: str
    polarity: Polarity
    scope: str
    expires_at: float

    def active(self, now: float, scope: str) -> bool:
        return now < self.expires_at and scope == self.scope


@dataclass(frozen=True)
class Imposition:
    """A request with no authority to force acceptance. IDs are idempotency keys."""
    id: str
    sender: str
    recipient: str
    intent: str
    scope: str
    payload: str

    @classmethod
    def request(cls, sender: str, recipient: str, intent: str,
                scope: str, payload: str) -> "Imposition":
        return cls(str(uuid4()), sender, recipient, intent, scope, payload)


def compatible(provider: Promise, consumer: Promise, now: float) -> bool:
    return (provider.polarity == Polarity.PROVIDE
            and consumer.polarity == Polarity.ACCEPT
            and provider.intent == consumer.intent
            and provider.issuer != consumer.issuer
            and provider.active(now, consumer.scope)
            and consumer.active(now, provider.scope))
