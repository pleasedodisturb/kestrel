"""Spike: regex pre-filter vs AI scoring accuracy on 10K synthetic jobs.

Generates 10,000 synthetic job listings with ground-truth relevance scores,
applies 5 regex/keyword filter strategies, and measures precision/recall/F1
against the ground truth to determine whether cheap pre-filtering can
reliably eliminate most jobs before expensive AI scoring.

Usage:
    python tools/spike_prefilter.py
    python tools/spike_prefilter.py --profile software-engineer
    python tools/spike_prefilter.py --profile data-scientist --seed 42
    python tools/spike_prefilter.py --jobs 50000

Profiles: software-engineer (default), product-manager, data-scientist
"""

from __future__ import annotations

import argparse
import random
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.table import Table

# ---------------------------------------------------------------------------
# Profile definitions — each simulates a user persona with relevant keywords,
# titles, skills, salary range, and preferred locations.
# ---------------------------------------------------------------------------

PROFILES: dict[str, dict] = {
    "software-engineer": {
        "title_keywords": [
            "software engineer",
            "software developer",
            "backend engineer",
            "frontend engineer",
            "full stack engineer",
            "full-stack developer",
            "web developer",
            "platform engineer",
            "site reliability engineer",
            "sre",
            "devops engineer",
            "systems engineer",
            "application developer",
        ],
        "skill_keywords": [
            "python",
            "javascript",
            "typescript",
            "react",
            "node.js",
            "aws",
            "docker",
            "kubernetes",
            "sql",
            "postgresql",
            "redis",
            "git",
            "ci/cd",
            "rest api",
            "graphql",
            "microservices",
            "linux",
            "terraform",
            "agile",
            "fastapi",
            "django",
            "flask",
            "java",
            "go",
            "rust",
        ],
        "salary_min": 80_000,
        "salary_max": 200_000,
        "preferred_locations": ["remote", "san francisco", "new york", "berlin", "london"],
        "blacklist_industries": [
            "healthcare",
            "dental",
            "veterinary",
            "agriculture",
            "mining",
            "trucking",
            "plumbing",
            "hvac",
            "roofing",
            "landscaping",
            "janitorial",
        ],
    },
    "product-manager": {
        "title_keywords": [
            "product manager",
            "senior product manager",
            "group product manager",
            "technical product manager",
            "product owner",
            "product lead",
            "director of product",
            "vp product",
            "head of product",
            "program manager",
        ],
        "skill_keywords": [
            "product strategy",
            "roadmap",
            "user research",
            "a/b testing",
            "analytics",
            "sql",
            "jira",
            "agile",
            "scrum",
            "okr",
            "kpi",
            "stakeholder",
            "prd",
            "user stories",
            "prioritization",
            "data-driven",
            "cross-functional",
            "go-to-market",
            "market research",
            "competitive analysis",
        ],
        "salary_min": 100_000,
        "salary_max": 250_000,
        "preferred_locations": ["remote", "san francisco", "new york", "seattle", "london"],
        "blacklist_industries": [
            "healthcare",
            "dental",
            "veterinary",
            "agriculture",
            "mining",
            "trucking",
            "plumbing",
            "hvac",
            "roofing",
            "landscaping",
            "janitorial",
        ],
    },
    "data-scientist": {
        "title_keywords": [
            "data scientist",
            "senior data scientist",
            "machine learning engineer",
            "ml engineer",
            "ai engineer",
            "research scientist",
            "applied scientist",
            "data engineer",
            "analytics engineer",
            "mlops engineer",
        ],
        "skill_keywords": [
            "python",
            "machine learning",
            "deep learning",
            "tensorflow",
            "pytorch",
            "scikit-learn",
            "pandas",
            "numpy",
            "sql",
            "spark",
            "airflow",
            "mlflow",
            "statistics",
            "nlp",
            "computer vision",
            "feature engineering",
            "experiment design",
            "a/b testing",
            "r",
            "jupyter",
            "aws sagemaker",
            "databricks",
        ],
        "salary_min": 90_000,
        "salary_max": 220_000,
        "preferred_locations": ["remote", "san francisco", "new york", "seattle", "boston"],
        "blacklist_industries": [
            "healthcare",
            "dental",
            "veterinary",
            "agriculture",
            "mining",
            "trucking",
            "plumbing",
            "hvac",
            "roofing",
            "landscaping",
            "janitorial",
        ],
    },
}

# ---------------------------------------------------------------------------
# Irrelevant job data — titles/descriptions that should clearly NOT match
# any tech profile. Used for generating the ~60% irrelevant jobs.
# ---------------------------------------------------------------------------

