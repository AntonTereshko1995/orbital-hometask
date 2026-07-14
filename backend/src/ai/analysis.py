from __future__ import annotations

import re


def count_sources_cited(response: str) -> int:
    """Count the number of references to document sections, clauses, pages, etc."""
    patterns = [
        r"section\s+\d+",
        r"clause\s+\d+",
        r"page\s+\d+",
        r"paragraph\s+\d+",
    ]
    return sum(len(re.findall(pattern, response, re.IGNORECASE)) for pattern in patterns)
