"""Tests for tools/job_scorer.py -- AI-based job scoring with pre-filters."""

import json
from unittest.mock import MagicMock

from job_scorer import (
    AI_KEYWORDS,
    BLOCKED_COMPANIES,
    EU_LOCATIONS,
    HARD_CAP_RULES,
    PRODUCT_KEYWORDS,
    PROFILE_CRITERIA,
    REJECT_TITLE_PATTERNS,
    US_ONLY_LOCATIONS,
    apply_hard_caps,
    pre_filter_job,
    score_job,
)

# ==================== PROFILE_CRITERIA ====================


class TestProfileCriteria:
    def test_criteria_is_nonempty(self):
        assert len(PROFILE_CRITERIA) > 100

    def test_contains_must_haves(self):
        assert "MUST-HAVES" in PROFILE_CRITERIA

    def test_contains_scoring_instructions(self):
        assert "fit_score" in PROFILE_CRITERIA or "score" in PROFILE_CRITERIA.lower()

    def test_contains_effort_flag(self):
        assert "effort_flag" in PROFILE_CRITERIA

    def test_contains_prep_level(self):
        assert "prep_level" in PROFILE_CRITERIA

    def test_salary_target_present(self):
        assert "EUR" in PROFILE_CRITERIA  # salary range loaded from config


# ==================== Pre-filter constants ====================


class TestFilterConstants:
    def test_reject_patterns_not_empty(self):
        assert len(REJECT_TITLE_PATTERNS) > 20

    def test_blocked_companies_not_empty(self):
        assert len(BLOCKED_COMPANIES) >= 2

    def test_us_locations_not_empty(self):
        assert len(US_ONLY_LOCATIONS) >= 10

    def test_eu_locations_not_empty(self):
        assert len(EU_LOCATIONS) >= 15

    def test_critical_reject_patterns_present(self):
        """Ensure the most important reject patterns are in the list."""
        critical = [
            "accountant",
            "sales rep",
            "customer support",
            "hr specialist",
            "nurse",
            "recruiter",
        ]
        for pattern in critical:
            assert pattern in REJECT_TITLE_PATTERNS, f"Missing critical pattern: {pattern}"

    def test_blocked_companies_includes_nebius(self):
        assert any("nebius" in c for c in BLOCKED_COMPANIES)

    def test_blocked_companies_includes_yandex(self):
        assert any("yandex" in c for c in BLOCKED_COMPANIES)


# ==================== pre_filter_job ====================