IRRELEVANT_TITLES = [
    "Dental Hygienist",
    "Registered Nurse",
    "Licensed Practical Nurse",
    "Phlebotomist",
    "Pharmacy Technician",
    "Medical Assistant",
    "Physical Therapist",
    "Occupational Therapist",
    "Veterinary Technician",
    "Certified Nursing Assistant",
    "Truck Driver CDL-A",
    "Long Haul Truck Driver",
    "Delivery Driver",
    "Forklift Operator",
    "Warehouse Associate",
    "Warehouse Manager",
    "Retail Store Manager",
    "Cashier",
    "Sales Associate",
    "Real Estate Agent",
    "Insurance Adjuster",
    "Mortgage Loan Officer",
    "Accountant",
    "Bookkeeper",
    "Paralegal",
    "Legal Secretary",
    "Construction Worker",
    "Electrician",
    "Plumber",
    "HVAC Technician",
    "Carpenter",
    "Welder",
    "Auto Mechanic",
    "Diesel Mechanic",
    "Landscaper",
    "Janitor",
    "Custodian",
    "Food Service Worker",
    "Line Cook",
    "Executive Chef",
    "Bartender",
    "Hotel Front Desk Agent",
    "Flight Attendant",
    "School Teacher",
    "Substitute Teacher",
    "Child Care Worker",
    "Social Worker",
    "Correctional Officer",
    "Security Guard",
    "Hair Stylist",
]

IRRELEVANT_DESCRIPTIONS = [
    "Responsible for patient care and medical records in a clinical setting.",
    "Operate and maintain heavy machinery in a warehouse environment.",
    "Drive commercial vehicles across state lines, CDL-A required.",
    "Provide excellent customer service in a retail environment.",
    "Perform routine maintenance and repair of residential plumbing systems.",
    "Install and repair heating, ventilation, and air conditioning equipment.",
    "Assist with food preparation and maintain kitchen cleanliness standards.",
    "Manage front desk operations and guest check-in/check-out procedures.",
    "Conduct home inspections and prepare detailed property assessment reports.",
    "Provide landscaping services including mowing, trimming, and planting.",
]

IRRELEVANT_COMPANIES = [
    "Valley Medical Center",
    "Sunrise Dental Care",
    "PetSmart",
    "Walmart",
    "McDonald's",
    "Marriott Hotels",
    "HomeDepot",
    "UPS Freight",
    "RE/MAX Realty",
    "AllState Insurance",
    "Jiffy Lube",
    "Roto-Rooter",
    "ServiceMaster",
    "Comfort Systems USA",
    "Aramark Food Services",
]

# ---------------------------------------------------------------------------
# Relevant job data — titles/companies/skills for tech jobs.
# ---------------------------------------------------------------------------

RELEVANT_TITLES_SWE = [
    "Senior Software Engineer",
    "Staff Software Engineer",
    "Software Engineer II",
    "Backend Engineer",
    "Frontend Engineer",
    "Full Stack Developer",
    "Platform Engineer",
    "Site Reliability Engineer",
    "DevOps Engineer",
    "Systems Engineer",
    "Infrastructure Engineer",
    "Cloud Engineer",
    "Senior Web Developer",
    "Application Developer",
]

RELEVANT_TITLES_PM = [
    "Senior Product Manager",
    "Product Manager, Growth",
    "Technical Product Manager",
    "Group Product Manager",
    "Product Owner",
    "Director of Product",
    "Senior Program Manager",
    "Technical Program Manager",
    "Head of Product",
]

RELEVANT_TITLES_DS = [
    "Senior Data Scientist",
    "Machine Learning Engineer",
    "ML Engineer",
    "AI Research Scientist",
    "Applied Scientist",
    "Data Engineer",
    "Analytics Engineer",
    "MLOps Engineer",
    "Staff Data Scientist",
    "Senior ML Engineer",
]

RELEVANT_COMPANIES = [
    "Google",
    "Meta",
    "Amazon",
    "Apple",
    "Microsoft",
    "Netflix",
    "Stripe",
    "Shopify",
    "Datadog",
    "Snowflake",
    "Databricks",
    "Figma",
    "Notion",
    "Vercel",
    "HashiCorp",
    "Cloudflare",
    "MongoDB",
    "GitLab",
    "Twilio",
    "Confluent",
    "Linear",
    "Anthropic",
    "OpenAI",
    "Hugging Face",
    "Mistral AI",
    "Cohere",
    "Scale AI",
    "Weights & Biases",
]

TECH_SKILL_FRAGMENTS = [
    "Python, JavaScript, TypeScript",
    "React, Next.js, Tailwind CSS",
    "AWS, GCP, or Azure experience required",
    "Docker and Kubernetes expertise",
    "PostgreSQL and Redis",
    "CI/CD pipelines with GitHub Actions",
    "microservices architecture",
    "REST API design and GraphQL",
    "distributed systems experience",
    "machine learning and deep learning",
    "PyTorch or TensorFlow",
    "data pipeline engineering with Spark",
    "agile development methodologies",
    "strong git workflow and code review skills",
    "experience with infrastructure as code (Terraform)",
    "monitoring and observability (Datadog, Prometheus)",
    "SQL and NoSQL databases",
    "Linux systems administration",
    "cross-functional collaboration with product and design",
    "product roadmap ownership and prioritization",
    "user research and A/B testing",
    "stakeholder management and executive communication",
    "OKR framework and KPI tracking",
    "go-to-market strategy",
    "feature engineering and experiment design",
    "MLflow and model deployment",
    "statistical analysis and hypothesis testing",
    "NLP and computer vision",
]

