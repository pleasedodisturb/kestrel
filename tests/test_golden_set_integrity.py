import json
from pathlib import Path

import pytest

FIXTURES = list(Path("tests/fixtures").glob("scoring_golden_set*.json"))


@pytest.mark.parametrize("fixture_path", FIXTURES, ids=lambda p: p.name)
def test_golden_set_structure(fixture_path):
    with open(fixture_path) as f:
        data = json.load(f)

    assert "profile" in data, "Missing profile section"
    assert "jobs" in data, "Missing jobs section"
    assert "job_family" in data["profile"]
    assert "location" in data["profile"]

    jobs = data["jobs"]
    assert len(jobs) >= 20

    ids = [j["id"] for j in jobs]
    assert len(ids) == len(set(ids)), "Duplicate IDs found"

    valid_categories = {"reject", "mediocre", "strong", "dream"}
    for job in jobs:
        assert "id" in job
        assert "category" in job and job["category"] in valid_categories
        assert "expected_band" in job and len(job["expected_band"]) == 2
        assert job["expected_band"][0] <= job["expected_band"][1]
        assert "title" in job
        assert "company" in job
        assert "description" in job
        assert len(job["description"]) >= 50, f"Description too short for {job['id']}"