class TestPreFilterJob:
    """Test the hard pre-filter that runs before AI scoring."""

    # --- Rejected titles ---

    def test_rejects_compensation_analyst(self):
        skip, reason, _ = pre_filter_job("Compensation Analyst", "BHG Financial", "Remote")
        assert skip is True
        assert "compensation analyst" in reason.lower()

    def test_rejects_customer_support_specialist(self):
        skip, _reason, _ = pre_filter_job("Customer Support Specialist", "HighLevel", "Remote")
        assert skip is True

    def test_rejects_senior_accountant(self):
        skip, _reason, _ = pre_filter_job("Senior Accountant", "Blink Health", "United States")
        assert skip is True

    def test_rejects_financial_crimes_analyst(self):
        skip, _reason, _ = pre_filter_job("Financial Crimes Analyst I", "Dave", "Remote")
        assert skip is True

    def test_rejects_sales_development_rep(self):
        skip, _reason, _ = pre_filter_job("Sales Development Representative", "Ping Identity", "UK")
        assert skip is True

    def test_rejects_benefits_manager(self):
        skip, _reason, _ = pre_filter_job("Benefits Manager", "Deel", "EMEA")
        assert skip is True

    def test_rejects_employee_relations(self):
        skip, _reason, _ = pre_filter_job("Manager, Employee Relations", "Remote", "Europe")
        assert skip is True

    def test_rejects_nurse_pmhnp(self):
        skip, _reason, _ = pre_filter_job(
            "PMHNP Clinical Autonomy", "Seasoned Recruitment", "Remote"
        )
        assert skip is True

    def test_rejects_hr_specialist(self):
        skip, _reason, _ = pre_filter_job("HR Specialist", "Automat-it", "Ukraine")
        assert skip is True

    def test_rejects_clinical_trial_manager(self):
        skip, _reason, _ = pre_filter_job(
            "Senior Manager, Clinical Trial Management", "Precision Medicine Group", "Spain"
        )
        assert skip is True

    def test_rejects_affiliate_marketing(self):
        skip, _reason, _ = pre_filter_job(
            "Affiliate Marketing Manager", "Hello There Collective", "Remote"
        )
        assert skip is True

    def test_rejects_head_of_aml(self):
        skip, _reason, _ = pre_filter_job(
            "Global Head of AML & Regulatory Compliance", "Kraken", "UK"
        )
        assert skip is True

    def test_rejects_account_executive(self):
        skip, _reason, _ = pre_filter_job("Account Executive, Mid-Market | DACH", "Deel", "Europe")
        assert skip is True

    def test_rejects_food_assurance(self):
        skip, _reason, _ = pre_filter_job("Head of Food Assurance Services", "SGS", "UK")
        assert skip is True

    def test_rejects_salesforce_developer(self):
        skip, _reason, _ = pre_filter_job("Salesforce Developer", "UCAS", "UK")
        assert skip is True

    def test_rejects_onboarding_technician(self):
        skip, _reason, _ = pre_filter_job("Onboarding Technician", "Nextiva", "Ukraine")
        assert skip is True

    def test_rejects_crypto_trader(self):
        skip, _reason, _ = pre_filter_job("Crypto Trader", "ELEMENTAL TERRA", "Remote")
        assert skip is True

    def test_rejects_technical_artist(self):
        skip, _reason, _ = pre_filter_job("Sr. Technical Artist", "Fortis Games", "UK")
        assert skip is True

    def test_rejects_network_support_technician(self):
        skip, _reason, _ = pre_filter_job(
            "Network Support Technician Senior", "General Dynamics", "Wiesbaden"
        )
        assert skip is True

    # --- Roles that should NOT be rejected ---

    def test_passes_senior_tpm_ai(self):
        skip, _, _ = pre_filter_job("Senior TPM AI", "Mistral", "Paris")
        assert skip is False

    def test_passes_product_manager_ai(self):
        skip, _, _ = pre_filter_job("Product Manager, AI", "n8n", "Berlin")
        assert skip is False

    def test_passes_devrel_ai(self):
        skip, _, _ = pre_filter_job("Developer Advocate AI", "Anthropic", "Remote")
        assert skip is False

    def test_passes_founding_engineer(self):
        skip, _, _ = pre_filter_job(
            "Founding Software Engineer - Agentic Systems", "Veriff", "Estonia"
        )
        assert skip is False

    def test_passes_product_engineer(self):
        skip, _, _ = pre_filter_job("Product Engineer", "Oxide Computer", "Remote")
        assert skip is False

    def test_passes_senior_product_manager(self):
        skip, _, _ = pre_filter_job("Senior Product Manager (Data Products)", "G2", "Remote")
        assert skip is False

    def test_passes_engineering_manager(self):
        skip, _, _ = pre_filter_job("Senior Engineering Manager, Design", "GitLab", "Germany")
        assert skip is False

    def test_passes_head_of_engineering(self):
        skip, _, _ = pre_filter_job("Head of Engineering", "Lemon.io", "Remote")
        assert skip is False

    def test_passes_ai_solutions_architect(self):
        skip, _, _ = pre_filter_job("AI Agents Solutions Architect", "Kraken", "UK")
        assert skip is False

    def test_passes_ai_solutions_engineer(self):
        skip, _, _ = pre_filter_job("(Senior) AI Solutions Engineer", "Aktor AI", "Remote")
        assert skip is False

    def test_passes_senior_product_ops(self):
        skip, _, _ = pre_filter_job("Senior Product Operations Manager", "Clickhouse", "UK")
        assert skip is False

    # --- Blocked companies ---

    def test_blocks_nebius(self):
        skip, reason, _ = pre_filter_job("Senior TPM", "Nebius AI", "Amsterdam")
        assert skip is True
        assert "Blocked company" in reason

    def test_blocks_yandex(self):
        skip, _reason, _ = pre_filter_job("Product Manager", "Yandex", "Moscow")
        assert skip is True

    def test_does_not_block_mistral(self):
        skip, _, _ = pre_filter_job("TPM", "Mistral AI", "Paris")
        assert skip is False

    # --- Junior roles ---

    def test_rejects_junior_developer(self):
        skip, reason, _ = pre_filter_job("Junior Full-Stack Developer", "LeadUp AI", "Remote")
        assert skip is True
        assert "Junior" in reason

    def test_passes_junior_if_also_lead(self):
        """Edge case: title with both junior and lead should pass."""
        skip, _, _ = pre_filter_job("Junior to Lead Engineer Pipeline", "SomeCompany", "Remote")
        assert skip is False

    def test_rejects_intern(self):
        skip, _, _ = pre_filter_job("Intern Product Manager", "Google", "Munich")
        assert skip is True

    def test_rejects_werkstudent(self):
        skip, _, _ = pre_filter_job("Werkstudent Data Science", "SAP", "Berlin")
        assert skip is True

    # --- US-only location cap ---

    def test_caps_us_only_san_francisco(self):
        skip, _reason, cap = pre_filter_job(
            "Senior TPM", "Faire", "San Francisco, CA", remote=False
        )
        assert skip is False
        assert cap == 3

    def test_caps_us_only_new_york(self):
        _, _, cap = pre_filter_job("Product Manager", "Stripe", "New York", remote=False)
        assert cap == 3

    def test_no_cap_us_if_remote(self):
        _, _, cap = pre_filter_job("Senior TPM", "Faire", "San Francisco, CA", remote=True)
        assert cap is None

    def test_no_cap_for_eu_location(self):
        _, _, cap = pre_filter_job("Senior TPM", "DeepL", "Berlin, Germany")
        assert cap is None

    def test_no_cap_for_remote(self):
        _, _, cap = pre_filter_job("Product Manager AI", "n8n", "Remote")
        assert cap is None

    def test_no_cap_for_emea(self):
        _, _, cap = pre_filter_job("TPM", "GitLab", "EMEA")
        assert cap is None

    # --- Edge cases ---

    def test_empty_title(self):
        skip, _, _ = pre_filter_job("", "SomeCompany", "Remote")
        assert skip is False  # Empty title should not crash

    def test_empty_company(self):
        skip, _, _ = pre_filter_job("Product Manager", "", "Remote")
        assert skip is False

    def test_none_location(self):
        skip, _, _ = pre_filter_job("Product Manager", "Company", None)
        assert skip is False  # Should not crash


