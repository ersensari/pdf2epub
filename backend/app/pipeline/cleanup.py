"""Page-level text cleanup: intro/front-matter detection, page-number and
running-header removal.

Pure text functions — no FastAPI or LLM dependencies, unit-testable in
isolation.
"""

import re
from collections import Counter

_JUNK_MARKERS = [
    "publisher",
    "isbn",
    "copyright",
    "printed",
    "reserved",
    "edition",
    "all rights",
    "www.",
    "http",
    "notice:",
    "warning:",
    "disclaimer",
    "table of contents",
    "contents:",
    # Turkish equivalents commonly found in old books
    "yayınevi",
    "yayınları",
    "basımevi",
    "matbaası",
    "baskı",
    "her hakkı",
    "telif",
    "içindekiler",
]

# A line that is only a page number, possibly decorated:
#   "12", "- 12 -", "— 12 —", "[12]", "(12)", "Sayfa 12", "12 / 348", "* 12 *"
_PAGE_NUMBER_LINE = re.compile(
    r"""^\s*
    [-–—*._\[\(\s]*                # leading decoration
    (?:sayfa|page|s\.|p\.)?\s*     # optional label
    \d{1,4}                        # the number itself
    (?:\s*/\s*\d{1,4})?            # optional "12 / 348" form
    [-–—*._\]\)\s]*                # trailing decoration
    $""",
    re.IGNORECASE | re.VERBOSE,
)

# Roman-numeral-only lines (front matter pagination): "iv", "XII", "- vii -".
# Uses real roman-numeral grammar so short words like "dil" don't match.
_ROMAN_NUMERAL_LINE = re.compile(
    r"^\s*[-–—*._\[\(\s]*"
    r"(?=[ivxlcdm])m{0,3}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})"
    r"[-–—*._\]\)\s]*$",
    re.IGNORECASE,
)

# How many of the first/last lines of a page we inspect for artifacts.
_EDGE_LINES = 3

# A header line must repeat on at least this fraction of pages to be
# considered a running header rather than real content.
_RUNNING_HEADER_MIN_RATIO = 0.3
_RUNNING_HEADER_MIN_PAGES = 5


def is_intro_page(text: str) -> bool:
    """Detect if a page is likely intro/frontmatter that should be skipped.

    Looks for: copyright, ISBN, publisher info, table of contents, etc.
    """
    if not text or len(text.strip()) < 50:
        return True

    text_lower = text.lower()
    marker_count = sum(1 for marker in _JUNK_MARKERS if marker in text_lower)

    # If more than 2 junk markers, likely intro/metadata
    if marker_count >= 2:
        return True

    # If mostly non-alphanumeric (list/table format)
    alphanumeric = sum(1 for c in text if c.isalnum() or c.isspace())
    if len(text) > 0 and alphanumeric / len(text) < 0.4:
        return True

    return False


def filter_pages(pages: list[str]) -> tuple[list[str], list[int]]:
    """Filter out intro pages, return (filtered_pages, removed_indices)."""
    filtered = []
    removed = []

    for idx, text in enumerate(pages):
        if not is_intro_page(text):
            filtered.append(text)
        else:
            removed.append(idx + 1)  # 1-indexed

    return filtered, removed


def _is_page_number_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return bool(
        _PAGE_NUMBER_LINE.match(stripped) or _ROMAN_NUMERAL_LINE.match(stripped)
    )


def strip_page_artifacts(text: str) -> str:
    """Remove page-number lines from the top and bottom edges of a page.

    Only the first/last few lines are inspected so that a bare number inside
    the body (e.g. a year in a sentence broken across lines) survives.
    """
    lines = text.splitlines()

    # Strip from the top edge.
    start = 0
    inspected = 0
    for i, line in enumerate(lines):
        if inspected >= _EDGE_LINES:
            break
        if not line.strip():
            start = i + 1
            continue
        inspected += 1
        if _is_page_number_line(line):
            start = i + 1
        else:
            break

    # Strip from the bottom edge.
    end = len(lines)
    inspected = 0
    for i in range(len(lines) - 1, start - 1, -1):
        if inspected >= _EDGE_LINES:
            break
        if not lines[i].strip():
            end = i
            continue
        inspected += 1
        if _is_page_number_line(lines[i]):
            end = i
        else:
            break

    return "\n".join(lines[start:end]).strip("\n")


def _normalize_header(line: str) -> str:
    """Normalize a candidate header line for cross-page comparison.

    OCR renders the same running header slightly differently on each page;
    lowercasing and collapsing non-alphanumerics makes repeats detectable.
    """
    return re.sub(r"[^a-z0-9çğıöşü]+", " ", line.strip().lower()).strip()


def detect_running_headers(pages: list[str]) -> set[str]:
    """Find normalized header/footer lines repeated across many pages.

    A book/chapter title printed on every page shows up as the same first or
    last non-empty line on a large fraction of pages.
    """
    if len(pages) < _RUNNING_HEADER_MIN_PAGES:
        return set()

    counter: Counter[str] = Counter()
    for text in pages:
        lines = [line for line in text.splitlines() if line.strip()]
        edges = lines[:1] + lines[-1:]
        seen_on_page = set()
        for line in edges:
            normalized = _normalize_header(line)
            # Ignore very short or numeric-only edges (page numbers handled elsewhere).
            if len(normalized) >= 4 and not normalized.replace(" ", "").isdigit():
                seen_on_page.add(normalized)
        counter.update(seen_on_page)

    threshold = max(_RUNNING_HEADER_MIN_PAGES, int(len(pages) * _RUNNING_HEADER_MIN_RATIO))
    return {header for header, count in counter.items() if count >= threshold}


def strip_running_headers(text: str, headers: set[str]) -> str:
    """Remove known running-header lines from the edges of one page."""
    if not headers:
        return text

    lines = text.splitlines()
    non_empty = [i for i, line in enumerate(lines) if line.strip()]
    if not non_empty:
        return text

    drop: set[int] = set()
    for idx in (non_empty[0], non_empty[-1]):
        if _normalize_header(lines[idx]) in headers:
            drop.add(idx)

    kept = [line for i, line in enumerate(lines) if i not in drop]
    return "\n".join(kept).strip("\n")


def clean_pages(pages: list[str]) -> list[str]:
    """Full cleanup pass over a book's pages.

    Order matters: page numbers are stripped first so that running-header
    detection sees the real header lines at the page edges.
    """
    without_numbers = [strip_page_artifacts(text) for text in pages]
    headers = detect_running_headers(without_numbers)
    return [strip_running_headers(text, headers) for text in without_numbers]