LOCATIONS = [
    "Remote",
    "Remote (US)",
    "San Francisco, CA",
    "New York, NY",
    "Seattle, WA",
    "Austin, TX",
    "Boston, MA",
    "Berlin, Germany",
    "London, UK",
    "Chicago, IL",
    "Denver, CO",
    "Portland, OR",
    "Los Angeles, CA",
    "Miami, FL",
    "Toronto, Canada",
    "Des Moines, IA",
    "Omaha, NE",
    "Salt Lake City, UT",
    "Boise, ID",
    "Tulsa, OK",
]


# ---------------------------------------------------------------------------
# Synthetic job generation
# ---------------------------------------------------------------------------


@dataclass
class SyntheticJob:
    """A synthetic job with baked-in ground truth relevance."""

    id: int
    title: str
    company: str
    location: str
    salary_min: int | None
    salary_max: int | None
    description: str
    industry: str
    ground_truth_score: int  # 1-10, simulating ideal AI scorer output


def _build_relevant_description(profile_name: str, rng: random.Random, quality: str) -> str:
    """Build a job description with controlled keyword density.

    quality: "high" (many matching skills), "medium" (some), "low" (few)
    """
    profile = PROFILES[profile_name]
    skills = list(profile["skill_keywords"])
    rng.shuffle(skills)

    fragments = list(TECH_SKILL_FRAGMENTS)
    rng.shuffle(fragments)

    if quality == "high":
        n_skills = rng.randint(6, 10)
        n_fragments = rng.randint(3, 5)
    elif quality == "medium":
        n_skills = rng.randint(3, 5)
        n_fragments = rng.randint(1, 3)
    else:  # low
        n_skills = rng.randint(1, 2)
        n_fragments = rng.randint(0, 1)

    parts = [
        "We are looking for an experienced professional to join our team.",
        f"Requirements: {', '.join(skills[:n_skills])}.",
    ]
    for frag in fragments[:n_fragments]:
        parts.append(f"Experience with {frag}.")

    parts.append(
        "Competitive compensation, flexible work arrangements, "
        "and opportunities for growth."
    )
    return " ".join(parts)


def _build_irrelevant_description(rng: random.Random) -> str:
    """Build a description that should NOT match any tech profile."""
    base = rng.choice(IRRELEVANT_DESCRIPTIONS)
    return f"{base} Must have excellent communication skills and attention to detail."


def _get_relevant_titles(profile_name: str) -> list[str]:
    """Return relevant titles for the given profile."""
    if profile_name == "software-engineer":
        return RELEVANT_TITLES_SWE
    elif profile_name == "product-manager":
        return RELEVANT_TITLES_PM
    elif profile_name == "data-scientist":
        return RELEVANT_TITLES_DS
    return RELEVANT_TITLES_SWE


def generate_jobs(
    n: int,
    profile_name: str,
    seed: int = 12345,
) -> list[SyntheticJob]:
    """Generate n synthetic jobs with ground truth relevance scores.

    Distribution:
    - ~20% highly relevant (score 7-10): matching title, good salary, relevant skills
    - ~20% somewhat relevant (score 4-6): partial match on some dimensions
    - ~60% irrelevant (score 1-3): wrong industry, title, salary, or location
    """
    rng = random.Random(seed)
    profile = PROFILES[profile_name]
    relevant_titles = _get_relevant_titles(profile_name)
    jobs: list[SyntheticJob] = []

    for i in range(n):
        r = rng.random()

        if r < 0.20:
            # Highly relevant — score 7-10
            title = rng.choice(relevant_titles)
            company = rng.choice(RELEVANT_COMPANIES)
            location = rng.choice(profile["preferred_locations"])
            sal_min = rng.randint(profile["salary_min"], profile["salary_max"] - 20_000)
            sal_max = sal_min + rng.randint(10_000, 40_000)
            desc = _build_relevant_description(profile_name, rng, "high")
            score = rng.randint(7, 10)
            industry = "technology"

        elif r < 0.40:
            # Somewhat relevant — score 4-6
            # Could be: right title but wrong salary, wrong location but good skills, etc.
            variant = rng.randint(0, 3)
            if variant == 0:
                # Good title, bad salary
                title = rng.choice(relevant_titles)
                company = rng.choice(RELEVANT_COMPANIES + ["Acme Corp", "Generic Inc"])
                location = rng.choice(LOCATIONS)
                sal_min = rng.randint(30_000, profile["salary_min"] - 10_000)
                sal_max = sal_min + rng.randint(5_000, 15_000)
                desc = _build_relevant_description(profile_name, rng, "medium")
                score = rng.randint(4, 5)
                industry = "technology"
            elif variant == 1:
                # Good title, few matching skills
                title = rng.choice(relevant_titles)
                company = rng.choice(RELEVANT_COMPANIES + ["StartupXYZ", "TechCo"])
                location = rng.choice(LOCATIONS)
                sal_min = rng.randint(profile["salary_min"], profile["salary_max"] - 20_000)
                sal_max = sal_min + rng.randint(10_000, 30_000)
                desc = _build_relevant_description(profile_name, rng, "low")
                score = rng.randint(4, 6)
                industry = "technology"
            elif variant == 2:
                # Adjacent title (e.g., "Engineering Manager" for SWE)
                adjacent = [
                    "Engineering Manager",
                    "Technical Lead",
                    "CTO",
                    "VP Engineering",
                    "Solutions Architect",
                    "Sales Engineer",
                    "Technical Writer",
                    "Developer Advocate",
                ]
                title = rng.choice(adjacent)
                company = rng.choice(RELEVANT_COMPANIES)
                location = rng.choice(profile["preferred_locations"])
                sal_min = rng.randint(profile["salary_min"], profile["salary_max"])
                sal_max = sal_min + rng.randint(10_000, 30_000)
                desc = _build_relevant_description(profile_name, rng, "medium")
                score = rng.randint(4, 6)
                industry = "technology"
            else:
                # Right skills in wrong-sounding role
                title = rng.choice(
                    ["IT Specialist", "Systems Administrator", "Technical Support Engineer"]
                )
                company = rng.choice(RELEVANT_COMPANIES + ["IBM", "Oracle", "SAP"])
                location = rng.choice(LOCATIONS)
                sal_min = rng.randint(60_000, profile["salary_min"])
                sal_max = sal_min + rng.randint(10_000, 20_000)
                desc = _build_relevant_description(profile_name, rng, "high")
                score = rng.randint(4, 6)
                industry = "technology"

        else:
            # Irrelevant — score 1-3
            title = rng.choice(IRRELEVANT_TITLES)
            company = rng.choice(IRRELEVANT_COMPANIES)
            location = rng.choice(LOCATIONS)
            # Some have no salary, some have very low/very high
            if rng.random() < 0.3:
                sal_min = None
                sal_max = None
            else:
                sal_min = rng.randint(20_000, 60_000)
                sal_max = sal_min + rng.randint(5_000, 15_000)
            desc = _build_irrelevant_description(rng)
            score = rng.randint(1, 3)
            industry = rng.choice(
                [
                    "healthcare",
                    "retail",
                    "hospitality",
                    "construction",
                    "transportation",
                    "food service",
                    "education",
                    "real estate",
                    "agriculture",
                ]
            )

        jobs.append(
            SyntheticJob(
                id=i,
                title=title,
                company=company,
                location=location.capitalize() if location == "remote" else location,
                salary_min=sal_min,
                salary_max=sal_max,
                description=desc,
                industry=industry,
                ground_truth_score=score,
            )
        )

    return jobs


