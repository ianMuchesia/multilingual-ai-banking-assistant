"""transfer_help: a static FAQ (limits, charges, timings per channel). All values are DEMO values."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from bankchat.domain import ReplyKind
from bankchat.schemas import ReplyOut


@dataclass(frozen=True)
class FaqTopic:
    id: str
    keywords: tuple[str, ...]
    answer: str


@dataclass(frozen=True)
class TransferFaq:
    disclaimer: str
    default_topic: str
    topics: tuple[FaqTopic, ...]

    def find(self, text: str) -> FaqTopic:
        """The topic whose keywords appear most often in `text`; the default topic if none do."""
        lowered = text.lower()

        def hits(topic: FaqTopic) -> int:
            return sum(1 for k in topic.keywords if re.search(rf"(?<!\w){re.escape(k)}(?!\w)", lowered))

        best = max(self.topics, key=hits)
        if hits(best) == 0:
            return next(t for t in self.topics if t.id == self.default_topic)
        return best


def load_transfer_faq(path: Path) -> TransferFaq:
    raw = json.loads(path.read_text(encoding="utf-8"))
    topics = tuple(FaqTopic(t["id"], tuple(k.lower() for k in t["keywords"]), t["answer"]) for t in raw["topics"])
    if not any(t.id == raw["default_topic"] for t in topics):
        raise ValueError(f"{path.name}: default_topic {raw['default_topic']!r} is not a topic")
    return TransferFaq(raw["disclaimer"], raw["default_topic"], topics)


def transfer_help_reply(faq: TransferFaq, text: str) -> ReplyOut:
    topic = faq.find(text)
    answer = f"{topic.answer} ({faq.disclaimer})"
    return ReplyOut(kind=ReplyKind.TRANSFER_HELP.value, text=answer, data={"topic": topic.id, "answer": answer})
