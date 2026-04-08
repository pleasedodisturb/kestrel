"""URL validation utilities for ATS platform detection.

Replaces substring-based URL checks (e.g. ``"greenhouse.io" in url``) with
proper ``urlparse``-based hostname validation that cannot be bypassed via
query parameters, fragments, or subdomain tricks.
"""

from urllib.parse import urlparse

# Maps platform name -> set of valid hostnames (and suffixes for subdomains)
_PLATFORM_DOMAINS: dict[str, list[str]] = {
    "ashby": ["jobs.ashbyhq.com"],
    "lever": ["jobs.lever.co", "jobs.eu.lever.co"],
    "greenhouse": ["boards.greenhouse.io", "boards.eu.greenhouse.io",
                    "job-boards.greenhouse.io", "job-boards.eu.greenhouse.io"],
    "remotely": ["www.remotely.de", "remotely.de"],
    "linkedin": ["www.linkedin.com", "linkedin.com"],
    "workable": ["apply.workable.com"],
}

# Greenhouse domain suffixes for EU detection
_GREENHOUSE_EU_SUFFIXES = (".eu.greenhouse.io",)


def _hostname_matches(hostname: str, allowed: list[str]) -> bool:
    """Check if hostname matches or is a subdomain of any allowed domain."""
    return any(hostname == domain or hostname.endswith("." + domain) for domain in allowed)


def detect_platform(url: str) -> str:
    """Detect ATS platform from a job URL using proper hostname validation.

    Parses the URL and checks the hostname against known ATS domains.
    Returns the platform name or "unknown"/"other".
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return "unknown"

    hostname = (parsed.hostname or "").lower()

    for platform, domains in _PLATFORM_DOMAINS.items():
        if _hostname_matches(hostname, domains):
            return platform

    return "unknown"


def is_greenhouse_eu(url: str) -> bool:
    """Check if a Greenhouse URL is for the EU region.

    Uses hostname parsing instead of substring matching.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    hostname = (parsed.hostname or "").lower()
    return any(hostname.endswith(suffix) for suffix in _GREENHOUSE_EU_SUFFIXES)


def url_has_domain(url: str, domain: str) -> bool:
    """Check if a URL's hostname matches or is a subdomain of the given domain.

    Safe replacement for ``"domain" in url`` patterns.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False

    hostname = (parsed.hostname or "").lower()
    domain = domain.lower()
    return hostname == domain or hostname.endswith("." + domain)