# ==================== score_job (mocked AI) ====================


class TestScoreJob:
    def _make_client(self, response_json: dict):
        """Create a mock OpenAI client that returns the given JSON."""
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(response_json)
        client.chat.completions.create.return_value = mock_response
        return client

    def test_parses_valid_response(self):
        client = self._make_client(
            {
                "score": 8,
                "reasoning": "Strong AI focus",
                "estimated_salary": "130-150k EUR",
                "effort_flag": "sweet-spot",
                "prep_level": 2,
                "prep_notes": "Brush up on MLOps",
            }
        )

        score, reasoning, salary, effort, prep, notes = score_job(
            client, "AI PM", "Mistral", "Build AI products"
        )

        assert score == 8
        assert reasoning == "Strong AI focus"
        assert salary == "130-150k EUR"
        assert effort == "sweet-spot"
        assert prep == 2
        assert notes == "Brush up on MLOps"

    def test_handles_missing_description(self):
        client = MagicMock()
        score, reasoning, _salary, _effort, _prep, _notes = score_job(client, "Test", "Co", None)
        assert score == 0
        assert "No description" in reasoning
        # Should not call OpenAI
        client.chat.completions.create.assert_not_called()

    def test_handles_nan_description(self):
        client = MagicMock()
        score, _reasoning, _salary, _effort, _prep, _notes = score_job(
            client, "Test", "Co", float("nan")
        )
        assert score == 0

    def test_handles_json_parse_error(self):
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not json at all"
        client.chat.completions.create.return_value = mock_response

        score, reasoning, _salary, _effort, _prep, _notes = score_job(
            client, "Test", "Co", "Some description"
        )

        # Fallback should be 2 (not 5) -- conservative
        assert score == 2
        assert "Parse error" in reasoning

    def test_handles_missing_optional_fields(self):
        client = self._make_client(
            {
                "score": 6,
                "reasoning": "Okay fit",
            }
        )

        score, _reasoning, salary, effort, prep, notes = score_job(
            client, "PM", "Co", "Product work"
        )

        assert score == 6
        assert salary == "unknown"
        assert effort == "unknown"
        assert prep == 0
        assert notes == "unknown"

    def test_truncates_long_description(self):
        client = self._make_client(
            {
                "score": 5,
                "reasoning": "Average",
                "estimated_salary": "unknown",
                "effort_flag": "unknown",
                "prep_level": 3,
                "prep_notes": "Study domain",
            }
        )

        long_desc = "x" * 10000
        score_job(client, "Test", "Co", long_desc)

        # Check that the description passed to the API was truncated
        call_args = client.chat.completions.create.call_args
        user_msg = call_args[1]["messages"][1]["content"]
        # Original was 10000 chars, should be truncated to 3000
        assert len(long_desc) > 3000
        assert "x" * 3000 in user_msg

    def test_returns_correct_types(self):
        client = self._make_client(
            {
                "score": "7",  # string instead of int
                "reasoning": "Good fit",
                "estimated_salary": "100k",
                "effort_flag": "moderate",
                "prep_level": "3",  # string instead of int
                "prep_notes": "Some prep",
            }
        )

        score, _reasoning, _salary, _effort, prep, _notes = score_job(
            client, "Test", "Co", "Description"
        )

        assert isinstance(score, int)
        assert isinstance(prep, int)
        assert score == 7
        assert prep == 3

    def test_prompt_contains_strict_calibration(self):
        """Verify the system prompt contains strict scoring instructions."""
        client = self._make_client({"score": 5, "reasoning": "test"})
        score_job(client, "Test", "Co", "Description")

        call_args = client.chat.completions.create.call_args
        system_msg = call_args[1]["messages"][0]["content"]
        assert "EXTREMELY strict" in system_msg
        assert "HARD CAPS" in system_msg
        assert "MAX 1" in system_msg  # Sales, accounting, etc. capped at 1
        assert "EUR" in system_msg  # salary range from config

    def test_prompt_contains_candidate_profile(self):
        """Verify the system prompt includes candidate details."""
        client = self._make_client({"score": 5, "reasoning": "test"})
        score_job(client, "Test", "Co", "Description")

        call_args = client.chat.completions.create.call_args
        system_msg = call_args[1]["messages"][0]["content"]
        assert "THE CANDIDATE" in system_msg  # profile section present
        assert "SCORING CALIBRATION" in system_msg
        assert "HARD CAPS" in system_msg