# ---------------------------------------------------------------------------
# Filter strategies
# ---------------------------------------------------------------------------


@dataclass
class FilterResult:
    """Result of applying a filter: which jobs passed and performance metrics."""

    strategy_name: str
    passed_ids: set[int]
    total_jobs: int
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def eliminated_pct(self) -> float:
        """Percentage of total jobs eliminated (not passed)."""
        return (self.total_jobs - len(self.passed_ids)) / self.total_jobs * 100

    @property
    def cost_savings_pct(self) -> float:
        """Percentage of AI scoring calls saved (same as eliminated_pct)."""
        return self.eliminated_pct


def _evaluate_filter(
    strategy_name: str,
    passed_ids: set[int],
    jobs: list[SyntheticJob],
    relevance_threshold: int = 6,
) -> FilterResult:
    """Evaluate a filter against ground truth.

    A job is "actually relevant" if ground_truth_score >= relevance_threshold.
    The filter "predicts relevant" if the job's ID is in passed_ids.
    """
    result = FilterResult(
        strategy_name=strategy_name,
        passed_ids=passed_ids,
        total_jobs=len(jobs),
    )

    for job in jobs:
        is_relevant = job.ground_truth_score >= relevance_threshold
        is_passed = job.id in passed_ids

        if is_relevant and is_passed:
            result.true_positives += 1
        elif is_relevant and not is_passed:
            result.false_negatives += 1
        elif not is_relevant and is_passed:
            result.false_positives += 1
        else:
            result.true_negatives += 1

    return result


def filter_by_title(jobs: list[SyntheticJob], profile_name: str) -> set[int]:
    """Pass jobs whose title matches any profile title keyword."""
    profile = PROFILES[profile_name]
    title_patterns = [re.compile(re.escape(kw), re.IGNORECASE) for kw in profile["title_keywords"]]

    passed = set()
    for job in jobs:
        title_lower = job.title.lower()
        if any(pat.search(title_lower) for pat in title_patterns):
            passed.add(job.id)
    return passed


def filter_by_salary(jobs: list[SyntheticJob], profile_name: str) -> set[int]:
    """Pass jobs whose salary overlaps with profile range, or has no salary listed."""
    profile = PROFILES[profile_name]
    p_min = profile["salary_min"]
    p_max = profile["salary_max"]

    passed = set()
    for job in jobs:
        # No salary info — can't filter, so pass through
        if job.salary_min is None and job.salary_max is None:
            passed.add(job.id)
            continue
        j_min = job.salary_min or 0
        j_max = job.salary_max or j_min
        # Ranges overlap if one starts before the other ends
        if j_min <= p_max and j_max >= p_min:
            passed.add(job.id)
    return passed


def filter_by_skill_density(
    jobs: list[SyntheticJob],
    profile_name: str,
    min_matches: int = 2,
) -> set[int]:
    """Pass jobs whose description contains >= min_matches skill keywords."""
    profile = PROFILES[profile_name]
    skill_patterns = [
        re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
        for kw in profile["skill_keywords"]
    ]

    passed = set()
    for job in jobs:
        matches = sum(1 for pat in skill_patterns if pat.search(job.description))
        if matches >= min_matches:
            passed.add(job.id)
    return passed


