/**
 * Shared TypeScript types matching backend Pydantic schemas.
 */

export type ApplicationStatus =
  | "discovered"
  | "interested"
  | "applied"
  | "interviewing"
  | "offer"
  | "accepted"
  | "rejected"
  | "ghosted";

export const APPLICATION_STATUSES: ApplicationStatus[] = [
  "discovered",
  "interested",
  "applied",
  "interviewing",
  "offer",
  "accepted",
  "rejected",
  "ghosted",
];

/**
 * Normalize a status string to its canonical lowercase form.
 * Handles title-cased or mixed-case values from migrated DB rows.
 */
export function normalizeStatus(raw: string): ApplicationStatus {
  const lower = raw.trim().toLowerCase();
  if (APPLICATION_STATUSES.includes(lower as ApplicationStatus)) {
    return lower as ApplicationStatus;
  }
  return "discovered"; // fallback for unknown statuses
}

/** Human-readable labels for each status column. */
export const STATUS_LABELS: Record<ApplicationStatus, string> = {
  discovered: "Discovered",
  interested: "Interested",
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  accepted: "Accepted",
  rejected: "Rejected",
  ghosted: "Ghosted",
};

/** Color theme per status for visual distinction. */
export const STATUS_COLORS: Record<
  ApplicationStatus,
  { bg: string; border: string; text: string; badge: string }
> = {
  discovered: {
    bg: "bg-slate-50",
    border: "border-slate-200",
    text: "text-slate-700",
    badge: "bg-slate-100 text-slate-700",
  },
  interested: {
    bg: "bg-blue-50",
    border: "border-blue-200",
    text: "text-blue-700",
    badge: "bg-blue-100 text-blue-700",
  },
  applied: {
    bg: "bg-indigo-50",
    border: "border-indigo-200",
    text: "text-indigo-700",
    badge: "bg-indigo-100 text-indigo-700",
  },
  interviewing: {
    bg: "bg-amber-50",
    border: "border-amber-200",
    text: "text-amber-700",
    badge: "bg-amber-100 text-amber-700",
  },
  offer: {
    bg: "bg-emerald-50",
    border: "border-emerald-200",
    text: "text-emerald-700",
    badge: "bg-emerald-100 text-emerald-700",
  },
  accepted: {
    bg: "bg-green-50",
    border: "border-green-200",
    text: "text-green-700",
    badge: "bg-green-100 text-green-700",
  },
  rejected: {
    bg: "bg-red-50",
    border: "border-red-200",
    text: "text-red-700",
    badge: "bg-red-100 text-red-700",
  },
  ghosted: {
    bg: "bg-gray-50",
    border: "border-gray-300",
    text: "text-gray-500",
    badge: "bg-gray-100 text-gray-500",
  },
};

export type RedFlagSeverity = "info" | "caution" | "warning" | "dealbreaker";

export interface RedFlag {
  flag_type: string;
  severity: RedFlagSeverity;
  description: string;
}

/** Six dimensional sub-scores (0-10 each) returned by the scoring engine. */
export interface DimensionalScores {
  technical_fit: number;
  seniority_alignment: number;
  compensation_fit: number;
  location_fit: number;
  career_trajectory: number;
  company_fit: number;
}

export type ATSKeywordCategory =
  | "technical"
  | "soft_skill"
  | "tool"
  | "certification"
  | "domain";

export interface ATSKeyword {
  keyword: string;
  category: ATSKeywordCategory;
  matched: boolean;
}

/**
 * Shape of the /api/score/application/{id} response. Mirrors the backend
 * `ScoreResponse` pydantic schema — only the fields we actively consume on
 * the application detail page are listed.
 */
export interface ScoreResponseShape {
  fit_score: number;
  readiness_score: number;
  career_alignment: number;
  letter_grade?: string | null;
  dimensional_scores?: DimensionalScores | null;
  ats_keywords?: ATSKeyword[];
  red_flags?: RedFlag[];
  reasoning: string;
}