# ==================== Integration: pre_filter + score_job ====================


class TestScoringIntegration:
    """
    Test the full flow: pre_filter_job decides whether to skip,
    then score_job gets called for non-skipped jobs.
    These test the expected final scores for real job titles from the
    2026-03-27 daily scan.
    """

    def test_compensation_analyst_bhg_financial(self):
        """Compensation Analyst at BHG Financial -- should be rejected by pre-filter."""
        skip, _, _ = pre_filter_job("Compensation Analyst", "BHG Financial", "Remote")
        assert skip is True
        # Effective score: 0

    def test_customer_support_highlevel(self):
        """Customer Support Specialist at HighLevel -- rejected."""
        skip, _, _ = pre_filter_job("Customer Support Specialist", "HighLevel", "Remote")
        assert skip is True

    def test_senior_accountant_blink_health(self):
        """Senior Accountant at Blink Health -- rejected."""
        skip, _, _ = pre_filter_job("Senior Accountant", "Blink Health", "United States")
        assert skip is True

    def test_financial_crimes_analyst_dave(self):
        """Financial Crimes Analyst I at Dave -- rejected."""
        skip, _, _ = pre_filter_job("Financial Crimes Analyst I", "Dave", "")
        assert skip is True

    def test_sales_bdr_near(self):
        """Sales & Business Development Director at NEAR -- rejected."""
        skip, _, _ = pre_filter_job(
            "Sales & Business Development Director", "NEAR Foundation", "San Francisco"
        )
        # "business development" is in reject list
        assert skip is True

    def test_mid_market_customer_account_manager(self):
        """Mid Market Customer Account Manager at Iterable -- rejected."""
        skip, _, _ = pre_filter_job(
            "Mid Market Customer Account Manager", "Iterable", "REMOTE - US"
        )
        assert skip is True

    def test_product_manager_growth_passes(self):
        """Product Manager Growth at 12Go Asia -- should pass filter (PM role)."""
        skip, _, _ = pre_filter_job("Product Manager Growth", "12Go Asia", "Remote")
        assert skip is False

    def test_senior_pm_core_infra_passes(self):
        """Senior Product Manager Core Infrastructure at Mesh -- should pass."""
        skip, _, _ = pre_filter_job("Senior Product Manager Core Infrastructure", "Mesh", "Remote")
        assert skip is False

    def test_founding_sw_eng_agentic_passes(self):
        """Founding Software Engineer - Agentic Systems at Veriff -- should pass."""
        skip, _, _ = pre_filter_job(
            "Founding Software Engineer - Agentic Systems", "Veriff", "Estonia"
        )
        assert skip is False

    def test_ai_solutions_architect_passes(self):
        """AI Agents Solutions Architect at Kraken -- should pass."""
        skip, _, _ = pre_filter_job("AI Agents Solutions Architect - Finance", "Kraken", "UK")
        assert skip is False

    def test_product_manager_ai_wing_passes(self):
        """Product Manager, AI at Wing Assistant -- should pass."""
        skip, _, _ = pre_filter_job("Product Manager, AI", "Wing Assistant", "Remote")
        assert skip is False