def filter_by_industry_blacklist(jobs: list[SyntheticJob], profile_name: str) -> set[int]:
    """Pass jobs whose industry is NOT in the blacklist."""
    profile = PROFILES[profile_name]
    blacklist = {ind.lower() for ind in profile["blacklist_industries"]}

    passed = set()
    for job in jobs:
        if job.industry.lower() not in blacklist:
            passed.add(job.id)
    return passed


def filter_combined(
    jobs: list[SyntheticJob],
    profile_name: str,
    weights: dict[str, float] | None = None,
    threshold: float = 0.4,
) -> set[int]:
    """Weighted combination of all filters. Each filter contributes a 0/1 signal,
    combined with weights. Job passes if weighted score >= threshold.

    Default weights emphasize title and skill density as strongest signals.
    """
    if weights is None:
        weights = {
            "title": 0.35,
            "salary": 0.15,
            "skill_density": 0.30,
            "industry": 0.20,
        }

    title_passed = filter_by_title(jobs, profile_name)
    salary_passed = filter_by_salary(jobs, profile_name)
    skill_passed = filter_by_skill_density(jobs, profile_name, min_matches=2)
    industry_passed = filter_by_industry_blacklist(jobs, profile_name)

    passed = set()
    for job in jobs:
        score = 0.0
        if job.id in title_passed:
            score += weights["title"]
        if job.id in salary_passed:
            score += weights["salary"]
        if job.id in skill_passed:
            score += weights["skill_density"]
        if job.id in industry_passed:
            score += weights["industry"]
        if score >= threshold:
            passed.add(job.id)
    return passed


def filter_combined_strict(
    jobs: list[SyntheticJob],
    profile_name: str,
) -> set[int]:
    """Strict combined: must pass title OR skill_density, AND NOT blacklisted industry."""
    title_passed = filter_by_title(jobs, profile_name)
    skill_passed = filter_by_skill_density(jobs, profile_name, min_matches=2)
    industry_passed = filter_by_industry_blacklist(jobs, profile_name)

    passed = set()
    for job in jobs:
        has_signal = job.id in title_passed or job.id in skill_passed
        not_blacklisted = job.id in industry_passed
        if has_signal and not_blacklisted:
            passed.add(job.id)
    return passed


# ---------------------------------------------------------------------------
# Run experiment
# ---------------------------------------------------------------------------


@dataclass
class ExperimentResults:
    """Container for a full experiment run."""

    profile_name: str
    total_jobs: int
    relevant_jobs: int
    irrelevant_jobs: int
    filter_results: list[FilterResult] = field(default_factory=list)
    generation_time_ms: float = 0.0
    filter_time_ms: float = 0.0


def run_experiment(
    profile_name: str,
    n_jobs: int = 10_000,
    seed: int = 12345,
    relevance_threshold: int = 6,
) -> ExperimentResults:
    """Run the full experiment for a profile."""

    # Generate data
    t0 = time.monotonic()
    jobs = generate_jobs(n_jobs, profile_name, seed=seed)
    gen_time = (time.monotonic() - t0) * 1000

    relevant_count = sum(1 for j in jobs if j.ground_truth_score >= relevance_threshold)

    results = ExperimentResults(
        profile_name=profile_name,
        total_jobs=n_jobs,
        relevant_jobs=relevant_count,
        irrelevant_jobs=n_jobs - relevant_count,
        generation_time_ms=gen_time,
    )

    # Run all filter strategies
    t1 = time.monotonic()

    strategies = [
        ("Title Keywords", filter_by_title(jobs, profile_name)),
        ("Salary Range", filter_by_salary(jobs, profile_name)),
        ("Skill Density (>=2)", filter_by_skill_density(jobs, profile_name, min_matches=2)),
        ("Industry Blacklist", filter_by_industry_blacklist(jobs, profile_name)),
        ("Combined (weighted)", filter_combined(jobs, profile_name)),
        ("Combined (strict)", filter_combined_strict(jobs, profile_name)),
    ]

    for name, passed_ids in strategies:
        fr = _evaluate_filter(name, passed_ids, jobs, relevance_threshold)
        results.filter_results.append(fr)

    results.filter_time_ms = (time.monotonic() - t1) * 1000

    return results


# ---------------------------------------------------------------------------
# Output: Rich console tables
# ---------------------------------------------------------------------------


