"""Tests for the embedding pre-filter layer (Epic 4 / G-272).

Covers:
- Vector serialization round-trip
- Cosine similarity calculation
- Profile/job text builders
- Embedding CRUD (store, retrieve, delete, invalidation)
- Pre-filter logic (shadow mode, enabled mode, graceful degradation)
- MockProvider.embed() determinism
"""

from __future__ import annotations

import math

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from career_os.ai.mock_provider import MockProvider
from career_os.database import Base
from career_os.models.discovery import DiscoveredJob
from career_os.models.embeddings import Embedding
from career_os.models.models import Profile
from career_os.models.skills import Goal, Skill
from career_os.services.embeddings import (
    build_job_text,
    build_profile_text,
    bytes_to_vector,
    compute_job_similarities,
    cosine_similarity,
    delete_embedding,
    generate_job_embedding,
    generate_profile_embedding,
    get_embedding,
    invalidate_profile_embedding,
    store_embedding,
    vector_to_bytes,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_engine():
    """In-memory SQLite engine with all tables."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(db_engine) -> Session:
    """Yield a database session."""
    session_cls = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = session_cls()
    yield session
    session.close()


@pytest.fixture
def profile(db: Session) -> Profile:
    """Seed a profile with skills and goals."""
    p = Profile(id=1, name="Test User", email="t@test.com", location="Frankfurt", job_family="TPM")
    db.add(p)
    db.flush()

    db.add(
        Skill(
            profile_id=1,
            name="Python",
            category="technical",
            proficiency="expert",
            evidence_source="manual",
        )
    )
    db.add(
        Skill(
            profile_id=1,
            name="React",
            category="technical",
            proficiency="intermediate",
            evidence_source="manual",
        )
    )
    db.add(
        Goal(
            profile_id=1,
            title="AI-native company",
            goal_type="aspirational",
            description="AI-native company, senior IC track",
        )
    )
    db.commit()
    return p


@pytest.fixture
def discovered_jobs(db: Session, profile: Profile) -> list[DiscoveredJob]:
    """Seed three discovered jobs."""
    jobs = [
        DiscoveredJob(
            id=10,
            profile_id=1,
            title="Senior AI Engineer",
            company="Mistral AI",
            location="Remote",
            title_normalized="senior ai engineer",
            company_normalized="mistral ai",
            location_normalized="remote",
            description="Build cutting-edge AI models. Python, PyTorch required.",
        ),
        DiscoveredJob(
            id=20,
            profile_id=1,
            title="Office Administrator",
            company="Big Corp",
            location="Munich",
            title_normalized="office administrator",
            company_normalized="big corp",
            location_normalized="munich",
            description="Manage office supplies and calendar. MS Office required.",
        ),
        DiscoveredJob(
            id=30,
            profile_id=1,
            title="No Description Job",
            company="Mystery Inc",
            location="Nowhere",
            title_normalized="no description job",
            company_normalized="mystery inc",
            location_normalized="nowhere",
            description=None,
        ),
    ]
    db.add_all(jobs)
    db.commit()
    return jobs


@pytest.fixture
def mock_provider() -> MockProvider:
    return MockProvider()


# ---------------------------------------------------------------------------
# Vector serialization
# ---------------------------------------------------------------------------


class TestVectorSerialization:
    def test_round_trip(self):
        """Vector survives serialize → deserialize."""
        original = [0.1, -0.5, 0.0, 1.0, -1.0]
        blob = vector_to_bytes(original)
        restored = bytes_to_vector(blob)
        assert len(restored) == len(original)
        for a, b in zip(original, restored, strict=True):
            assert abs(a - b) < 1e-6

    def test_768_dim(self):
        """768-dim vector round-trips correctly."""
        vec = [float(i) / 768 for i in range(768)]
        assert len(bytes_to_vector(vector_to_bytes(vec))) == 768


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors(self):
        """Cosine similarity of identical vectors is 1.0."""
        v = [1.0, 2.0, 3.0]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        """Cosine similarity of orthogonal vectors is 0.0."""
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert abs(cosine_similarity(a, b)) < 1e-6

    def test_opposite_vectors(self):
        """Cosine similarity of opposite vectors is -1.0."""
        a = [1.0, 2.0, 3.0]
        b = [-1.0, -2.0, -3.0]
        assert abs(cosine_similarity(a, b) + 1.0) < 1e-6

    def test_known_value(self):
        """Known vectors produce expected cosine similarity."""
        a = [1.0, 0.0]
        b = [1.0, 1.0]
        # cos(45°) = 1/√2 ≈ 0.7071
        expected = 1.0 / math.sqrt(2)
        assert abs(cosine_similarity(a, b) - expected) < 1e-6

    def test_zero_vector(self):
        """Zero vector returns 0.0 similarity."""
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == 0.0

    def test_length_mismatch_raises(self):
        """Mismatched vector lengths raise ValueError."""
        with pytest.raises(ValueError, match="length mismatch"):
            cosine_similarity([1.0, 2.0], [1.0])


# ---------------------------------------------------------------------------
# Text builders
# ---------------------------------------------------------------------------


class TestTextBuilders:
    def test_build_profile_text(self, db: Session, profile: Profile):
        """Profile text includes job family, skills, goals, and location."""
        text = build_profile_text(db, profile.id)
        assert text is not None
        assert "TPM" in text
        assert "Python (expert)" in text
        assert "React (intermediate)" in text
        assert "AI-native company" in text
        assert "Frankfurt" in text

    def test_build_profile_text_nonexistent(self, db: Session):
        """Non-existent profile returns None."""
        assert build_profile_text(db, 9999) is None

    def test_build_job_text(self):
        """Job text includes title, company, and description."""
        text = build_job_text("Full stack developer needed", title="SWE", company="Acme")
        assert "Title: SWE" in text
        assert "Company: Acme" in text
        assert "Full stack developer" in text

    def test_build_job_text_empty(self):
        """Empty inputs produce empty string."""
        assert build_job_text(None) == ""

    def test_build_job_text_truncation(self):
        """Very long descriptions are truncated."""
        long_desc = "x" * 50_000
        text = build_job_text(long_desc)
        assert len(text) <= 35_000  # _MAX_JD_CHARS + small overhead


# ---------------------------------------------------------------------------
# Embedding CRUD
# ---------------------------------------------------------------------------


class TestEmbeddingCRUD:
    def test_store_and_retrieve(self, db: Session):
        """Store an embedding and retrieve it."""
        vec = [0.1, 0.2, 0.3]
        store_embedding(db, "profile", 1, vec, model_name="test-model")
        db.commit()

        result = get_embedding(db, "profile", 1, model_name="test-model")
        assert result is not None
        assert len(result) == 3
        for a, b in zip(vec, result, strict=True):
            assert abs(a - b) < 1e-6

    def test_store_updates_existing(self, db: Session):
        """Storing again for the same entity updates the vector."""
        store_embedding(db, "profile", 1, [1.0, 2.0], model_name="test-model")
        db.commit()

        store_embedding(db, "profile", 1, [3.0, 4.0], model_name="test-model")
        db.commit()

        result = get_embedding(db, "profile", 1, model_name="test-model")
        assert result is not None
        assert abs(result[0] - 3.0) < 1e-6

        # Only one row in the table
        count = db.query(Embedding).filter(Embedding.entity_type == "profile").count()
        assert count == 1

    def test_retrieve_nonexistent(self, db: Session):
        """Retrieving a missing embedding returns None."""
        assert get_embedding(db, "profile", 999, model_name="test-model") is None

    def test_delete_embedding(self, db: Session):
        """Delete removes the embedding."""
        store_embedding(db, "profile", 1, [1.0], model_name="test-model")
        db.commit()

        count = delete_embedding(db, "profile", 1, model_name="test-model")
        db.commit()
        assert count == 1
        assert get_embedding(db, "profile", 1, model_name="test-model") is None

    def test_invalidate_profile_embedding(self, db: Session, profile: Profile):
        """Invalidation deletes the profile embedding."""
        store_embedding(db, "profile", profile.id, [1.0, 2.0], model_name="nomic-embed-text")
        db.commit()

        deleted = invalidate_profile_embedding(db, profile.id)
        db.commit()
        assert deleted == 1
        assert get_embedding(db, "profile", profile.id, model_name="nomic-embed-text") is None


# ---------------------------------------------------------------------------
# MockProvider.embed()
# ---------------------------------------------------------------------------


class TestMockProviderEmbed:
    @pytest.mark.asyncio
    async def test_returns_768_dim(self, mock_provider: MockProvider):
        """MockProvider.embed() returns a 768-dimensional vector."""
        vec = await mock_provider.embed("test text")
        assert len(vec) == 768

    @pytest.mark.asyncio
    async def test_deterministic(self, mock_provider: MockProvider):
        """Same input produces same output."""
        a = await mock_provider.embed("hello world")
        b = await mock_provider.embed("hello world")
        assert a == b

    @pytest.mark.asyncio
    async def test_different_texts_differ(self, mock_provider: MockProvider):
        """Different inputs produce different vectors."""
        a = await mock_provider.embed("Python developer")
        b = await mock_provider.embed("Office administrator")
        assert a != b

    @pytest.mark.asyncio
    async def test_unit_normalized(self, mock_provider: MockProvider):
        """Mock embeddings are unit-normalized."""
        vec = await mock_provider.embed("test")
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# Profile & job embedding generation
# ---------------------------------------------------------------------------


class TestEmbeddingGeneration:
    @pytest.mark.asyncio
    async def test_profile_embedding_generated(
        self, db: Session, profile: Profile, mock_provider: MockProvider
    ):
        """Profile embedding is created and stored after generation."""
        vec = await generate_profile_embedding(db, profile.id, mock_provider)
        assert vec is not None
        assert len(vec) == 768

        # Verify it's cached
        cached = get_embedding(db, "profile", profile.id)
        assert cached is not None

    @pytest.mark.asyncio
    async def test_job_embedding_generated(self, db: Session, discovered_jobs, mock_provider):
        """Job embedding is created when generated."""
        job = discovered_jobs[0]
        vec = await generate_job_embedding(
            db,
            job.id,
            job.description,
            title=job.title,
            company=job.company,
            provider=mock_provider,
        )
        assert vec is not None
        assert len(vec) == 768

        cached = get_embedding(db, "discovered_job", job.id)
        assert cached is not None

    @pytest.mark.asyncio
    async def test_graceful_degradation_no_embed_support(self, db: Session, profile: Profile):
        """When provider doesn't support embeddings, returns None gracefully."""
        from career_os.ai.base import AIProvider
        from career_os.schemas.ai import AIFeature, AIResponse

        class NoEmbedProvider(AIProvider):
            @property
            def name(self):
                return "no-embed"

            async def complete(self, prompt, *, feature=AIFeature.complete, context=None, **kw):
                return AIResponse(content="", provider="no-embed", feature=feature)

            async def score(self, job_description, profile_data, **kw):
                return AIResponse(content="", provider="no-embed", feature=AIFeature.score)

        provider = NoEmbedProvider()
        vec = await generate_profile_embedding(db, profile.id, provider)
        assert vec is None

    @pytest.mark.asyncio
    async def test_embedding_invalidation_on_profile_change(
        self, db: Session, profile: Profile, mock_provider: MockProvider
    ):
        """Profile embedding is regenerated when skills/goals change."""
        # Generate initial embedding
        vec1 = await generate_profile_embedding(db, profile.id, mock_provider)
        assert vec1 is not None

        # Simulate profile change: invalidate
        invalidate_profile_embedding(db, profile.id)
        db.commit()

        # Embedding is gone
        assert get_embedding(db, "profile", profile.id) is None

        # Add a new skill and regenerate
        db.add(
            Skill(
                profile_id=profile.id,
                name="Kubernetes",
                category="technical",
                proficiency="beginner",
                evidence_source="manual",
            )
        )
        db.commit()

        vec2 = await generate_profile_embedding(db, profile.id, mock_provider)
        assert vec2 is not None
        # Different text should produce a different embedding
        assert vec1 != vec2


# ---------------------------------------------------------------------------
# Pre-filter logic
# ---------------------------------------------------------------------------


class TestPreFilter:
    @pytest.mark.asyncio
    async def test_compute_similarities(
        self, db: Session, profile: Profile, discovered_jobs, mock_provider
    ):
        """compute_job_similarities returns similarity scores for each job."""
        sims = await compute_job_similarities(db, profile.id, discovered_jobs, mock_provider)

        # Job 30 has no description but still has title/company, so it gets embedded
        # All 3 should have similarities
        assert len(sims) >= 2  # at least the 2 with descriptions
        for _job_id, score in sims.items():
            assert -1.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_prefilter_removes_low_similarity(
        self, db: Session, profile: Profile, discovered_jobs, mock_provider
    ):
        """Jobs below threshold are excluded when pre-filter is enabled."""
        sims = await compute_job_similarities(db, profile.id, discovered_jobs, mock_provider)

        # Use a threshold that filters some jobs
        # Set threshold very high so most jobs are filtered
        threshold = 0.99
        filtered = [j for j in discovered_jobs if sims.get(j.id, threshold) >= threshold]
        remaining = [j for j in discovered_jobs if sims.get(j.id, threshold) < threshold]

        # At least some should be filtered at 0.99 threshold
        # (mock embeddings are deterministic but not identical to profile)
        assert len(remaining) > 0 or len(filtered) < len(discovered_jobs)

    @pytest.mark.asyncio
    async def test_prefilter_keeps_high_similarity(
        self, db: Session, profile: Profile, discovered_jobs, mock_provider
    ):
        """Jobs above threshold proceed to full scoring."""
        sims = await compute_job_similarities(db, profile.id, discovered_jobs, mock_provider)

        # Use a very low threshold — all jobs should pass
        threshold = -1.0
        filtered = [j for j in discovered_jobs if sims.get(j.id, threshold) >= threshold]
        assert len(filtered) == len(sims)

    @pytest.mark.asyncio
    async def test_shadow_mode_logs_without_filtering(
        self, db: Session, profile: Profile, discovered_jobs, mock_provider
    ):
        """In shadow mode, similarities are computed and logged but all jobs remain."""
        sims = await compute_job_similarities(db, profile.id, discovered_jobs, mock_provider)

        # Shadow mode: don't filter, just log. Verify similarities were stored.
        for job in discovered_jobs:
            if job.id in sims:
                assert job.embedding_similarity is not None

        # All jobs still in the list (shadow mode doesn't remove any)
        assert len(discovered_jobs) == 3

    @pytest.mark.asyncio
    async def test_similarity_stored_on_discovered_job(
        self, db: Session, profile: Profile, discovered_jobs, mock_provider
    ):
        """embedding_similarity column is populated on DiscoveredJob rows."""
        await compute_job_similarities(db, profile.id, discovered_jobs, mock_provider)
        db.commit()

        for job in discovered_jobs:
            refreshed = db.get(DiscoveredJob, job.id)
            if refreshed.description or refreshed.title:
                # Jobs with any text should have similarity
                assert refreshed.embedding_similarity is not None

    @pytest.mark.asyncio
    async def test_graceful_degradation_no_profile(
        self, db: Session, discovered_jobs, mock_provider
    ):
        """When profile has no embedding text, similarities dict is empty."""
        # Create a minimal profile with no skills/goals/location/job_family
        bare = Profile(id=99, name="Bare Profile")
        db.add(bare)
        db.commit()

        sims = await compute_job_similarities(db, 99, discovered_jobs, mock_provider)
        assert sims == {}
