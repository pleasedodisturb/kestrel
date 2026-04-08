"""Run the full data migration: seed profile, import CSV, link packages.

Usage:
    python -m career_os.migration.run_migration [--csv-path PATH] [--packages-path PATH]
"""

import logging
import sys
from pathlib import Path

from career_os.database import SessionLocal
from career_os.migration.csv_import import import_csv
from career_os.migration.link_packages import link_packages
from career_os.migration.seed import seed_default_profile, seed_ghost_detection_records

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-5.5s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Default paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CSV_PATH = PROJECT_ROOT / "tracking" / "applications.csv"
DEFAULT_PACKAGES_PATH = PROJECT_ROOT / "cv" / "applications"


def run_full_migration(
    csv_path: Path | None = None,
    packages_path: Path | None = None,
) -> dict:
    """Run the complete data migration pipeline.

    1. Seed default profile
    2. Import CSV data
    3. Link application packages

    Args:
        csv_path: Path to applications.csv. Defaults to tracking/applications.csv.
        packages_path: Path to application packages. Defaults to cv/applications/.

    Returns:
        Dictionary with migration results.
    """
    csv_path = csv_path or DEFAULT_CSV_PATH
    packages_path = packages_path or DEFAULT_PACKAGES_PATH

    db = SessionLocal()
    try:
        # Step 1: Seed default profile
        logger.info("Step 1: Seeding default profile...")
        profile = seed_default_profile(db)

        # Step 2: Import CSV
        logger.info("Step 2: Importing CSV from %s...", csv_path)
        csv_stats = import_csv(db, csv_path, profile.id)

        # Step 3: Link application packages
        logger.info("Step 3: Linking application packages from %s...", packages_path)
        pkg_stats = link_packages(db, packages_path, profile.id)

        # Step 4: Seed ghost detection test records
        logger.info("Step 4: Seeding ghost detection test records...")
        ghost_count = seed_ghost_detection_records(db, profile.id)

        results = {
            "profile": {"id": profile.id, "name": profile.name},
            "csv_import": csv_stats,
            "package_linking": pkg_stats,
            "ghost_seed": {"created": ghost_count},
        }

        logger.info("=" * 60)
        logger.info("Migration complete!")
        logger.info(
            "  Profile: %s (id=%d)", profile.name, profile.id
        )
        logger.info(
            "  CSV: %d imported, %d skipped",
            csv_stats["imported"],
            csv_stats["skipped"],
        )
        logger.info(
            "  Packages: %d linked, %d not found",
            pkg_stats["linked"],
            pkg_stats["not_found"],
        )
        if csv_stats["warnings"]:
            logger.info("  CSV warnings:")
            for w in csv_stats["warnings"]:  # type: ignore[union-attr]
                logger.info("    - %s", w)
        if pkg_stats["warnings"]:
            logger.info("  Package warnings:")
            for w in pkg_stats["warnings"]:  # type: ignore[union-attr]
                logger.info("    - %s", w)

        return results

    finally:
        db.close()


if __name__ == "__main__":
    csv_arg = sys.argv[1] if len(sys.argv) > 1 else None
    pkg_arg = sys.argv[2] if len(sys.argv) > 2 else None
    run_full_migration(
        csv_path=Path(csv_arg) if csv_arg else None,
        packages_path=Path(pkg_arg) if pkg_arg else None,
    )