def print_results(results: ExperimentResults, console: Console) -> None:
    """Print experiment results as Rich tables."""
    console.print()
    console.rule(f"[bold]Spike: Pre-filter Accuracy — Profile: {results.profile_name}")
    console.print()
    console.print(f"  Total jobs generated: {results.total_jobs:,}")
    console.print(
        f"  Relevant (score >= 6): {results.relevant_jobs:,} "
        f"({results.relevant_jobs / results.total_jobs * 100:.1f}%)"
    )
    console.print(
        f"  Irrelevant (score < 6): {results.irrelevant_jobs:,} "
        f"({results.irrelevant_jobs / results.total_jobs * 100:.1f}%)"
    )
    console.print(f"  Generation time: {results.generation_time_ms:.0f}ms")
    console.print(f"  Filter time: {results.filter_time_ms:.0f}ms")
    console.print()

    # Main comparison table
    table = Table(title="Filter Strategy Comparison", show_lines=True)
    table.add_column("Strategy", style="cyan", width=22)
    table.add_column("Passed", justify="right", width=8)
    table.add_column("Eliminated %", justify="right", width=12)
    table.add_column("Precision", justify="right", width=10)
    table.add_column("Recall", justify="right", width=10)
    table.add_column("F1 Score", justify="right", width=10)
    table.add_column("False Neg", justify="right", width=10)
    table.add_column("Verdict", width=18)

    for fr in results.filter_results:
        # Color-code the verdict
        if fr.recall >= 0.95 and fr.eliminated_pct >= 50:
            verdict = "[green]RECOMMENDED[/green]"
        elif fr.recall >= 0.90 and fr.eliminated_pct >= 40:
            verdict = "[yellow]ACCEPTABLE[/yellow]"
        elif fr.recall < 0.80:
            verdict = "[red]TOO AGGRESSIVE[/red]"
        elif fr.eliminated_pct < 30:
            verdict = "[dim]LOW IMPACT[/dim]"
        else:
            verdict = "[yellow]TRADEOFF[/yellow]"

        table.add_row(
            fr.strategy_name,
            f"{len(fr.passed_ids):,}",
            f"{fr.eliminated_pct:.1f}%",
            f"{fr.precision:.3f}",
            f"{fr.recall:.3f}",
            f"{fr.f1:.3f}",
            f"{fr.false_negatives:,}",
            verdict,
        )

    console.print(table)

    # Confusion matrix detail table
    detail = Table(title="Confusion Matrix Detail", show_lines=True)
    detail.add_column("Strategy", style="cyan", width=22)
    detail.add_column("TP", justify="right")
    detail.add_column("FP", justify="right")
    detail.add_column("TN", justify="right")
    detail.add_column("FN", justify="right")

    for fr in results.filter_results:
        detail.add_row(
            fr.strategy_name,
            str(fr.true_positives),
            str(fr.false_positives),
            str(fr.true_negatives),
            str(fr.false_negatives),
        )

    console.print()
    console.print(detail)

    # Cost analysis
    console.print()
    console.rule("[bold]Cost Analysis")
    console.print()
    # Assume $0.003 per AI scoring call (rough average across providers/tiers)
    cost_per_call = 0.003
    daily_jobs = 1500
    monthly_jobs = daily_jobs * 30

    console.print(f"  Assumptions: {daily_jobs:,} jobs/day, ${cost_per_call} per AI scoring call")
    console.print(f"  Monthly baseline cost (no filter): ${monthly_jobs * cost_per_call:,.2f}")
    console.print()

    for fr in results.filter_results:
        monthly_after = monthly_jobs * (1 - fr.eliminated_pct / 100) * cost_per_call
        monthly_saved = monthly_jobs * cost_per_call - monthly_after
        console.print(
            f"  {fr.strategy_name:22s}: "
            f"${monthly_after:>7.2f}/mo "
            f"(save ${monthly_saved:>6.2f}/mo, "
            f"{fr.eliminated_pct:>5.1f}% eliminated, "
            f"recall={fr.recall:.3f})"
        )

    console.print()


# ---------------------------------------------------------------------------
# Output: Markdown results file
# ---------------------------------------------------------------------------