# ==================== Batch simulation: 2026-03-27 scan sample ====================


class TestBatchScanSample:
    """
    Simulate pre-filtering on a sample from the 2026-03-27 daily scan.
    Verify that obviously irrelevant roles get filtered out.
    """

    SAMPLE_JOBS = [
        # Should be REJECTED (score 0)
        ("Compensation Analyst", "BHG Financial", "Remote", False),
        ("Customer Support Specialist", "HighLevel", "Remote", False),
        ("Senior Accountant", "Blink Health", "United States", False),
        ("Financial Crimes Analyst I", "Dave", "", False),
        ("Sales Development Representative", "Ping Identity", "UK", False),
        ("Benefits Manager", "Deel", "EMEA", False),
        ("Manager, Employee Relations", "Remote", "Europe", False),
        ("HR Specialist", "Automat-it", "Ukraine", False),
        ("Global Head of AML & Regulatory Compliance", "Kraken", "UK", False),
        ("Affiliate Marketing Manager", "Hello There Collective", "Remote", False),
        ("Sr. Technical Artist", "Fortis Games", "UK", False),
        ("Buyer Support Team Lead", "Paddle", "Portugal", False),
        ("Network Support Technician Senior", "General Dynamics", "Wiesbaden", False),
        ("PMHNP Clinical Autonomy", "Seasoned Recruitment", "", False),
        ("Crypto Trader", "ELEMENTAL TERRA", "", False),
        ("Head of Food Assurance Services", "SGS", "UK", False),
        # Should PASS filter (not rejected)
        ("Senior Product Manager (Data Products)", "G2", "Remote", True),
        ("Product Manager, AI", "Wing Assistant", "Remote", True),
        ("(Senior) AI Solutions Engineer", "Aktor AI", "Remote", True),
        ("Founding Software Engineer - Agentic Systems", "Veriff", "Estonia", True),
        ("Head of Engineering", "Lemon.io", "Remote", True),
        ("Lead Frontend Engineer", "FINN", "Remote", True),
        ("Senior Engineering Manager, Design", "GitLab", "Germany", True),
    ]

    def test_batch_filter_accuracy(self):
        """Verify that pre-filter correctly separates good from bad roles."""
        for title, company, location, should_pass in self.SAMPLE_JOBS:
            skip, reason, _ = pre_filter_job(title, company, location)
            if should_pass:
                assert skip is False, f"WRONGLY REJECTED: {title} @ {company} -- {reason}"
            else:
                assert skip is True, f"WRONGLY PASSED: {title} @ {company} should be rejected"

    def test_at_least_60pct_rejected(self):
        """From a mixed sample, at least 60% of obviously bad roles are caught."""
        rejected = 0
        total_bad = sum(1 for _, _, _, should_pass in self.SAMPLE_JOBS if not should_pass)
        for title, company, location, should_pass in self.SAMPLE_JOBS:
            if not should_pass:
                skip, _, _ = pre_filter_job(title, company, location)
                if skip:
                    rejected += 1
        ratio = rejected / total_bad
        assert ratio >= 0.6, f"Only {ratio:.0%} of bad roles were rejected (need >= 60%)"


