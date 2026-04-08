"""Link YAML application packages from cv/applications/ to database records.

Matches package directories to Application records by company+role heuristic.
"""

import logging
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from career_os.models.models import Application, ApplicationPackage

logger = logging.getLogger(__name__)

# Mapping from package directory names to (company_substring, role_substring) patterns
# These map the 14 known package directories to their CSV counterparts
PACKAGE_MAPPINGS: dict[str, tuple[str, str]] = {
    "ashby-sr-swe-product-eng": ("Ashby", "Senior Software Engineer"),
    "attio-product-engineer": ("Attio", "Product Engineer"),
    "deepl-sr-technical-pm-ai": ("DeepL", "Senior Technical Product Manager"),
    "jetbrains-pm-bonsai": ("JetBrains", "Product Manager for Bonsai"),
    "mistral-ai-deployment-strategist": ("Mistral AI", "AI Deployment Strategist"),
    "mistral-tpm-engineering": ("Mistral AI", "Technical Program Manager - Engineering"),
    "mistral-tpm-science-ops": ("Mistral AI", "Technical Program Manager - Science"),
    "mongodb-technical-project-manager": ("MongoDB", "Technical Project Manager"),
    "n8n-sr-developer-advocate": ("n8n", "Senior Developer Advocate"),
    "oxide-computer": ("Oxide Computer", ""),
    "plain-sr-product-engineer-ai": ("Plain", "Senior Product Engineer"),
    "shopware-ai-native-pm": ("shopware", "AI-Native Product Manager"),
    "shopware-ai-native-tpm": ("shopware", "AI-Native Technical Program Manager"),
}


def _find_matching_application(
    db: Session,
    company_pattern: str,
    role_pattern: str,
    profile_id: int,
) -> Application | None:
    """Find an application matching company and role patterns.

    Args:
        db: SQLAlchemy session.
        company_pattern: Company name substring to match.
        role_pattern: Role title substring to match.
        profile_id: Profile ID to filter by.

    Returns:
        Matching Application or None.
    """
    query = db.query(Application).filter(
        Application.profile_id == profile_id,
        func.lower(Application.company).contains(company_pattern.lower()),
    )

    if role_pattern:
        # Try matching with role pattern
        results = query.filter(
            func.lower(Application.role).contains(role_pattern.lower())
        ).all()
        if results:
            return results[0]

        # If no match with role, try company-only match
        results = query.all()
        if len(results) == 1:
            return results[0]
        return results[0] if results else None
    else:
        # Company-only match (e.g., oxide-computer)
        results = query.all()
        return results[0] if results else None


def _find_file(directory: Path, patterns: list[str]) -> str | None:
    """Find a file matching any of the given patterns in a directory.

    Args:
        directory: Directory to search in.
        patterns: List of glob patterns to try.

    Returns:
        Relative path to the file, or None.
    """
    for pattern in patterns:
        matches = list(directory.glob(pattern))
        if matches:
            return str(matches[0])
    return None


def link_packages(
    db: Session,
    packages_dir: str | Path,
    profile_id: int,
    *,
    dry_run: bool = False,
) -> dict[str, int | list[str]]:
    """Link application package directories to Application records.

    Args:
        db: SQLAlchemy session.
        packages_dir: Path to cv/applications/ directory.
        profile_id: Profile ID for the packages.
        dry_run: If True, don't commit.

    Returns:
        Dictionary with linking statistics.
    """
    packages_dir = Path(packages_dir)
    if not packages_dir.exists():
        raise FileNotFoundError(f"Packages directory not found: {packages_dir}")

    stats: dict[str, int | list[str]] = {
        "linked": 0,
        "not_found": 0,
        "warnings": [],
    }
    warnings_list: list[str] = stats["warnings"]  # type: ignore[assignment]

    # Get all subdirectories (skip hidden files like .DS_Store)
    package_dirs = sorted(
        d for d in packages_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    )

    for pkg_dir in package_dirs:
        dir_name = pkg_dir.name

        # Look up the mapping
        mapping = PACKAGE_MAPPINGS.get(dir_name)
        if mapping is None:
            warnings_list.append(f"No mapping defined for package directory: {dir_name}")
            stats["not_found"] = int(stats["not_found"]) + 1
            continue

        company_pattern, role_pattern = mapping

        # Find matching application
        application = _find_matching_application(
            db, company_pattern, role_pattern, profile_id
        )

        if application is None:
            warnings_list.append(
                f"No matching application for package '{dir_name}' "
                f"(company='{company_pattern}', role='{role_pattern}')"
            )
            stats["not_found"] = int(stats["not_found"]) + 1
            continue

        # Check if already linked
        existing = (
            db.query(ApplicationPackage)
            .filter(
                ApplicationPackage.application_id == application.id,
                ApplicationPackage.package_dir == str(pkg_dir),
            )
            .first()
        )
        if existing:
            logger.info("Package '%s' already linked to application %d", dir_name, application.id)
            continue

        # Find cover letter and CV files
        cover_letter = _find_file(pkg_dir, ["cover-letter.md", "cover_letter.md", "cover*.md"])
        cv_file = _find_file(pkg_dir, ["*cv*.pdf", "*CV*.pdf"])

        # Create package record
        package = ApplicationPackage(
            profile_id=profile_id,
            application_id=application.id,
            package_dir=str(pkg_dir),
            cover_letter_path=cover_letter,
            cv_path=cv_file,
        )
        db.add(package)

        stats["linked"] = int(stats["linked"]) + 1
        logger.info(
            "Linked package '%s' to %s / %s (id=%d)",
            dir_name,
            application.company,
            application.role,
            application.id,
        )

    if not dry_run:
        db.commit()

    logger.info(
        "Package linking complete: %d linked, %d not found, %d warnings",
        stats["linked"],
        stats["not_found"],
        len(warnings_list),
    )
    return stats
