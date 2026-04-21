"""SQLAlchemy models package."""

from career_os.models.calendar import CalendarEvent
from career_os.models.company_research import CompanyResearchReportModel
from career_os.models.contacts import Contact, ContactApplication, ContactInteraction
from career_os.models.discovery import (
    DiscoveredJob,
    DiscoveryRun,
    SearchProfile,
)
from career_os.models.embeddings import Embedding
from career_os.models.esco import ESCOSkill, SkillMapping
from career_os.models.integrations import IntegrationConfig
from career_os.models.interview_prep import (
    InterviewPrepItem,
    InterviewPrepSession,
)
from career_os.models.models import (
    ActivityLog,
    Application,
    ApplicationPackage,
    FollowUp,
    Profile,
)
from career_os.models.onboarding import OnboardingState
from career_os.models.pushover import NotificationLog, NotificationPreference
from career_os.models.scoring import (
    ScoredJob,
    ScoringWeights,
)
from career_os.models.skills import (
    CoachingSuggestion,
    Goal,
    JobRequirement,
    LearningResource,
    Skill,
    SkillHistory,
)
from career_os.models.star_stories import StarStory
from career_os.models.ticktick_sync import TickTickSyncTask
from career_os.models.voice import VoiceMessage, VoiceSession

__all__ = [
    "ActivityLog",
    "Application",
    "CalendarEvent",
    "CompanyResearchReportModel",
    "Contact",
    "ESCOSkill",
    "SkillMapping",
    "ContactApplication",
    "ContactInteraction",
    "ApplicationPackage",
    "CoachingSuggestion",
    "Embedding",
    "DiscoveredJob",
    "DiscoveryRun",
    "FollowUp",
    "Goal",
    "IntegrationConfig",
    "InterviewPrepItem",
    "InterviewPrepSession",
    "JobRequirement",
    "LearningResource",
    "NotificationLog",
    "NotificationPreference",
    "OnboardingState",
    "Profile",
    "ScoredJob",
    "ScoringWeights",
    "SearchProfile",
    "Skill",
    "SkillHistory",
    "StarStory",
    "TickTickSyncTask",
    "VoiceMessage",
    "VoiceSession",
]
