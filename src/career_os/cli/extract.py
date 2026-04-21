"""Resume text extraction utilities for the CLI wizard.

Provides regex-based contact info extraction, ESCO skill fuzzy matching,
and multiline paste input handling.

Functions:
    extract_from_text: Extract emails, phones, URLs via regex
    extract_skills_from_text: Fuzzy-match text against ESCO taxonomy
    read_multiline_paste: Read stdin until double-Enter
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz, process
from rich.console import Console
from sqlalchemy.orm import Session

from career_os.models.esco import ESCOSkill

# ---------------------------------------------------------------------------
# Regex patterns for contact info extraction
# ---------------------------------------------------------------------------

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}")
URL_RE = re.compile(r"https?://[^\s<>\"']+")

# Fuzzy match threshold (lower than normalizer's 85 for broader recall during extraction)
SKILL_MATCH_THRESHOLD = 80.0

# T-02-02 mitigation: cap n-gram generation to first 500 words
MAX_WORDS_FOR_NGRAMS = 500


def extract_from_text(text: str) -> dict[str, list[str]]:
    """Extract structured contact data from pasted resume text.

    Args:
        text: Raw text (typically pasted resume content).

    Returns:
        Dict with keys "emails", "phones", "urls", each a list of strings.
    """
    return {
        "emails": EMAIL_RE.findall(text),
        "phones": PHONE_RE.findall(text),
        "urls": URL_RE.findall(text),
    }


def extract_skills_from_text(text: str, db: Session, top_n: int = 10) -> list[str]:
    """Find skill mentions in text by fuzzy-matching against ESCO taxonomy.

    Generates 1-3 word n-grams from the input text and fuzzy-matches each
    against ESCOSkill.preferred_label using rapidfuzz.

    Args:
        text: Raw text to scan for skill mentions.
        db: SQLAlchemy session for querying ESCO skills.
        top_n: Maximum number of matched skills to return.

    Returns:
        Sorted list of matched ESCO preferred labels, capped at top_n.
    """
    words = text.split()

    # T-02-02: cap input to prevent O(n^2) on massive text
    words = words[:MAX_WORDS_FOR_NGRAMS]

    # Generate 1-3 word n-grams as candidates
    candidates: set[str] = set()
    for n in range(1, 4):
        for i in range(len(words) - n + 1):
            candidates.add(" ".join(words[i : i + n]))

    if not candidates:
        return []

    # Load all ESCO labels
    all_skills = db.query(ESCOSkill.preferred_label).all()
    labels = [s.preferred_label for s in all_skills]

    if not labels:
        return []

    # Match each candidate against taxonomy
    matched: set[str] = set()
    for candidate in candidates:
        result = process.extractOne(
            candidate,
            labels,
            scorer=fuzz.WRatio,
            score_cutoff=SKILL_MATCH_THRESHOLD,
        )
        if result:
            matched.add(result[0])

    return sorted(matched)[:top_n]


def read_multiline_paste(console: Console) -> str:
    """Read multiline input from stdin, terminated by double-Enter.

    Prints a prompt instructing the user to paste text and press Enter twice
    when done. Handles EOF gracefully.

    Args:
        console: Rich Console for styled output.

    Returns:
        The joined and stripped text from all input lines.
    """
    console.print("[dim]Paste your resume text below (press Enter twice when done):[/dim]")
    lines: list[str] = []
    empty_count = 0
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            empty_count += 1
            if empty_count >= 2:
                break
            lines.append(line)
        else:
            empty_count = 0
            lines.append(line)
    return "\n".join(lines).strip()
