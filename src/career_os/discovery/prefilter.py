"""Pre-filter for discovery pipeline — cheap regex/keyword elimination before AI scoring.

Eliminates ~60% of irrelevant jobs with 99.5% recall using lightweight regex and
keyword matching. Runs AFTER scraping/dedup but BEFORE expensive AI scoring.

Three aggressiveness levels:
- strict:   (title match OR 2+ skill keywords) AND NOT blacklisted industry
- moderate: title match OR 2+ skill keywords (no industry check)
- off:      disabled — all jobs pass through

Based on validated spike results in tools/spike_prefilter.py.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum

from career_os.services.geo.classifier import geo_eligibility
from career_os.services.geo.profile import GeoProfile

logger = logging.getLogger(__name__)


class PrefilterStrategy(StrEnum):
    """Prefilter aggressiveness level."""

    STRICT = "strict"
    MODERATE = "moderate"
    OFF = "off"


@dataclass
class PrefilterConfig:
    """Configuration for the discovery pre-filter.

    Attributes:
        strategy: Aggressiveness level (strict/moderate/off).
        title_keywords: Job title substrings that indicate relevance.
        skill_keywords: Skill terms to search for in descriptions.
        min_skill_matches: Minimum skill keyword matches to pass (default 2).
        blacklist_industries: Industries to reject in strict mode.
        geo_profile: Optional GeoProfile enabling the opt-in geo gate. When
            None (the default) the gate is a strict no-op and pre-filter
            behaviour is unchanged.
    """

    strategy: PrefilterStrategy = PrefilterStrategy.STRICT
    title_keywords: list[str] = field(default_factory=list)
    skill_keywords: list[str] = field(default_factory=list)
    min_skill_matches: int = 2
    blacklist_industries: list[str] = field(default_factory=list)
    geo_profile: GeoProfile | None = None


@dataclass
class PrefilterMetrics:
    """Metrics from a prefilter pass.

    Tracks how many jobs were evaluated, passed, and filtered by each signal.
    """

    total: int = 0
    passed: int = 0
    filtered: int = 0
    strategy: str = ""
    title_matches: int = 0
    skill_matches: int = 0
    industry_rejections: int = 0
    geo_rejections: int = 0

    @property
    def filter_rate(self) -> float:
        """Percentage of jobs filtered out."""
        return (self.filtered / self.total * 100) if self.total else 0.0


def _compile_patterns(keywords: list[str]) -> list[re.Pattern]:
    """Compile keyword list into case-insensitive regex patterns."""
    return [re.compile(re.escape(kw), re.IGNORECASE) for kw in keywords if kw]


def _title_matches(title: str, patterns: list[re.Pattern]) -> bool:
    """Check if job title matches any title keyword pattern."""
    return any(pat.search(title) for pat in patterns)


def _skill_density_passes(
    description: str,
    patterns: list[re.Pattern],
    min_matches: int,
) -> bool:
    """Check if description contains >= min_matches skill keywords."""
    matches = sum(1 for pat in patterns if pat.search(description))
    return matches >= min_matches


def _industry_blacklisted(industry: str, blacklist: set[str]) -> bool:
    """Check if job industry is in the blacklist."""
    return industry.strip().lower() in blacklist


def run_prefilter(
    jobs: list[dict],
    config: PrefilterConfig,
) -> tuple[list[dict], PrefilterMetrics]:
    """Apply pre-filter to a list of merged job dicts.

    Each job dict is expected to have at minimum:
    - "title": str
    - "description": str
    - "industry": str (optional, used only in strict mode)
    - "location" / "offices" / "remote" (optional, used only by the geo gate)

    The geo gate is OPT-IN: it runs only when ``config.geo_profile`` is set,
    and only in strict/moderate mode (``off`` stays a full bypass — no geo
    classification happens). When active it stores the verdict on each job as
    ``job["geo_class"]`` and rejects ONLY the explicit ``"foreign"`` class;
    ``unknown`` and the maybe classes always pass through — absence of geo
    signal must never bury a role.

    Returns:
        Tuple of (passed_jobs, metrics).
    """
    metrics = PrefilterMetrics(
        total=len(jobs),
        strategy=config.strategy.value,
    )

    if config.strategy == PrefilterStrategy.OFF:
        metrics.passed = len(jobs)
        logger.info(
            "Prefilter OFF: all %d jobs passed through",
            len(jobs),
        )
        return jobs, metrics

    title_patterns = _compile_patterns(config.title_keywords)
    skill_patterns = _compile_patterns(config.skill_keywords)
    blacklist = {ind.strip().lower() for ind in config.blacklist_industries}

    passed: list[dict] = []

    for job in jobs:
        title = job.get("title", "")
        description = job.get("description", "")
        industry = job.get("industry", "")

        # Opt-in geo gate: inert unless a profile is configured. Rejects ONLY
        # the explicit "foreign" class; "unknown" and the maybe classes pass.
        if config.geo_profile is not None:
            geo_class = geo_eligibility(
                job.get("location"),
                job.get("offices"),
                bool(job.get("remote")),
                job.get("title", ""),
                job.get("description", ""),
                profile=config.geo_profile,
            )
            job["geo_class"] = geo_class
            if geo_class == "foreign":
                metrics.geo_rejections += 1
                metrics.filtered += 1
                continue

        has_title = _title_matches(title, title_patterns)
        has_skills = _skill_density_passes(description, skill_patterns, config.min_skill_matches)
        is_blacklisted = _industry_blacklisted(industry, blacklist)

        if has_title:
            metrics.title_matches += 1
        if has_skills:
            metrics.skill_matches += 1
        if is_blacklisted:
            metrics.industry_rejections += 1

        # Decision logic depends on strategy
        if config.strategy == PrefilterStrategy.STRICT:
            # (title OR skills) AND NOT blacklisted
            has_signal = has_title or has_skills
            if has_signal and not is_blacklisted:
                passed.append(job)
            else:
                metrics.filtered += 1

        elif config.strategy == PrefilterStrategy.MODERATE:
            # title OR skills (no industry check)
            if has_title or has_skills:
                passed.append(job)
            else:
                metrics.filtered += 1

    metrics.passed = len(passed)

    logger.info(
        "Prefilter [%s]: %d/%d passed (%.1f%% filtered) "
        "| title_matches=%d skill_matches=%d industry_rejections=%d geo_rejections=%d",
        config.strategy.value,
        metrics.passed,
        metrics.total,
        metrics.filter_rate,
        metrics.title_matches,
        metrics.skill_matches,
        metrics.industry_rejections,
        metrics.geo_rejections,
    )

    return passed, metrics
