"""
Job scraper for TPM/Product/AI roles using python-jobspy.
Searches LinkedIn, Indeed, Glassdoor, and Google Jobs.

Usage:
    python tools/scraper.py
    python tools/scraper.py --keywords "AI Product Manager"
    python tools/scraper.py --location "Berlin, Germany" --hours 24
"""

import argparse
from datetime import datetime
from pathlib import Path

from jobspy import scrape_jobs

DEFAULT_KEYWORDS = [
    "Senior Technical Program Manager AI",
    "Technical Program Manager ML",
    "Technical Product Manager AI",
    "AI Program Lead",
    "Senior Product Manager AI developer tools",
    "Innovation Lead AI transformation",
    "Technical Program Manager remote",
]

# ---------------------------------------------------------------------------
# Job family keyword presets — map each scoring job family to discovery search
# terms so first-time users get relevant results without crafting queries.
#
# Keys match JOB_FAMILY_WEIGHTS in career_os.services.scoring.
# Values are lists of search strings that produce good signal on major boards.
# ---------------------------------------------------------------------------

JOB_FAMILY_KEYWORDS: dict[str, list[str]] = {
    # ── Technology ────────────────────────────────────────────────────────
    "TPM": [
        "Technical Program Manager",
        "Technical Program Manager AI",
        "Senior Technical Program Manager",
        "Staff Technical Program Manager",
        "Technical Program Manager remote",
    ],
    "SWE": [
        "Senior Software Engineer",
        "Staff Software Engineer",
        "Software Engineer backend",
        "Software Engineer full stack",
        "Senior Software Developer",
    ],
    "Product Engineer": [
        "Product Engineer",
        "Senior Product Engineer",
        "Staff Product Engineer",
        "Product Engineer AI",
        "Product Engineer full stack",
    ],
    "DevRel": [
        "Developer Advocate",
        "Developer Relations Engineer",
        "Developer Experience Engineer",
        "Senior Developer Advocate",
        "DevRel Engineer",
    ],
    "AI Program Lead": [
        "AI Program Lead",
        "AI Program Manager",
        "Head of AI Programs",
        "Senior AI Program Manager",
        "AI Transformation Lead",
    ],
    "Backend Engineer": [
        "Senior Backend Engineer",
        "Staff Backend Engineer",
        "Backend Engineer Python",
        "Backend Engineer Go",
        "Backend Developer senior",
    ],
    "Frontend Engineer": [
        "Senior Frontend Engineer",
        "Staff Frontend Engineer",
        "Frontend Engineer React",
        "Frontend Developer senior",
        "UI Engineer",
    ],
    "Full-Stack Developer": [
        "Senior Full Stack Engineer",
        "Full Stack Developer",
        "Staff Full Stack Engineer",
        "Full Stack Engineer React",
        "Full Stack Developer Python",
    ],
    "Mobile Developer (iOS)": [
        "Senior iOS Developer",
        "iOS Engineer",
        "Staff iOS Engineer",
        "Mobile Developer iOS",
        "Swift Developer senior",
    ],
    "Mobile Developer (Android)": [
        "Senior Android Developer",
        "Android Engineer",
        "Staff Android Engineer",
        "Mobile Developer Android",
        "Kotlin Developer senior",
    ],
    "DevOps Engineer": [
        "Senior DevOps Engineer",
        "Staff DevOps Engineer",
        "DevOps Engineer Kubernetes",
        "DevOps Engineer AWS",
        "Infrastructure Engineer",
    ],
    "Site Reliability Engineer (SRE)": [
        "Site Reliability Engineer",
        "Senior SRE",
        "Staff SRE",
        "SRE Engineer",
        "Reliability Engineer",
    ],
    "Platform Engineer": [
        "Senior Platform Engineer",
        "Staff Platform Engineer",
        "Platform Engineer Kubernetes",
        "Platform Engineer cloud",
        "Internal Platform Engineer",
    ],
    "Cloud Architect": [
        "Cloud Architect",
        "Senior Cloud Architect",
        "Cloud Solutions Architect",
        "Cloud Infrastructure Architect",
        "AWS Architect senior",
    ],
    "Solutions Architect": [
        "Solutions Architect",
        "Senior Solutions Architect",
        "Technical Solutions Architect",
        "Solutions Architect cloud",
        "Pre-Sales Solutions Architect",
    ],
    "Security Engineer": [
        "Senior Security Engineer",
        "Staff Security Engineer",
        "Application Security Engineer",
        "Cloud Security Engineer",
        "Security Engineer remote",
    ],
    "DevSecOps Engineer": [
        "DevSecOps Engineer",
        "Senior DevSecOps Engineer",
        "Security DevOps Engineer",
        "DevSecOps Architect",
        "DevSecOps Engineer cloud",
    ],
    "QA Engineer": [
        "Senior QA Engineer",
        "QA Engineer",
        "Quality Assurance Engineer",
        "QA Lead",
        "Test Engineer senior",
    ],
    "QA Automation Engineer": [
        "QA Automation Engineer",
        "Senior QA Automation Engineer",
        "Test Automation Engineer",
        "Automation Test Engineer",
        "SDET QA",
    ],
    "SDET": [
        "SDET",
        "Senior SDET",
        "Software Development Engineer in Test",
        "SDET Engineer",
        "Staff SDET",
    ],
    "Data Engineer": [
        "Senior Data Engineer",
        "Staff Data Engineer",
        "Data Engineer Python",
        "Data Engineer Spark",
        "Analytics Engineer",
    ],
    "ML Engineer": [
        "Senior ML Engineer",
        "Machine Learning Engineer",
        "Staff ML Engineer",
        "ML Engineer Python",
        "Applied ML Engineer",
    ],
    "MLOps Engineer": [
        "MLOps Engineer",
        "Senior MLOps Engineer",
        "ML Platform Engineer",
        "Machine Learning Operations Engineer",
        "MLOps Engineer remote",
    ],
    "AI Research Scientist": [
        "AI Research Scientist",
        "Senior Research Scientist AI",
        "Research Scientist Machine Learning",
        "Applied Research Scientist",
        "Staff Research Scientist",
    ],
    "Data Scientist": [
        "Senior Data Scientist",
        "Staff Data Scientist",
        "Data Scientist ML",
        "Applied Data Scientist",
        "Data Scientist Python",
    ],
    "Data Analyst": [
        "Senior Data Analyst",
        "Data Analyst",
        "Business Data Analyst",
        "Data Analyst SQL",
        "Analytics Analyst senior",
    ],
    "Business Intelligence Analyst": [
        "Business Intelligence Analyst",
        "Senior BI Analyst",
        "BI Developer",
        "Business Intelligence Developer",
        "BI Analyst senior",
    ],
    "Database Administrator": [
        "Database Administrator",
        "Senior DBA",
        "Database Engineer",
        "DBA PostgreSQL",
        "Database Administrator senior",
    ],
    "Network Engineer": [
        "Senior Network Engineer",
        "Network Engineer",
        "Network Architect",
        "Network Engineer Cisco",
        "Network Operations Engineer",
    ],
    "Systems Administrator": [
        "Senior Systems Administrator",
        "Systems Administrator",
        "Linux Systems Administrator",
        "Systems Engineer",
        "Infrastructure Administrator",
    ],
    "IT Support": [
        "IT Support Engineer",
        "Senior IT Support",
        "IT Support Specialist",
        "Desktop Support Engineer",
        "IT Help Desk senior",
    ],
    "Cybersecurity Analyst": [
        "Cybersecurity Analyst",
        "Senior Cybersecurity Analyst",
        "Information Security Analyst",
        "SOC Analyst",
        "Cyber Threat Analyst",
    ],
    "Penetration Tester": [
        "Penetration Tester",
        "Senior Penetration Tester",
        "Offensive Security Engineer",
        "Red Team Engineer",
        "Ethical Hacker",
    ],
    "Embedded Systems Engineer": [
        "Embedded Systems Engineer",
        "Senior Embedded Engineer",
        "Embedded Software Engineer",
        "Firmware Developer",
        "Embedded C Developer",
    ],
    "Firmware Engineer": [
        "Firmware Engineer",
        "Senior Firmware Engineer",
        "Embedded Firmware Developer",
        "Firmware Software Engineer",
        "IoT Firmware Engineer",
    ],
    "Game Developer": [
        "Game Developer",
        "Senior Game Developer",
        "Game Programmer",
        "Unity Developer",
        "Unreal Engine Developer",
    ],
    "Blockchain Developer": [
        "Blockchain Developer",
        "Senior Blockchain Engineer",
        "Smart Contract Developer",
        "Web3 Developer",
        "Solidity Developer",
    ],
    "Technical Writer (Tech)": [
        "Technical Writer",
        "Senior Technical Writer",
        "Technical Writer API",
        "Documentation Engineer",
        "Technical Content Writer",
    ],
    "Release Manager": [
        "Release Manager",
        "Senior Release Manager",
        "Release Engineer",
        "Build and Release Manager",
        "Configuration Manager",
    ],
    "Scrum Master": [
        "Scrum Master",
        "Senior Scrum Master",
        "Agile Coach",
        "Agile Scrum Master",
        "Scrum Master remote",
    ],
    "Engineering Manager": [
        "Engineering Manager",
        "Senior Engineering Manager",
        "Software Engineering Manager",
        "Engineering Manager backend",
        "Head of Engineering",
    ],
    "VP Engineering": [
        "VP Engineering",
        "Vice President Engineering",
        "VP of Engineering",
        "SVP Engineering",
        "Head of Engineering",
    ],
    "CTO": [
        "CTO",
        "Chief Technology Officer",
        "CTO startup",
        "VP Engineering CTO",
        "Fractional CTO",
    ],
    "Chief Architect": [
        "Chief Architect",
        "Principal Architect",
        "Enterprise Architect",
        "Chief Software Architect",
        "Distinguished Engineer",
    ],
    # ── Product & Design ──────────────────────────────────────────────────
    "Product Manager": [
        "Senior Product Manager",
        "Product Manager",
        "Staff Product Manager",
        "Product Manager AI",
        "Group Product Manager",
    ],
    "Product Owner": [
        "Product Owner",
        "Senior Product Owner",
        "Technical Product Owner",
        "Product Owner Agile",
        "Product Owner remote",
    ],
    "UX Designer": [
        "Senior UX Designer",
        "UX Designer",
        "UX/UI Designer",
        "Product Designer",
        "User Experience Designer",
    ],
    "UI Designer": [
        "UI Designer",
        "Senior UI Designer",
        "Visual Designer",
        "UI/UX Designer",
        "Interface Designer",
    ],
    "UX Researcher": [
        "UX Researcher",
        "Senior UX Researcher",
        "User Research Lead",
        "Design Researcher",
        "UX Research Manager",
    ],
    # ── Data & Analytics ──────────────────────────────────────────────────
    "Analytics Engineer": [
        "Analytics Engineer",
        "Senior Analytics Engineer",
        "Data Analytics Engineer",
        "Analytics Engineer dbt",
        "Analytics Engineer remote",
    ],
    # ── Leadership ────────────────────────────────────────────────────────
    "Director of Engineering": [
        "Director of Engineering",
        "Senior Director Engineering",
        "Director Software Engineering",
        "Director Engineering AI",
        "Engineering Director",
    ],
    "Head of Product": [
        "Head of Product",
        "VP Product",
        "Director of Product",
        "Head of Product Management",
        "VP Product Management",
    ],
    "Founding Engineer": [
        "Founding Engineer",
        "First Engineer startup",
        "Founding Software Engineer",
        "Founding Full Stack Engineer",
        "Early Stage Engineer",
    ],
}


