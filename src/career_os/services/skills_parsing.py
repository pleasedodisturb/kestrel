"""Skills parsing engine: extracts skills from CV, assessments, and profile docs.

Sources:
- cv/cv.yaml → technical, domain, tools skills with evidence from CV sections
- profile/cliftonstrengths.md → soft skills from CliftonStrengths assessment
- profile/personality-epp.md → soft skills from EPP assessment
- profile/cognitive-ccat.md → cognitive/technical skills from CCAT
- profile/workplace-insights.md → soft skills from Workplace Insights
- profile/*.md (narrative docs) → domain and soft skills from narratives
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ParsedSkill:
    """A skill extracted from a source document."""

    name: str
    category: str  # technical, domain, soft, tools
    proficiency: str  # beginner, intermediate, advanced, expert
    evidence_source: str  # cv.yaml, assessment:cliftonstrengths, profile, manual
    evidence_detail: str | None = None


# ---------------------------------------------------------------------------
# Proficiency helpers
# ---------------------------------------------------------------------------

PROFICIENCY_ORDER = ["beginner", "intermediate", "advanced", "expert"]


def _proficiency_from_source_count(count: int) -> str:
    """Derive proficiency from number of evidence sources.

    Multiple sources = higher proficiency:
    - 1 source → intermediate
    - 2 sources → advanced
    - 3+ sources → expert
    """
    if count >= 3:
        return "expert"
    if count >= 2:
        return "advanced"
    return "intermediate"


def _higher_proficiency(a: str, b: str) -> str:
    """Return the higher of two proficiency levels."""
    a_idx = PROFICIENCY_ORDER.index(a) if a in PROFICIENCY_ORDER else 0
    b_idx = PROFICIENCY_ORDER.index(b) if b in PROFICIENCY_ORDER else 0
    return PROFICIENCY_ORDER[max(a_idx, b_idx)]


# ---------------------------------------------------------------------------
# CV Parsing
# ---------------------------------------------------------------------------


def parse_cv_yaml(cv_path: Path) -> list[ParsedSkill]:
    """Parse cv/cv.yaml and extract skills from sections.

    Extracts from:
    - cv.sections.skills → direct skill listings with categories
    - cv.sections.experience → technical skills mentioned in highlights
    """
    if not cv_path.exists():
        return []

    with open(cv_path) as f:
        data = yaml.safe_load(f)

    if not data or "cv" not in data:
        return []

    cv = data["cv"]
    sections = cv.get("sections", {})
    skills: list[ParsedSkill] = []

    # ---- Parse explicit skills section ----
    skills_section = sections.get("skills", [])
    for skill_entry in skills_section:
        label = skill_entry.get("label", "")
        details = skill_entry.get("details", "")

        # Map CV skill labels to categories
        category = _map_cv_label_to_category(label)

        # Split details into individual skills (parenthesis-aware)
        individual_skills = _split_details_paren_aware(details)
        for skill_name in individual_skills:
            skills.append(
                ParsedSkill(
                    name=skill_name,
                    category=category,
                    proficiency="intermediate",
                    evidence_source="cv.yaml",
                    evidence_detail=f"CV skills section: {label}",
                )
            )

    # ---- Parse experience section for additional skills ----
    experience_section = sections.get("experience", [])
    experience_skills = _extract_skills_from_experience(experience_section)
    skills.extend(experience_skills)

    return skills


def _map_cv_label_to_category(label: str) -> str:
    """Map CV skill label to our category enum."""
    label_lower = label.lower()
    if any(kw in label_lower for kw in ["tool", "platform", "software"]):
        return "tools"
    if any(
        kw in label_lower
        for kw in [
            "communication",
            "teamwork",
            "leadership",
            "problem solving",
            "adaptability",
            "negotiation",
            "mentoring",
            "coaching",
            "collaboration",
            "interpersonal",
            "soft skill",
            "language",
        ]
    ):
        return "soft"
    if any(kw in label_lower for kw in ["program", "management"]):
        return "domain"
    if any(kw in label_lower for kw in ["ai", "ml", "technical", "engineer", "development"]):
        return "technical"
    return "domain"


def _split_details_paren_aware(details: str) -> list[str]:
    """Split a comma-separated details string, respecting parenthesised groups.

    For example:
        "English (fluent, CAE C1), Ukrainian (native)"
    →   ["English (fluent, CAE C1)", "Ukrainian (native)"]
    """
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in details:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth = max(depth - 1, 0)
            current.append(ch)
        elif ch == "," and depth == 0:
            token = "".join(current).strip()
            if token:
                parts.append(token)
            current = []
        else:
            current.append(ch)
    token = "".join(current).strip()
    if token:
        parts.append(token)
    return parts


# Mapping of keywords found in experience highlights to skills
_EXPERIENCE_SKILL_PATTERNS: dict[str, tuple[str, str]] = {
    r"\bAI\b": ("AI/ML", "technical"),
    r"\bML\b": ("Machine Learning", "technical"),
    r"\bLLM": ("LLM Integration", "technical"),
    r"\bASR\b": ("Speech Recognition (ASR)", "technical"),
    r"\bradar\b": ("Radar/Sensor R&D", "technical"),
    r"\bfirmware\b": ("Firmware Development", "technical"),
    r"\bAWS\b": ("AWS Infrastructure", "tools"),
    r"\bSalesforce\b": ("Salesforce", "tools"),
    r"\bCANBUS\b": ("CANBUS", "technical"),
    r"\bPython\b": ("Python", "technical"),
    r"\bSelenium\b": ("Selenium", "tools"),
    r"\bC\+\+\b": ("C++", "technical"),
    r"\bcross-functional\b": ("Cross-functional Leadership", "domain"),
    r"\bstakeholder": ("Stakeholder Management", "domain"),
    r"\bdeployment\b": ("Deployment Pipeline", "technical"),
    r"\bcompliance\b": ("Compliance Management", "domain"),
    r"\bAxure\b": ("Axure Prototyping", "tools"),
}


def _extract_skills_from_experience(experience: list[dict]) -> list[ParsedSkill]:
    """Extract implied skills from experience highlights."""
    skills: list[ParsedSkill] = []
    seen: set[str] = set()

    for job in experience:
        company = job.get("company", "")
        position = job.get("position", "")
        highlights = job.get("highlights", [])

        for highlight in highlights:
            for pattern, (skill_name, category) in _EXPERIENCE_SKILL_PATTERNS.items():
                if re.search(pattern, highlight, re.IGNORECASE) and skill_name not in seen:
                    seen.add(skill_name)
                    skills.append(
                        ParsedSkill(
                            name=skill_name,
                            category=category,
                            proficiency="advanced",
                            evidence_source="cv.yaml",
                            evidence_detail=(
                                f"Experience at {company} ({position}): {highlight[:120]}"
                            ),
                        )
                    )

    return skills


# ---------------------------------------------------------------------------
# Assessment Parsing
# ---------------------------------------------------------------------------


def _proficiency_from_rank(rank: int, total: int = 34) -> str | None:
    """Map a CliftonStrengths rank to a proficiency level.

    Returns None for ranks that should be skipped (bottom 14).
    """
    if rank <= 5:
        return "expert"
    if rank <= 10:
        return "advanced"
    if rank <= 20:
        return "intermediate"
    return None  # Skip bottom 14 (below average)


def parse_cliftonstrengths(file_path: Path) -> list[ParsedSkill]:
    """Parse CliftonStrengths assessment → soft skills with proficiency from rank."""
    if not file_path.exists():
        return []

    content = file_path.read_text()
    skills: list[ParsedSkill] = []

    # Parse the ranked themes table
    # Format: | Rank | Theme | Domain |
    table_pattern = re.compile(r"\|\s*(\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|")
    matches = table_pattern.findall(content)

    for rank_str, theme, domain in matches:
        try:
            rank = int(rank_str.strip())
        except ValueError:
            continue

        theme = theme.strip()
        domain = domain.strip()

        if not theme or theme == "Theme":  # skip header row
            continue

        proficiency = _proficiency_from_rank(rank)
        if proficiency is None:
            continue

        skills.append(
            ParsedSkill(
                name=f"{theme} ({domain})",
                category="soft",
                proficiency=proficiency,
                evidence_source="assessment:cliftonstrengths",
                evidence_detail=f"CliftonStrengths Rank #{rank}, Domain: {domain}",
            )
        )

    return skills


def parse_epp(file_path: Path) -> list[ParsedSkill]:
    """Parse Employee Personality Profile (EPP) → soft skills with proficiency from percentile."""
    if not file_path.exists():
        return []

    content = file_path.read_text()
    skills: list[ParsedSkill] = []

    # Parse trait scores table
    # Format: | Trait | Percentile | Category | Description |
    table_pattern = re.compile(
        r"\|\s*([^|]+)\s*\|\s*(\d+)(?:st|nd|rd|th)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|"
    )
    matches = table_pattern.findall(content)

    for trait, percentile_str, _category, description in matches:
        try:
            percentile = int(percentile_str.strip())
        except ValueError:
            continue

        trait = trait.strip()
        description = description.strip()

        if not trait or trait == "Trait":  # skip header
            continue

        proficiency = _proficiency_from_percentile(percentile)

        skills.append(
            ParsedSkill(
                name=trait,
                category="soft",
                proficiency=proficiency,
                evidence_source="assessment:epp",
                evidence_detail=f"EPP {percentile}th percentile: {description[:120]}",
            )
        )

    return skills


def _proficiency_from_percentile(percentile: int) -> str:
    """Map a percentile score to a proficiency level.

    >=80 → expert, >=60 → advanced, >=40 → intermediate, else → beginner.
    """
    if percentile >= 80:
        return "expert"
    if percentile >= 60:
        return "advanced"
    if percentile >= 40:
        return "intermediate"
    return "beginner"


_CCAT_SKILL_MAP: dict[str, tuple[str, str]] = {
    "Spatial Reasoning": ("Spatial Reasoning", "soft"),
    "Math & Logic": ("Analytical Thinking", "soft"),
    "Verbal": ("Verbal Reasoning", "soft"),
}


def _map_ccat_category(
    category_name: str, skill_map: dict[str, tuple[str, str]]
) -> tuple[str, str] | None:
    """Resolve a CCAT category name to (skill_name, skill_category) or None."""
    return skill_map.get(category_name)


def parse_ccat(file_path: Path) -> list[ParsedSkill]:
    """Parse Criteria Cognitive Aptitude Test (CCAT) → cognitive skills."""
    if not file_path.exists():
        return []

    content = file_path.read_text()
    skills: list[ParsedSkill] = []

    # Parse sub-category breakdown
    # Format: | Category | Percentile | Description |
    table_pattern = re.compile(
        r"\|\s*\*\*([^*]+)\*\*\s*\|\s*(\d+)(?:st|nd|rd|th)\s*\|\s*([^|]+)\s*\|"
    )
    matches = table_pattern.findall(content)

    for category_name, percentile_str, description in matches:
        try:
            percentile = int(percentile_str.strip())
        except ValueError:
            continue

        category_name = category_name.strip()
        description = description.strip()

        mapped = _map_ccat_category(category_name, _CCAT_SKILL_MAP)
        if mapped is None:
            continue
        skill_name, skill_category = mapped

        proficiency = _proficiency_from_percentile(percentile)

        skills.append(
            ParsedSkill(
                name=skill_name,
                category=skill_category,
                proficiency=proficiency,
                evidence_source="assessment:ccat",
                evidence_detail=f"CCAT {percentile}th percentile: {description[:120]}",
            )
        )

    # Also extract the overall score
    overall_match = re.search(r"\*\*Percentile\*\*\s*\|\s*(\d+)(?:st|nd|rd|th)", content)
    if overall_match:
        overall_pct = int(overall_match.group(1))
        # Overall score uses intermediate as floor (no beginner for overall aptitude)
        prof = _proficiency_from_percentile(overall_pct)
        if prof == "beginner":
            prof = "intermediate"

        skills.append(
            ParsedSkill(
                name="Cognitive Aptitude",
                category="soft",
                proficiency=prof,
                evidence_source="assessment:ccat",
                evidence_detail=f"CCAT Overall: {overall_pct}th percentile",
            )
        )

    return skills


_STRENGTH_KEYWORD_MAP: list[tuple[list[str], str]] = [
    (["assertive", "deferential"], "Adaptive Assertiveness"),
    (["sociable", "energetic"], "Social Energy"),
    (["curiosity", "experiment"], "Experimental Mindset"),
]


def _match_strength_keyword(line: str) -> str | None:
    """Return the skill name if any strength keywords match the line."""
    lower = line.lower()
    for keywords, skill_name in _STRENGTH_KEYWORD_MAP:
        if any(kw in lower for kw in keywords):
            return skill_name
    return None


def parse_workplace_insights(file_path: Path) -> list[ParsedSkill]:
    """Parse Workplace Insights report → soft skills from notable traits."""
    if not file_path.exists():
        return []

    content = file_path.read_text()
    skills: list[ParsedSkill] = []

    # Parse notable traits table
    # Format: | Trait | Description |
    notable_pattern = re.compile(r"\|\s*\*\*([^*]+)\*\*\s*\|\s*([^|]+)\s*\|")
    matches = notable_pattern.findall(content)

    trait_map = {
        "Cooperative": "Cooperation",
        "Extroverted": "Extroversion",
        "Intellectually Curious": "Intellectual Curiosity",
        "Self-Confident": "Self-Confidence",
    }

    for trait, description in matches:
        trait = trait.strip()
        description = description.strip()

        if trait in trait_map:
            skills.append(
                ParsedSkill(
                    name=trait_map[trait],
                    category="soft",
                    proficiency="advanced",
                    evidence_source="assessment:workplace-insights",
                    evidence_detail=f"Workplace Insights: {description[:120]}",
                )
            )

    # Parse strengths section
    strengths_section = re.search(r"## Strengths\n\n((?:- .+\n)+)", content)
    if strengths_section:
        for line in strengths_section.group(1).strip().split("\n"):
            line = line.strip("- ").strip()
            matched = _match_strength_keyword(line)
            if matched:
                skills.append(
                    ParsedSkill(
                        name=matched,
                        category="soft",
                        proficiency="advanced",
                        evidence_source="assessment:workplace-insights",
                        evidence_detail=f"Workplace Insights strength: {line[:120]}",
                    )
                )

    return skills


# ---------------------------------------------------------------------------
# Profile Doc Parsing
# ---------------------------------------------------------------------------

# Skills we look for in narrative documents
_NARRATIVE_SKILL_PATTERNS: dict[str, tuple[str, str]] = {
    # Domain skills
    r"stakeholder\s+management": ("Stakeholder Management", "domain"),
    r"cross-functional": ("Cross-functional Leadership", "domain"),
    r"change\s+management": ("Change Management", "domain"),
    r"risk\s+(?:mitigation|management|identification)": ("Risk Management", "domain"),
    r"roadmap\s+planning": ("Roadmap Planning", "domain"),
    r"AI[\s-]+(?:powered|augmented|driven)": ("AI Strategy", "domain"),
    r"program\s+management": ("Program Management", "domain"),
    r"technical\s+program": ("Technical Program Management", "domain"),
    r"product\s+management": ("Product Management", "domain"),
    r"agile|kanban|scrum": ("Agile/Kanban", "domain"),
    r"OKR": ("OKR Framework", "domain"),
    # Soft skills
    r"strategic\s+(?:thinking|vision|planning)": ("Strategic Thinking", "soft"),
    r"communication": ("Communication", "soft"),
    r"visionary\s+leader": ("Visionary Leadership", "soft"),
    r"innovation": ("Innovation", "soft"),
    r"problem[\s-]+solving": ("Problem Solving", "soft"),
    r"adaptab": ("Adaptability", "soft"),
    r"mentoring|coaching": ("Coaching & Mentoring", "soft"),
    r"negotiation": ("Negotiation", "soft"),
    # Technical skills
    r"\bPython\b": ("Python", "technical"),
    r"\bJavaScript\b|\bTypeScript\b": ("JavaScript/TypeScript", "technical"),
    r"\bSQL\b": ("SQL", "technical"),
    r"\bDocker\b": ("Docker", "technical"),
    r"\bKubernetes\b": ("Kubernetes", "technical"),
    r"\bCI/CD\b|continuous\s+(?:integration|delivery|deployment)": ("CI/CD", "technical"),
    r"\bautomation\b": ("Automation", "technical"),
    r"\bAPI\b(?:\s+design|\s+development|\s+integration)?": ("API Development", "technical"),
    r"\bmachine\s+learning\b|\bML\b": ("Machine Learning", "technical"),
    r"\bdata\s+(?:analysis|analytics|engineering|pipeline)": ("Data Engineering", "technical"),
    # Tools
    r"\bPipedrive\b": ("Pipedrive", "tools"),
    r"\bSalesforce\b": ("Salesforce", "tools"),
    r"\bNotion\b": ("Notion", "tools"),
    r"\bJira\b": ("Jira", "tools"),
    r"\bConfluence\b": ("Confluence", "tools"),
    r"\bLinear\b": ("Linear", "tools"),
    r"\bGitHub\b": ("GitHub", "tools"),
    r"\bSlack\b": ("Slack", "tools"),
    r"\bFigma\b": ("Figma", "tools"),
    r"\bTableau\b|\bLooker\b": ("BI Tools (Tableau/Looker)", "tools"),
    r"\bMiro\b": ("Miro", "tools"),
    r"\bAsana\b": ("Asana", "tools"),
}


@dataclass
class _NarrativeMatch:
    """Internal: track a narrative skill match with its evidence."""

    skill_name: str
    category: str
    source_file: str
    evidence_quote: str
    count: int = 1


def _extract_matches_from_file(
    file_path: Path,
    skill_patterns: dict[str, tuple[str, str]],
    matches: dict[str, _NarrativeMatch],
) -> None:
    """Scan a single file for skill patterns and update *matches* in place."""
    content = file_path.read_text()

    for pattern, (skill_name, category) in skill_patterns.items():
        regex_matches = list(re.finditer(pattern, content, re.IGNORECASE))
        if not regex_matches:
            continue

        # Get context around first match for evidence
        first_match = regex_matches[0]
        start = max(0, first_match.start() - 60)
        end = min(len(content), first_match.end() + 60)
        evidence_quote = content[start:end].strip()
        # Clean up the evidence (remove markdown)
        evidence_quote = re.sub(r"\s+", " ", evidence_quote)

        key = skill_name.lower()
        if key in matches:
            matches[key].count += 1
        else:
            matches[key] = _NarrativeMatch(
                skill_name=skill_name,
                category=category,
                source_file=file_path.name,
                evidence_quote=evidence_quote,
            )


def parse_profile_docs(profile_dir: Path) -> list[ParsedSkill]:
    """Parse profile narrative documents for skills.

    Reads .md files in the profile directory (excluding assessment files
    which are handled separately) and extracts domain and soft skills
    from narrative content.
    """
    if not profile_dir.exists():
        return []

    # Assessment files are parsed separately
    assessment_files = {
        "cliftonstrengths.md",
        "personality-epp.md",
        "cognitive-ccat.md",
        "workplace-insights.md",
    }

    matches: dict[str, _NarrativeMatch] = {}

    for md_file in sorted(profile_dir.glob("*.md")):
        if md_file.name in assessment_files:
            continue
        _extract_matches_from_file(md_file, _NARRATIVE_SKILL_PATTERNS, matches)

    skills: list[ParsedSkill] = []
    for match in matches.values():
        proficiency = _proficiency_from_source_count(match.count)
        skills.append(
            ParsedSkill(
                name=match.skill_name,
                category=match.category,
                proficiency=proficiency,
                evidence_source="profile",
                evidence_detail=f"Found in {match.source_file}: ...{match.evidence_quote}...",
            )
        )

    return skills


# ---------------------------------------------------------------------------
# Combined Ingestion
# ---------------------------------------------------------------------------


@dataclass
class IngestionResult:
    """Result of a full skills ingestion run."""

    skills: list[ParsedSkill] = field(default_factory=list)
    sources_processed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _ingest_source(
    result: IngestionResult,
    func: callable,
    args: tuple,
    label: str,
) -> None:
    """Call *func(*args)*, extending *result* on success or appending an error."""
    try:
        parsed = func(*args)
        result.skills.extend(parsed)
        if parsed:
            result.sources_processed.append(label)
    except Exception as e:
        result.errors.append(f"{label} parsing error: {e}")


def ingest_all_skills(
    cv_path: Path | None = None,
    profile_dir: Path | None = None,
    sources: list[str] | None = None,
) -> IngestionResult:
    """Run full skills ingestion from all configured sources.

    Args:
        cv_path: Path to cv.yaml file.
        profile_dir: Path to profile/ directory containing .md files.
        sources: List of sources to ingest. Default is all.
            Options: "cv", "assessments", "profile"

    Returns:
        IngestionResult with all extracted skills and metadata.
    """
    if sources is None:
        sources = ["cv", "assessments", "profile"]

    result = IngestionResult()

    if "cv" in sources and cv_path:
        _ingest_source(result, parse_cv_yaml, (cv_path,), "cv.yaml")

    if "assessments" in sources and profile_dir:
        assessment_parsers = [
            ("cliftonstrengths.md", parse_cliftonstrengths, "assessment:cliftonstrengths"),
            ("personality-epp.md", parse_epp, "assessment:epp"),
            ("cognitive-ccat.md", parse_ccat, "assessment:ccat"),
            ("workplace-insights.md", parse_workplace_insights, "assessment:workplace-insights"),
        ]
        for filename, parser, source_name in assessment_parsers:
            _ingest_source(result, parser, (profile_dir / filename,), source_name)

    if "profile" in sources and profile_dir:
        _ingest_source(result, parse_profile_docs, (profile_dir,), "profile")

    return result


def _evidence_sources_set(evidence_source: str) -> set[str]:
    """Parse a comma-separated evidence_source string into a set of sources."""
    return {s.strip() for s in evidence_source.split(",") if s.strip()}


def _upgrade_proficiency(
    existing_skill: ParsedSkill,
    new_skill: ParsedSkill,
    current_sources: set[str],
) -> None:
    """Upgrade *existing_skill* proficiency and evidence from *new_skill* in place.

    Handles both level-comparison and source-count-based upgrades.
    """
    existing_skill.proficiency = _higher_proficiency(
        existing_skill.proficiency, new_skill.proficiency
    )

    new_sources = _evidence_sources_set(new_skill.evidence_source)
    added_sources = new_sources - current_sources
    if not added_sources:
        return

    current_sources.update(added_sources)

    # Append evidence detail from different sources
    if new_skill.evidence_detail:
        if existing_skill.evidence_detail:
            existing_skill.evidence_detail += f" | Also: {new_skill.evidence_detail}"
        else:
            existing_skill.evidence_detail = new_skill.evidence_detail

    # Update evidence_source to include all sources
    existing_skill.evidence_source = ", ".join(sorted(current_sources))

    # Upgrade proficiency based on total source count
    source_prof = _proficiency_from_source_count(len(current_sources))
    existing_skill.proficiency = _higher_proficiency(existing_skill.proficiency, source_prof)


def merge_skills(existing: list[ParsedSkill], new: list[ParsedSkill]) -> list[ParsedSkill]:
    """Merge skill lists, upgrading proficiency when multiple sources provide evidence.

    Skills are matched by normalized name (case-insensitive).
    When a skill appears from multiple sources:
    - All evidence sources are tracked (comma-separated in evidence_source)
    - Proficiency is upgraded both by comparing levels AND by source count
    """
    merged: dict[str, ParsedSkill] = {}
    # Track distinct sources per skill for source-count-based proficiency upgrade
    sources_per_skill: dict[str, set[str]] = {}

    for skill in existing + new:
        key = skill.name.lower().strip()
        if key in merged:
            _upgrade_proficiency(merged[key], skill, sources_per_skill[key])
        else:
            merged[key] = ParsedSkill(
                name=skill.name,
                category=skill.category,
                proficiency=skill.proficiency,
                evidence_source=skill.evidence_source,
                evidence_detail=skill.evidence_detail,
            )
            sources_per_skill[key] = _evidence_sources_set(skill.evidence_source)

    return list(merged.values())
