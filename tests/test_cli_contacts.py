"""CLI tests for Networking CRM (M6) — 12 tests per spec §3.6."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from career_os.cli.main import app
from career_os.database import Base
from career_os.models.contacts import Contact
from career_os.models.models import Application, Profile

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def db_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    TestSession = sessionmaker(bind=connection, autocommit=False, autoflush=False)

    session = TestSession()
    session.add(Profile(id=1, name="Test User", email="test@example.com"))
    session.commit()

    # Monkeypatch SessionLocal to return our test session
    monkeypatch.setattr("career_os.cli.contacts.SessionLocal", TestSession)

    yield session
    session.close()
    connection.close()
    engine.dispose()


@pytest.fixture
def sample_app(db_session: Session) -> int:
    a = Application(profile_id=1, company="Mistral", role="TPM", status="applied")
    db_session.add(a)
    db_session.commit()
    db_session.refresh(a)
    return a.id


def _add_contact(name: str = "Jane Doe", **kwargs) -> int:
    """Helper: add a contact and return its ID."""
    args = ["contacts", "add", "--name", name]
    for k, v in kwargs.items():
        args.extend([f"--{k.replace('_', '-')}", str(v)])
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    # Extract ID from output
    import re

    match = re.search(r"ID: (\d+)", result.output)
    assert match, f"Could not find ID in output: {result.output}"
    return int(match.group(1))


# ---------------------------------------------------------------------------
# 1. contacts add — full flags
# ---------------------------------------------------------------------------


def test_contacts_add_full(db_session):
    result = runner.invoke(
        app,
        [
            "contacts",
            "add",
            "--name",
            "Jane Doe",
            "--company",
            "Mistral",
            "--type",
            "referral",
            "--warmth",
            "hot",
            "--source",
            "conference",
            "--notes",
            "Met at AI conf",
            "--tags",
            "ai,tpm",
        ],
    )
    assert result.exit_code == 0
    assert "Jane Doe" in result.output
    assert "ID:" in result.output


# ---------------------------------------------------------------------------
# 2. contacts list — empty
# ---------------------------------------------------------------------------


def test_contacts_list_empty(db_session):
    result = runner.invoke(app, ["contacts", "list"])
    assert result.exit_code == 0
    assert "No contacts found" in result.output


# ---------------------------------------------------------------------------
# 3. contacts list — with data
# ---------------------------------------------------------------------------


def test_contacts_list_with_data(db_session):
    _add_contact("Alice")
    _add_contact("Bob")
    result = runner.invoke(app, ["contacts", "list"])
    assert result.exit_code == 0
    assert "Alice" in result.output
    assert "Bob" in result.output


# ---------------------------------------------------------------------------
# 4. contacts list --company X
# ---------------------------------------------------------------------------


def test_contacts_list_filter_company(db_session):
    _add_contact("Alice", company="Mistral")
    _add_contact("Bob", company="Linear")
    result = runner.invoke(app, ["contacts", "list", "--company", "Mistral"])
    assert result.exit_code == 0
    assert "Alice" in result.output
    assert "Bob" not in result.output


# ---------------------------------------------------------------------------
# 5. contacts list --type referral
# ---------------------------------------------------------------------------


def test_contacts_list_filter_type(db_session):
    _add_contact("Ref", type="referral")
    _add_contact("Rec", type="recruiter")
    result = runner.invoke(app, ["contacts", "list", "--type", "referral"])
    assert result.exit_code == 0
    assert "Ref" in result.output
    assert "Rec" not in result.output


# ---------------------------------------------------------------------------
# 6. contacts show <id>
# ---------------------------------------------------------------------------


def test_contacts_show(db_session):
    cid = _add_contact("Jane Doe", company="Mistral", type="referral")
    result = runner.invoke(app, ["contacts", "show", str(cid)])
    assert result.exit_code == 0
    assert "Jane Doe" in result.output
    assert "Mistral" in result.output
    assert "referral" in result.output


# ---------------------------------------------------------------------------
# 7. contacts update <id> --referral-status cv_sent
# ---------------------------------------------------------------------------


def test_contacts_update(db_session):
    cid = _add_contact("Jane")
    result = runner.invoke(app, ["contacts", "update", str(cid), "--referral-status", "cv_sent"])
    assert result.exit_code == 0
    assert "Updated" in result.output


# ---------------------------------------------------------------------------
# 8. contacts log <id> --type email
# ---------------------------------------------------------------------------


def test_contacts_log_interaction(db_session):
    cid = _add_contact("Jane")
    result = runner.invoke(
        app,
        [
            "contacts",
            "log",
            str(cid),
            "--type",
            "email",
            "--direction",
            "outbound",
            "--notes",
            "Sent CV for TPM role",
        ],
    )
    assert result.exit_code == 0
    assert "email" in result.output
    assert "outbound" in result.output


# ---------------------------------------------------------------------------
# 9. contacts history <id>
# ---------------------------------------------------------------------------


def test_contacts_history(db_session):
    cid = _add_contact("Jane")
    runner.invoke(app, ["contacts", "log", str(cid), "--type", "email", "--direction", "outbound"])
    runner.invoke(app, ["contacts", "log", str(cid), "--type", "call", "--direction", "inbound"])
    result = runner.invoke(app, ["contacts", "history", str(cid)])
    assert result.exit_code == 0
    assert "email" in result.output
    assert "call" in result.output


# ---------------------------------------------------------------------------
# 10. contacts link <c_id> <a_id>
# ---------------------------------------------------------------------------


def test_contacts_link(db_session, sample_app: int):
    cid = _add_contact("Jane")
    result = runner.invoke(
        app, ["contacts", "link", str(cid), str(sample_app), "--role", "referrer"]
    )
    assert result.exit_code == 0
    assert "Linked" in result.output


# ---------------------------------------------------------------------------
# 11. contacts at <company>
# ---------------------------------------------------------------------------


def test_contacts_at_company(db_session):
    _add_contact("Alice", company="Mistral")
    _add_contact("Bob", company="Mistral")
    result = runner.invoke(app, ["contacts", "at", "Mistral"])
    assert result.exit_code == 0
    assert "Alice" in result.output
    assert "Bob" in result.output


# ---------------------------------------------------------------------------
# 12. contacts follow-ups
# ---------------------------------------------------------------------------


def test_contacts_follow_ups(db_session):
    # Create a contact with overdue follow-up directly in DB
    past = datetime.now(UTC) - timedelta(days=1)
    contact = Contact(
        profile_id=1,
        name="Overdue Jane",
        relationship_type="referral",
        warmth="warm",
        next_follow_up=past,
    )
    db_session.add(contact)
    db_session.commit()

    result = runner.invoke(app, ["contacts", "follow-ups"])
    assert result.exit_code == 0
    assert "Overdue Jane" in result.output