def _normalize_role(role: str) -> str:
    """Normalize a role title for fuzzy matching against JOB_FAMILY_KEYWORDS keys."""
    return role.strip().lower()


def _match_job_family(role: str) -> str | None:
    """Match a target role string to a JOB_FAMILY_KEYWORDS key.

    Tries exact match, case-insensitive match, then substring containment.
    Returns the matching key or None.
    """
    normalized = role.strip()

    # Exact match
    if normalized in JOB_FAMILY_KEYWORDS:
        return normalized

    # Case-insensitive match
    lower = _normalize_role(role)
    for key in JOB_FAMILY_KEYWORDS:
        if key.lower() == lower:
            return key

    # Substring match (either direction)
    for key in JOB_FAMILY_KEYWORDS:
        if lower in key.lower() or key.lower() in lower:
            return key

    return None


def get_keywords_for_profile(
    target_roles: list[str] | None = None,
    job_family: str | None = None,
) -> list[str]:
    """Build a keyword list from a user's target roles or job family.

    Resolution order:
    1. If target_roles is provided, match each role to a job family preset
       and collect all keywords (deduplicated, order-preserved).
    2. Else if job_family is provided, look up that single family.
    3. Else fall back to DEFAULT_KEYWORDS.

    Args:
        target_roles: List of role titles from config/personal.yaml target_roles.
        job_family: Single job family string from the profile's job_family field.

    Returns:
        List of search keyword strings, deduplicated and order-preserved.
    """
    keywords: list[str] = []
    seen: set[str] = set()

    def _add(kw: str) -> None:
        lower = kw.lower()
        if lower not in seen:
            seen.add(lower)
            keywords.append(kw)

    if target_roles:
        for role in target_roles:
            matched_key = _match_job_family(role)
            if matched_key:
                for kw in JOB_FAMILY_KEYWORDS[matched_key]:
                    _add(kw)
            else:
                # Use the role title itself as a search keyword
                _add(role)
        if keywords:
            return keywords

    if job_family:
        matched_key = _match_job_family(job_family)
        if matched_key:
            return list(JOB_FAMILY_KEYWORDS[matched_key])

    return list(DEFAULT_KEYWORDS)