export interface Application {
  id: number;
  profile_id: number;
  company: string;
  role: string;
  url: string | null;
  source: string | null;
  status: ApplicationStatus;
  salary_range: string | null;
  contact: string | null;
  next_step: string | null;
  notes: string | null;
  fit_score: number | null;
  readiness_score: number | null;
  letter_grade?: string | null;
  red_flags?: RedFlag[] | null;
  date_applied: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  is_ghost: boolean;
}

export interface ApplicationListResponse {
  applications: Application[];
  total: number;
}

export interface ApplicationUpdate {
  company?: string;
  role?: string;
  url?: string;
  source?: string;
  status?: string;
  salary_range?: string;
  contact?: string;
  next_step?: string;
  notes?: string;
  fit_score?: number;
}

export interface ApplicationCreate {
  company: string;
  role: string;
  url?: string;
  source?: string;
  salary_range?: string;
  contact?: string;
  next_step?: string;
  notes?: string;
  fit_score?: number;
}

export interface ActivityLogEntry {
  id: number;
  action: string;
  details: string | null;
  source: string | null;
  created_at: string;
}

export interface FollowUpSummary {
  id: number;
  due_date: string;
  follow_up_type: string;
  notes: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ApplicationPackageSummary {
  id: number;
  package_name: string;
  file_path: string;
  package_type: string;
}

export interface ApplicationDetailResponse extends Application {
  activity_log: ActivityLogEntry[];
  follow_ups: FollowUpSummary[];
  packages: ApplicationPackageSummary[];
}

export interface FollowUp {
  id: number;
  application_id: number;
  profile_id: number;
  due_date: string;
  follow_up_type: string;
  notes: string | null;
  completed_at: string | null;
  created_at: string;
  application_company: string | null;
  application_role: string | null;
}

export interface FollowUpListResponse {
  follow_ups: FollowUp[];
  total: number;
}

export interface FollowUpCreate {
  application_id: number;
  profile_id: number;
  due_date: string;
  follow_up_type: string;
  notes?: string;
}

export interface OverdueCountResponse {
  count: number;
}

// ---------------------------------------------------------------------------
// Skills Intelligence types
// ---------------------------------------------------------------------------

export type SkillCategory = "technical" | "domain" | "soft" | "tools";

export type SkillProficiency = "beginner" | "intermediate" | "advanced" | "expert";

export interface Skill {
  id: number;
  profile_id: number;
  name: string;
  category: SkillCategory;
  proficiency: SkillProficiency;
  evidence_source: string;
  evidence_detail: string | null;
  created_at: string;
  updated_at: string;
}

export interface SkillListResponse {
  skills: Skill[];
  total: number;
  ctas?: { label: string; action: string }[];
}

export interface SkillCreate {
  profile_id: number;
  name: string;
  category: SkillCategory;
  proficiency?: SkillProficiency;
  evidence_source?: string;
  evidence_detail?: string;
}

export interface SkillUpdate {
  name?: string;
  category?: SkillCategory;
  proficiency?: SkillProficiency;
  evidence_source?: string;
  evidence_detail?: string | null;
  reason?: string;
}

export interface SkillHistoryEntry {
  id: number;
  skill_id: number;
  previous_proficiency: string | null;
  new_proficiency: string;
  reason: string | null;
  created_at: string;
}

export interface IngestRequest {
  profile_id: number;
  sources: string[];
}

export interface IngestResponse {
  skills_created: number;
  skills_updated: number;
  sources_processed: string[];
  errors: string[];
}

// ---------------------------------------------------------------------------
// Learning Paths types
// ---------------------------------------------------------------------------

export type LearningStatus = "not_started" | "in_progress" | "completed";

export type ResourceType = "free_course" | "paid_course" | "hands_on_project";

export type Difficulty = "beginner" | "intermediate" | "advanced" | "expert";

export interface LearningResource {
  id: number;
  profile_id: number;
  gap_id: number | null;
  skill_id: number | null;
  title: string;
  url: string | null;
  provider: string | null;
  resource_type: ResourceType;
  estimated_hours: number | null;
  difficulty: Difficulty | null;
  status: LearningStatus;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface TemplateRecommendation {
  title: string;
  url: string | null;
  provider: string | null;
  resource_type: ResourceType;
  estimated_hours: number | null;
  difficulty: Difficulty | null;
}

export interface GapRecommendationsResponse {
  gap_id: number;
  skill_name: string;
  recommendations: LearningResource[];
  template_recommendations: TemplateRecommendation[];
  cta: { label: string; action: string } | null;
}

export interface LearningResourceCreate {
  profile_id: number;
  title: string;
  url?: string;
  resource_type: ResourceType;
  estimated_hours?: number;
  difficulty?: Difficulty;
  provider?: string;
}

export interface LearningStatusUpdate {
  profile_id: number;
  status: LearningStatus;
}

// ---------------------------------------------------------------------------
// Gap types (for learning paths integration)
// ---------------------------------------------------------------------------

export interface GapItem {
  skill_name: string;
  required_level: string;
  current_level: string | null;
  severity: string;
  distance: number;
}

export interface GapAnalysisResponse {
  application_id: number;
  company: string;
  role: string;
  gaps: GapItem[];
  readiness_score: number;
  total_requirements: number;
  gaps_count: number;
}

// ---------------------------------------------------------------------------
// Discovery Search & Filter types
// ---------------------------------------------------------------------------

export interface DiscoveredJob {
  id: number;
  profile_id: number;
  title: string;
  company: string;
  location: string;
  url: string | null;
  description: string | null;
  salary_range: string | null;
  remote: boolean;
  posted_at: string | null;
  sources: string[];
  source_urls: string[];
  fit_score: number | null;
  readiness_score: number | null;
  letter_grade?: string | null;
  red_flags?: RedFlag[] | null;
  application_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface JobSearchResponse {
  jobs: DiscoveredJob[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface JobSearchParams {
  profile_id: number;
  q?: string;
  source?: string;
  remote?: boolean;
  salary_min?: number;
  salary_max?: number;
  score_min?: number;
  score_max?: number;
  date_from?: string;
  date_to?: string;
  company?: string;
  location?: string;
  sort?: string;
  order?: string;
  page?: number;
  page_size?: number;
}

export interface SavedSearchConfig {
  q?: string;
  source?: string;
  remote?: boolean;
  salary_min?: number;
  salary_max?: number;
  score_min?: number;
  score_max?: number;
  date_from?: string;
  date_to?: string;
  company?: string;
  location?: string;
  sort?: string;
  order?: string;
}

export interface SavedSearch {
  id: number;
  profile_id: number;
  name: string;
  config: SavedSearchConfig;
  created_at: string;
  updated_at: string;
}

export interface SavedSearchListResponse {
  searches: SavedSearch[];
  total: number;
}

export interface SavedSearchCreate {
  profile_id: number;
  name: string;
  config: SavedSearchConfig;
}

// ---------------------------------------------------------------------------
// Interview Prep types
// ---------------------------------------------------------------------------

export interface PrepTopic {
  topic: string;
  relevance: string;
  difficulty: string;
  source?: string | null;
}

export interface PrepQuestion {
  question: string;
  category: string;
  difficulty: string;
}

export interface PrepChecklistItem {
  id: number;
  item: string;
  time_minutes: number;
  priority: string;
  completed: boolean;
  completed_at: string | null;
}

export interface InterviewPrepResponse {
  application_id: number;
  company: string;
  role: string;
  company_researched: boolean;
  research_prompt: string | null;
  topics: PrepTopic[];
  questions: PrepQuestion[];
  checklist: PrepChecklistItem[];
  total_prep_minutes: number;
  total_prep_hours: number;
  progress_percentage: number;
  completed_items: number;
  total_items: number;
}

// ---------------------------------------------------------------------------
// STAR Stories types
// ---------------------------------------------------------------------------

export interface StarStory {
  id: number;
  profile_id: number;
  title: string;
  situation: string;
  task: string;
  action: string;
  result: string;
  skill_tags: string[];
  created_at: string;
  updated_at: string;
}

export interface StarStoryListResponse {
  stories: StarStory[];
  total: number;
}

export interface StarStoryCreate {
  title: string;
  situation: string;
  task: string;
  action: string;
  result: string;
  skill_tags: string[];
}

export interface StarStoryUpdate {
  title?: string;
  situation?: string;
  task?: string;
  action?: string;
  result?: string;
  skill_tags?: string[];
}

export interface RecommendedStory {
  story: StarStory;
  matching_skills: string[];
  match_count: number;
}

export interface RecommendedStoriesResponse {
  application_id: number;
  company: string;
  role: string;
  recommended_stories: RecommendedStory[];
  total_requirements: number;
  covered_skills: string[];
}

export interface StoryGap {
  skill_name: string;
  severity: string;
  required_level: string;
  has_story: boolean;
  create_prompt: string;
}

export interface StoryGapsResponse {
  application_id: number;
  company: string;
  role: string;
  story_gaps: StoryGap[];
  total_requirements: number;
  covered_count: number;
  gap_count: number;
}

// ---------------------------------------------------------------------------
// Networking CRM types (M6)
// ---------------------------------------------------------------------------

export type RelationshipType =
  | "referral"
  | "recruiter"
  | "hiring_manager"
  | "peer"
  | "mentor"
  | "other";

export const RELATIONSHIP_TYPES: RelationshipType[] = [
  "referral",
  "recruiter",
  "hiring_manager",
  "peer",
  "mentor",
  "other",
];

export const RELATIONSHIP_LABELS: Record<RelationshipType, string> = {
  referral: "Referral",
  recruiter: "Recruiter",
  hiring_manager: "Hiring Manager",
  peer: "Peer",
  mentor: "Mentor",
  other: "Other",
};

export type Warmth = "cold" | "warm" | "hot";

export const WARMTH_LEVELS: Warmth[] = ["cold", "warm", "hot"];

export const WARMTH_COLORS: Record<Warmth, { bg: string; text: string; badge: string }> = {
  cold: { bg: "bg-blue-50", text: "text-blue-700", badge: "bg-blue-100 text-blue-700" },
  warm: { bg: "bg-amber-50", text: "text-amber-700", badge: "bg-amber-100 text-amber-700" },
  hot: { bg: "bg-red-50", text: "text-red-700", badge: "bg-red-100 text-red-700" },
};

export type ReferralStatus =
  | "none"
  | "contacted"
  | "cv_sent"
  | "submitted"
  | "feedback_received";

export type InteractionType =
  | "email"
  | "call"
  | "coffee"
  | "linkedin_message"
  | "intro"
  | "referral_submission";

export type ContactRole =
  | "referrer"
  | "recruiter"
  | "hiring_manager"
  | "interviewer"
  | "insider";

export interface Contact {
  id: number;
  profile_id: number;
  name: string;
  company: string | null;
  role: string | null;
  email: string | null;
  linkedin_url: string | null;
  phone: string | null;
  relationship_type: RelationshipType;
  referral_status: string | null;
  warmth: Warmth;
  notes: string | null;
  tags: string[] | null;
  source: string | null;
  last_contacted_at: string | null;
  next_follow_up: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface ContactListResponse {
  contacts: Contact[];
  total: number;
}

export interface ContactCreate {
  name: string;
  company?: string;
  role?: string;
  email?: string;
  linkedin_url?: string;
  phone?: string;
  relationship_type?: RelationshipType;
  warmth?: Warmth;
  source?: string;
  notes?: string;
  tags?: string[];
}

export interface ContactUpdate {
  name?: string;
  company?: string;
  role?: string;
  email?: string;
  linkedin_url?: string;
  phone?: string;
  relationship_type?: RelationshipType;
  referral_status?: string;
  warmth?: Warmth;
  notes?: string;
  tags?: string[];
  source?: string;
}

export interface ContactInteraction {
  id: number;
  contact_id: number;
  profile_id: number;
  interaction_type: InteractionType;
  direction: "inbound" | "outbound";
  subject: string | null;
  notes: string | null;
  occurred_at: string;
  created_at: string;
}

export interface ContactApplicationLink {
  id: number;
  contact_id: number;
  application_id: number;
  profile_id: number;
  role: ContactRole;
  notes: string | null;
  created_at: string;
}

export interface ContactDetailResponse extends Contact {
  interactions: ContactInteraction[];
  linked_applications: ContactApplicationLink[];
}