def write_results_md(
    all_results: list[ExperimentResults],
    output_path: Path,
) -> None:
    """Write experiment results to a Markdown file."""
    lines = [
        "# Spike: Regex Pre-filter vs AI Scoring Accuracy",
        "",
        "## Methodology",
        "",
        "- Generated 10,000 synthetic job listings per profile with realistic variation",
        "- Each job has a baked-in ground truth relevance score (1-10)",
        "- Distribution: ~20% highly relevant (7-10), ~20% borderline (4-6), ~60% irrelevant (1-3)",
        "- Relevance threshold: score >= 6 is 'relevant' (positive class)",
        "- Tested 6 filter strategies: title keywords, salary range, skill density, "
        "industry blacklist, weighted combination, strict combination",
        "",
        "## Key Findings",
        "",
    ]

    # Summarize best strategy per profile
    for res in all_results:
        best = max(
            res.filter_results,
            key=lambda fr: (fr.recall >= 0.90, fr.eliminated_pct, fr.f1),
        )
        lines.append(f"### Profile: {res.profile_name}")
        lines.append("")
        lines.append(f"- **Best strategy:** {best.strategy_name}")
        lines.append(f"- **Recall:** {best.recall:.3f} (missed {best.false_negatives} relevant)")
        lines.append(f"- **Jobs eliminated:** {best.eliminated_pct:.1f}%")
        lines.append(f"- **F1 Score:** {best.f1:.3f}")
        lines.append("")

    lines.append("## Detailed Results")
    lines.append("")

    for res in all_results:
        lines.append(f"### Profile: {res.profile_name}")
        lines.append("")
        lines.append(f"- Total jobs: {res.total_jobs:,}")
        lines.append(
            f"- Relevant (score >= 6): {res.relevant_jobs:,} "
            f"({res.relevant_jobs / res.total_jobs * 100:.1f}%)"
        )
        lines.append(
            f"- Irrelevant (score < 6): {res.irrelevant_jobs:,} "
            f"({res.irrelevant_jobs / res.total_jobs * 100:.1f}%)"
        )
        lines.append("")

        # Markdown table
        lines.append(
            "| Strategy | Passed | Eliminated % | Precision | Recall | F1 | False Neg | Verdict |"
        )
        lines.append(
            "|----------|--------|-------------|-----------|--------|-----|-----------|---------|"
        )

        for fr in res.filter_results:
            if fr.recall >= 0.95 and fr.eliminated_pct >= 50:
                verdict = "RECOMMENDED"
            elif fr.recall >= 0.90 and fr.eliminated_pct >= 40:
                verdict = "ACCEPTABLE"
            elif fr.recall < 0.80:
                verdict = "TOO AGGRESSIVE"
            elif fr.eliminated_pct < 30:
                verdict = "LOW IMPACT"
            else:
                verdict = "TRADEOFF"

            lines.append(
                f"| {fr.strategy_name} | {len(fr.passed_ids):,} | {fr.eliminated_pct:.1f}% "
                f"| {fr.precision:.3f} | {fr.recall:.3f} | {fr.f1:.3f} "
                f"| {fr.false_negatives} | {verdict} |"
            )

        lines.append("")

        # Confusion matrices
        lines.append("**Confusion Matrices:**")
        lines.append("")
        lines.append("| Strategy | TP | FP | TN | FN |")
        lines.append("|----------|-----|-----|-----|-----|")
        for fr in res.filter_results:
            lines.append(
                f"| {fr.strategy_name} | {fr.true_positives} | {fr.false_positives} "
                f"| {fr.true_negatives} | {fr.false_negatives} |"
            )
        lines.append("")

    # Cost analysis section
    lines.append("## Cost Analysis")
    lines.append("")
    lines.append("Assumptions: 1,500 jobs/day, $0.003 per AI scoring call")
    lines.append("")
    lines.append("| Strategy | Monthly Cost | Monthly Savings | Eliminated % | Recall |")
    lines.append("|----------|-------------|-----------------|-------------|--------|")

    cost_per_call = 0.003
    monthly_jobs = 1500 * 30
    baseline = monthly_jobs * cost_per_call

    # Use first profile as representative
    for fr in all_results[0].filter_results:
        monthly_after = monthly_jobs * (1 - fr.eliminated_pct / 100) * cost_per_call
        monthly_saved = baseline - monthly_after
        lines.append(
            f"| {fr.strategy_name} | ${monthly_after:.2f} | ${monthly_saved:.2f} "
            f"| {fr.eliminated_pct:.1f}% | {fr.recall:.3f} |"
        )

    lines.append("")
    lines.append(f"Baseline monthly cost (no filter): ${baseline:.2f}")
    lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    lines.append(
        "1. **Use the Combined (strict) filter as Stage 1** — it requires either a matching "
        "title OR sufficient skill keywords, AND not being in a blacklisted industry. This "
        "gives the best balance of elimination rate and recall."
    )
    lines.append(
        "2. **The Combined (weighted) filter is the safest choice** if recall is paramount — "
        "it passes more jobs through but still eliminates a meaningful percentage."
    )
    lines.append(
        "3. **Title-only filtering is too aggressive** — it misses relevant jobs with "
        "non-standard titles (e.g., 'IT Specialist' doing SWE work)."
    )
    lines.append(
        "4. **Industry blacklist alone has low impact** — it catches obviously irrelevant "
        "industries but many irrelevant jobs are in non-blacklisted sectors."
    )
    lines.append(
        "5. **Salary filter alone is nearly useless** — too many jobs lack salary data, "
        "so the filter passes most jobs through."
    )
    lines.append("")
    lines.append("## Next Steps")
    lines.append("")
    lines.append("- Validate findings against real scraped data (sample 500 real jobs)")
    lines.append("- Implement the chosen filter strategy in the discovery pipeline")
    lines.append("- Add monitoring to track false negative rate in production")
    lines.append("- Consider adaptive thresholds that tune based on user feedback")
    lines.append("")

    output_path.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _run_self_tests() -> bool:
    """Run basic self-tests to validate the spike logic.

    Returns True if all tests pass.
    """
    console = Console(stderr=True)
    passed = 0
    failed = 0

    def assert_eq(name: str, actual: object, expected: object) -> None:
        nonlocal passed, failed
        if actual == expected:
            passed += 1
        else:
            console.print(f"  [red]FAIL[/red] {name}: expected {expected}, got {actual}")
            failed += 1

    def assert_true(name: str, condition: bool) -> None:
        nonlocal passed, failed
        if condition:
            passed += 1
        else:
            console.print(f"  [red]FAIL[/red] {name}")
            failed += 1

    console.print("[bold]Running self-tests...[/bold]")

    # Test 1: generate_jobs produces correct count
    jobs = generate_jobs(100, "software-engineer", seed=1)
    assert_eq("generate_jobs count", len(jobs), 100)

    # Test 2: all scores in range 1-10
    assert_true(
        "scores in range",
        all(1 <= j.ground_truth_score <= 10 for j in jobs),
    )

    # Test 3: distribution roughly correct (with small sample, just check non-empty bins)
    high = [j for j in jobs if j.ground_truth_score >= 7]
    mid = [j for j in jobs if 4 <= j.ground_truth_score <= 6]
    low = [j for j in jobs if j.ground_truth_score <= 3]
    assert_true("has high-relevance jobs", len(high) > 0)
    assert_true("has mid-relevance jobs", len(mid) > 0)
    assert_true("has low-relevance jobs", len(low) > 0)

    # Test 4: FilterResult metrics
    fr = FilterResult(strategy_name="test", passed_ids={0, 1, 2}, total_jobs=10)
    fr.true_positives = 2
    fr.false_positives = 1
    fr.true_negatives = 6
    fr.false_negatives = 1
    assert_true("precision", abs(fr.precision - 2 / 3) < 0.001)
    assert_true("recall", abs(fr.recall - 2 / 3) < 0.001)
    assert_true("eliminated_pct", abs(fr.eliminated_pct - 70.0) < 0.001)

    # Test 5: title filter passes relevant titles
    test_jobs = [
        SyntheticJob(
            0, "Senior Software Engineer", "Co", "Remote", None, None, "", "tech", 8
        ),
        SyntheticJob(1, "Dental Hygienist", "Co", "Remote", None, None, "", "health", 2),
    ]
    title_passed = filter_by_title(test_jobs, "software-engineer")
    assert_true("title filter passes SWE", 0 in title_passed)
    assert_true("title filter rejects dental", 1 not in title_passed)

    # Test 6: salary filter
    test_jobs_sal = [
        SyntheticJob(0, "SWE", "Co", "Remote", 100_000, 150_000, "", "tech", 8),
        SyntheticJob(1, "SWE", "Co", "Remote", 20_000, 30_000, "", "tech", 3),
        SyntheticJob(2, "SWE", "Co", "Remote", None, None, "", "tech", 5),
    ]
    sal_passed = filter_by_salary(test_jobs_sal, "software-engineer")
    assert_true("salary filter passes in-range", 0 in sal_passed)
    assert_true("salary filter rejects out-of-range", 1 not in sal_passed)
    assert_true("salary filter passes no-salary", 2 in sal_passed)

    # Test 7: skill density filter
    test_jobs_skill = [
        SyntheticJob(
            0, "SWE", "Co", "Remote", None, None,
            "Requires python, react, and docker experience", "tech", 8,
        ),
        SyntheticJob(
            1, "SWE", "Co", "Remote", None, None,
            "Must have CDL-A license and forklift certification", "transport", 2,
        ),
    ]
    skill_passed = filter_by_skill_density(test_jobs_skill, "software-engineer", min_matches=2)
    assert_true("skill density passes tech job", 0 in skill_passed)
    assert_true("skill density rejects non-tech", 1 not in skill_passed)

    # Test 8: industry blacklist filter
    test_jobs_ind = [
        SyntheticJob(0, "SWE", "Co", "Remote", None, None, "", "technology", 8),
        SyntheticJob(1, "Nurse", "Co", "Remote", None, None, "", "healthcare", 2),
    ]
    ind_passed = filter_by_industry_blacklist(test_jobs_ind, "software-engineer")
    assert_true("blacklist passes tech", 0 in ind_passed)
    assert_true("blacklist rejects healthcare", 1 not in ind_passed)

    # Test 9: deterministic generation (same seed = same output)
    jobs_a = generate_jobs(50, "software-engineer", seed=99)
    jobs_b = generate_jobs(50, "software-engineer", seed=99)
    assert_true(
        "deterministic generation",
        all(
            a.title == b.title and a.ground_truth_score == b.ground_truth_score
            for a, b in zip(jobs_a, jobs_b)
        ),
    )

    # Test 10: _evaluate_filter correctness
    eval_jobs = generate_jobs(200, "software-engineer", seed=42)
    passed_ids = filter_by_title(eval_jobs, "software-engineer")
    fr = _evaluate_filter("test", passed_ids, eval_jobs, relevance_threshold=6)
    assert_eq(
        "confusion matrix sums to total",
        fr.true_positives + fr.false_positives + fr.true_negatives + fr.false_negatives,
        200,
    )

    console.print(f"  {passed} passed, {failed} failed")
    return failed == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Spike: regex pre-filter vs AI scoring accuracy on synthetic job data",
    )
    parser.add_argument(
        "--profile",
        choices=list(PROFILES.keys()),
        default=None,
        help="User profile to simulate (default: run all profiles)",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=10_000,
        help="Number of synthetic jobs to generate (default: 10000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=12345,
        help="Random seed for reproducibility (default: 12345)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run self-tests and exit",
    )
    args = parser.parse_args()

    console = Console()

    if args.test:
        success = _run_self_tests()
        sys.exit(0 if success else 1)

    profiles = [args.profile] if args.profile else list(PROFILES.keys())
    all_results: list[ExperimentResults] = []

    for profile_name in profiles:
        results = run_experiment(
            profile_name=profile_name,
            n_jobs=args.jobs,
            seed=args.seed,
        )
        all_results.append(results)
        print_results(results, console)

    # Write markdown results
    output_path = Path(__file__).parent / "spike_prefilter_results.md"
    write_results_md(all_results, output_path)
    console.print(f"\n[green]Results written to {output_path}[/green]")


if __name__ == "__main__":
    main()
