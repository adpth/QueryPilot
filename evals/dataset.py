"""Loads the golden set. One JSON object per line."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Example:
    id: str
    database: str
    question: str
    reference_sql: str

    @property
    def order_matters(self) -> bool:
        """Row order only counts when the reference query asks for an ordering."""
        return "order by" in self.reference_sql.lower()


def load(path: Path) -> list[Example]:
    examples = []
    for line in path.read_text().splitlines():
        if line.strip():
            examples.append(Example(**json.loads(line)))
    return examples