DEFAULT_SITES = ["linkedin", "indeed", "glassdoor", "google"]
DEFAULT_LOCATION = "Berlin, Germany"
DEFAULT_HOURS_OLD = 72
DEFAULT_RESULTS_PER_KEYWORD = 30


def scrape_all(
    keywords: list[str] | None = None,
    location: str = DEFAULT_LOCATION,
    hours_old: int = DEFAULT_HOURS_OLD,
    results_per_keyword: int = DEFAULT_RESULTS_PER_KEYWORD,
    sites: list[str] | None = None,
) -> "pd.DataFrame":
    import pandas as pd

    keywords = keywords or DEFAULT_KEYWORDS
    sites = sites or DEFAULT_SITES
    all_jobs = []

    for kw in keywords:
        print(f"Scraping: '{kw}' in {location}...")
        try:
            jobs = scrape_jobs(
                site_name=sites,
                search_term=kw,
                location=location,
                results_wanted=results_per_keyword,
                hours_old=hours_old,
                country_indeed="Germany",
            )
            jobs["search_keyword"] = kw
            all_jobs.append(jobs)
            print(f"  Found {len(jobs)} results")
        except Exception as e:
            print(f"  Error scraping '{kw}': {e}")

    if not all_jobs:
        print("No jobs found.")
        return pd.DataFrame()

    combined = pd.concat(all_jobs, ignore_index=True)
    combined = combined.drop_duplicates(subset=["title", "company", "location"], keep="first")
    print(f"\nTotal unique jobs: {len(combined)}")
    return combined


def main():
    parser = argparse.ArgumentParser(description="Scrape job listings")
    parser.add_argument("--keywords", nargs="+", help="Search keywords (default: predefined list)")
    parser.add_argument("--location", default=DEFAULT_LOCATION, help="Location to search")
    parser.add_argument("--hours", type=int, default=DEFAULT_HOURS_OLD, help="Max age in hours")
    parser.add_argument(
        "--results", type=int, default=DEFAULT_RESULTS_PER_KEYWORD, help="Results per keyword"
    )
    parser.add_argument("--sites", nargs="+", default=DEFAULT_SITES, help="Sites to scrape")
    args = parser.parse_args()

    jobs = scrape_all(
        keywords=args.keywords,
        location=args.location,
        hours_old=args.hours,
        results_per_keyword=args.results,
        sites=args.sites,
    )

    if jobs.empty:
        return

    output_dir = Path(__file__).parent.parent / "tracking"
    output_dir.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = output_dir / f"scraped_jobs_{date_str}.csv"
    jobs.to_csv(output_path, index=False)
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