# ==================== Hard cap constants ====================


class TestHardCapConstants:
    def test_hard_cap_rules_not_empty(self):
        assert len(HARD_CAP_RULES) >= 7

    def test_product_keywords_not_empty(self):
        assert len(PRODUCT_KEYWORDS) >= 5

    def test_ai_keywords_not_empty(self):
        assert len(AI_KEYWORDS) >= 4

    def test_all_rules_have_three_elements(self):
        for rule in HARD_CAP_RULES:
            assert len(rule) == 3, f"Rule missing elements: {rule}"
            patterns, max_score, name = rule
            assert isinstance(patterns, list)
            assert isinstance(max_score, int)
            assert isinstance(name, str)

    def test_max_scores_are_reasonable(self):
        for _patterns, max_score, name in HARD_CAP_RULES:
            assert 1 <= max_score <= 5, f"Rule {name} has unreasonable max_score={max_score}"


# ==================== apply_hard_caps ====================


class TestApplyHardCaps:
    """Test post-scoring hard cap enforcement."""

    def _make_job(self, title, score, location="Remote", remote=False, reasoning="AI scored"):
        return {
            "title": title,
            "fit_score": score,
            "location": location,
            "remote": remote,
            "fit_reasoning": reasoning,
        }

    # --- Sales/finance/HR/legal/healthcare/support: MAX 1 ---

    def test_caps_sales_role_to_1(self):
        jobs = [self._make_job("Sales Manager", 5)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 1
        assert result[0]["cap_applied"] is True
        assert result[0]["cap_reason"] == "sales_finance_hr_legal_healthcare_support"

    def test_caps_account_executive_to_1(self):
        jobs = [self._make_job("Account Executive, DACH", 6)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 1

    def test_caps_accountant_to_1(self):
        jobs = [self._make_job("Senior Accountant", 4)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 1

    def test_caps_nurse_to_1(self):
        jobs = [self._make_job("Registered Nurse", 5)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 1

    def test_caps_recruiter_to_1(self):
        jobs = [self._make_job("Technical Recruiter", 4)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 1

    def test_caps_compliance_officer_to_1(self):
        jobs = [self._make_job("Compliance Officer", 3)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 1

    def test_caps_help_desk_to_1(self):
        jobs = [self._make_job("Help Desk Specialist", 4)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 1

    # --- Customer Success: MAX 2 ---

    def test_caps_customer_success_to_2(self):
        jobs = [self._make_job("Customer Success Manager", 5)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 2
        assert result[0]["cap_reason"] == "customer_success"

    def test_caps_client_success_to_2(self):
        jobs = [self._make_job("Client Success Lead", 6)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 2

    # --- Marketing/media: MAX 2 ---

    def test_caps_copywriter_to_2(self):
        jobs = [self._make_job("Senior Copywriter", 5)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 2
        assert result[0]["cap_reason"] == "marketing_media_seo_crm"

    def test_caps_seo_specialist_to_2(self):
        jobs = [self._make_job("SEO Specialist", 4)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 2

    def test_caps_crm_manager_to_2(self):
        jobs = [self._make_job("CRM Manager", 5)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 2

    # --- Design/UX (no product): MAX 3 ---

    def test_caps_ux_designer_to_3(self):
        jobs = [self._make_job("UX Designer", 6)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 3
        assert result[0]["cap_reason"] == "design_ux_no_product"

    def test_caps_graphic_designer_to_3(self):
        jobs = [self._make_job("Graphic Designer", 5)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 3

    def test_exempts_product_designer(self):
        """UX designer with 'product' in title should NOT be capped."""
        jobs = [self._make_job("Product UX Designer", 7)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 7
        assert "cap_applied" not in result[0]

    # --- DevOps/SRE (no AI/product): MAX 3 ---

    def test_caps_devops_to_3(self):
        jobs = [self._make_job("DevOps Engineer", 6)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 3
        assert result[0]["cap_reason"] == "devops_sre_no_ai_product"

    def test_caps_sre_to_3(self):
        jobs = [self._make_job("SRE Engineer", 5)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 3

    def test_exempts_ai_devops(self):
        """DevOps with AI keyword should NOT be capped."""
        jobs = [self._make_job("AI DevOps Engineer", 7)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 7

    def test_exempts_product_platform_engineer(self):
        """Platform engineer with 'product' in title should NOT be capped."""
        jobs = [self._make_job("Product Platform Engineer", 6)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 6

    # --- Pure engineer (no PM/product): MAX 4 ---

    def test_caps_software_engineer_to_4(self):
        jobs = [self._make_job("Software Engineer", 7)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 4
        assert result[0]["cap_reason"] == "pure_engineer_no_product"

    def test_caps_backend_engineer_to_4(self):
        jobs = [self._make_job("Backend Engineer", 6)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 4

    def test_exempts_product_software_engineer(self):
        """Software engineer with 'product' keyword should NOT be capped."""
        jobs = [self._make_job("Product Software Engineer", 7)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 7

    def test_exempts_ai_software_engineer(self):
        """Software engineer with AI keyword should NOT be capped."""
        jobs = [self._make_job("AI Software Engineer", 8)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 8

    def test_exempts_ml_software_developer(self):
        """Software developer with ML keyword should NOT be capped."""
        jobs = [self._make_job("ML Software Developer", 7)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 7

    # --- Junior/entry-level: MAX 1 ---

    def test_caps_junior_role_to_1(self):
        jobs = [self._make_job("Junior Developer", 5)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 1
        assert result[0]["cap_reason"] == "junior_entry_level"

    def test_caps_intern_to_1(self):
        jobs = [self._make_job("Intern Product Manager", 4)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 1

    def test_exempts_senior_with_junior_in_title(self):
        """Title with both 'junior' and 'senior' should NOT be capped."""
        jobs = [self._make_job("Senior (ex Junior) Lead", 6)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 6

    # --- US-only non-remote: MAX 3 ---

    def test_caps_us_non_remote_to_3(self):
        jobs = [self._make_job("Product Manager", 7, location="San Francisco", remote=False)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 3
        assert result[0]["cap_reason"] == "us_only_non_remote"

    def test_no_cap_us_if_remote(self):
        """US location with remote=True should NOT be location-capped."""
        jobs = [self._make_job("Product Manager", 7, location="San Francisco", remote=True)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 7

    def test_no_cap_eu_location(self):
        """EU location should NOT be capped."""
        jobs = [self._make_job("Product Manager", 8, location="Berlin, Germany")]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 8

    # --- Edge cases ---

    def test_skips_zero_scored_jobs(self):
        """Jobs with score 0 should not be processed."""
        jobs = [self._make_job("Sales Manager", 0)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 0
        assert "cap_applied" not in result[0]

    def test_no_cap_when_already_below(self):
        """If score is already at or below the cap, no cap is applied."""
        jobs = [self._make_job("Sales Manager", 1)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 1
        assert "cap_applied" not in result[0]

    def test_preserves_original_reasoning(self):
        """Cap should prepend to existing reasoning, not replace it."""
        jobs = [self._make_job("Sales Manager", 5, reasoning="AI thinks this is great")]
        result = apply_hard_caps(jobs)
        assert "AI thinks this is great" in result[0]["fit_reasoning"]
        assert "Hard-capped from 5 to 1" in result[0]["fit_reasoning"]

    def test_empty_title_no_crash(self):
        jobs = [self._make_job("", 5)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 5  # No pattern matches empty title

    def test_none_title_no_crash(self):
        jobs = [{"title": None, "fit_score": 5, "location": "Remote"}]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 5

    def test_multiple_jobs_independent(self):
        """Each job is capped independently."""
        jobs = [
            self._make_job("Sales Manager", 5),
            self._make_job("AI Product Manager", 8, location="Berlin"),
            self._make_job("Software Engineer", 7),
        ]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 1  # Sales capped
        assert result[1]["fit_score"] == 8  # AI PM untouched
        assert result[2]["fit_score"] == 4  # Pure engineer capped

    def test_first_matching_rule_wins(self):
        """Only the first (most restrictive) matching rule should apply."""
        # "customer support" matches both MAX 1 rule and potentially others
        jobs = [self._make_job("Customer Support Specialist", 5)]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 1
        assert result[0]["cap_reason"] == "sales_finance_hr_legal_healthcare_support"

    def test_returns_same_list(self):
        """apply_hard_caps mutates and returns the same list."""
        jobs = [self._make_job("Product Manager", 8)]
        result = apply_hard_caps(jobs)
        assert result is jobs


# ==================== Pre-filter + Hard cap interaction ====================


class TestPreFilterAndHardCapInteraction:
    """Test that pre-filters and hard caps work correctly together."""

    def test_pre_filtered_job_not_hard_capped(self):
        """Jobs rejected by pre-filter (score 0) should not be processed by hard caps."""
        # Pre-filter would reject this
        skip, _, _ = pre_filter_job("Senior Accountant", "BigCo", "Remote")
        assert skip is True
        # If somehow it got through with score 0, hard caps should skip it
        jobs = [{"title": "Senior Accountant", "fit_score": 0, "location": "Remote"}]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 0

    def test_pre_filter_location_cap_then_hard_cap(self):
        """
        A job that passes pre-filter with a location cap of 3
        should then also be checked by hard caps.
        The more restrictive cap should win.
        """
        # Pre-filter gives US-only cap of 3
        skip, _, cap = pre_filter_job("Sales Manager", "BigCo", "New York", remote=False)
        assert skip is False
        assert cap == 3
        # After AI scoring gives 3 (due to pre-filter cap), hard caps check title
        # Sales Manager matches MAX 1 rule, so it goes to 1
        jobs = [{"title": "Sales Manager", "fit_score": 3, "location": "New York"}]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 1

    def test_good_job_passes_both_layers(self):
        """A genuinely good job should pass both pre-filter and hard caps untouched."""
        skip, _, cap = pre_filter_job("Senior AI Product Manager", "Mistral", "Paris")
        assert skip is False
        assert cap is None
        jobs = [{"title": "Senior AI Product Manager", "fit_score": 9, "location": "Paris"}]
        result = apply_hard_caps(jobs)
        assert result[0]["fit_score"] == 9
        assert "cap_applied" not in result[0]
