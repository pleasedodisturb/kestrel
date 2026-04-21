# Spike: Regex Pre-filter vs AI Scoring Accuracy

## Methodology

- Generated 10,000 synthetic job listings per profile with realistic variation
- Each job has a baked-in ground truth relevance score (1-10)
- Distribution: ~20% highly relevant (7-10), ~20% borderline (4-6), ~60% irrelevant (1-3)
- Relevance threshold: score >= 6 is 'relevant' (positive class)
- Tested 6 filter strategies: title keywords, salary range, skill density, industry blacklist, weighted combination, strict combination

## Key Findings

### Profile: software-engineer

- **Best strategy:** Skill Density (>=2)
- **Recall:** 0.976 (missed 60 relevant)
- **Jobs eliminated:** 61.7%
- **F1 Score:** 0.769

### Profile: product-manager

- **Best strategy:** Skill Density (>=2)
- **Recall:** 0.971 (missed 72 relevant)
- **Jobs eliminated:** 61.7%
- **F1 Score:** 0.768

### Profile: data-scientist

- **Best strategy:** Skill Density (>=2)
- **Recall:** 0.969 (missed 79 relevant)
- **Jobs eliminated:** 61.6%
- **F1 Score:** 0.777

## Detailed Results

### Profile: software-engineer

- Total jobs: 10,000
- Relevant (score >= 6): 2,489 (24.9%)
- Irrelevant (score < 6): 7,511 (75.1%)

| Strategy | Passed | Eliminated % | Precision | Recall | F1 | False Neg | Verdict |
|----------|--------|-------------|-----------|--------|-----|-----------|---------|
| Title Keywords | 2,401 | 76.0% | 0.720 | 0.695 | 0.707 | 760 | TOO AGGRESSIVE |
| Salary Range | 5,151 | 48.5% | 0.474 | 0.982 | 0.640 | 45 | ACCEPTABLE |
| Skill Density (>=2) | 3,827 | 61.7% | 0.635 | 0.976 | 0.769 | 60 | RECOMMENDED |
| Industry Blacklist | 8,730 | 12.7% | 0.285 | 1.000 | 0.444 | 0 | LOW IMPACT |
| Combined (weighted) | 3,975 | 60.2% | 0.623 | 0.995 | 0.766 | 12 | RECOMMENDED |
| Combined (strict) | 3,975 | 60.2% | 0.623 | 0.995 | 0.766 | 12 | RECOMMENDED |

**Confusion Matrices:**

| Strategy | TP | FP | TN | FN |
|----------|-----|-----|-----|-----|
| Title Keywords | 1729 | 672 | 6839 | 760 |
| Salary Range | 2444 | 2707 | 4804 | 45 |
| Skill Density (>=2) | 2429 | 1398 | 6113 | 60 |
| Industry Blacklist | 2489 | 6241 | 1270 | 0 |
| Combined (weighted) | 2477 | 1498 | 6013 | 12 |
| Combined (strict) | 2477 | 1498 | 6013 | 12 |

### Profile: product-manager

- Total jobs: 10,000
- Relevant (score >= 6): 2,505 (25.1%)
- Irrelevant (score < 6): 7,495 (75.0%)

| Strategy | Passed | Eliminated % | Precision | Recall | F1 | False Neg | Verdict |
|----------|--------|-------------|-----------|--------|-----|-----------|---------|
| Title Keywords | 3,016 | 69.8% | 0.719 | 0.865 | 0.785 | 337 | TRADEOFF |
| Salary Range | 4,995 | 50.0% | 0.482 | 0.961 | 0.642 | 97 | RECOMMENDED |
| Skill Density (>=2) | 3,832 | 61.7% | 0.635 | 0.971 | 0.768 | 72 | RECOMMENDED |
| Industry Blacklist | 8,701 | 13.0% | 0.288 | 1.000 | 0.447 | 0 | LOW IMPACT |
| Combined (weighted) | 4,037 | 59.6% | 0.621 | 1.000 | 0.766 | 0 | RECOMMENDED |
| Combined (strict) | 4,037 | 59.6% | 0.621 | 1.000 | 0.766 | 0 | RECOMMENDED |

**Confusion Matrices:**

| Strategy | TP | FP | TN | FN |
|----------|-----|-----|-----|-----|
| Title Keywords | 2168 | 848 | 6647 | 337 |
| Salary Range | 2408 | 2587 | 4908 | 97 |
| Skill Density (>=2) | 2433 | 1399 | 6096 | 72 |
| Industry Blacklist | 2505 | 6196 | 1299 | 0 |
| Combined (weighted) | 2505 | 1532 | 5963 | 0 |
| Combined (strict) | 2505 | 1532 | 5963 | 0 |

### Profile: data-scientist

- Total jobs: 10,000
- Relevant (score >= 6): 2,571 (25.7%)
- Irrelevant (score < 6): 7,429 (74.3%)

| Strategy | Passed | Eliminated % | Precision | Recall | F1 | False Neg | Verdict |
|----------|--------|-------------|-----------|--------|-----|-----------|---------|
| Title Keywords | 3,084 | 69.2% | 0.720 | 0.863 | 0.785 | 352 | TRADEOFF |
| Salary Range | 5,064 | 49.4% | 0.491 | 0.967 | 0.651 | 84 | ACCEPTABLE |
| Skill Density (>=2) | 3,840 | 61.6% | 0.649 | 0.969 | 0.777 | 79 | RECOMMENDED |
| Industry Blacklist | 8,694 | 13.1% | 0.296 | 1.000 | 0.456 | 0 | LOW IMPACT |
| Combined (weighted) | 4,075 | 59.2% | 0.631 | 1.000 | 0.774 | 0 | RECOMMENDED |
| Combined (strict) | 4,075 | 59.2% | 0.631 | 1.000 | 0.774 | 0 | RECOMMENDED |

**Confusion Matrices:**

| Strategy | TP | FP | TN | FN |
|----------|-----|-----|-----|-----|
| Title Keywords | 2219 | 865 | 6564 | 352 |
| Salary Range | 2487 | 2577 | 4852 | 84 |
| Skill Density (>=2) | 2492 | 1348 | 6081 | 79 |
| Industry Blacklist | 2571 | 6123 | 1306 | 0 |
| Combined (weighted) | 2571 | 1504 | 5925 | 0 |
| Combined (strict) | 2571 | 1504 | 5925 | 0 |

## Cost Analysis

Assumptions: 1,500 jobs/day, $0.003 per AI scoring call

| Strategy | Monthly Cost | Monthly Savings | Eliminated % | Recall |
|----------|-------------|-----------------|-------------|--------|
| Title Keywords | $32.41 | $102.59 | 76.0% | 0.695 |
| Salary Range | $69.54 | $65.46 | 48.5% | 0.982 |
| Skill Density (>=2) | $51.66 | $83.34 | 61.7% | 0.976 |
| Industry Blacklist | $117.86 | $17.14 | 12.7% | 1.000 |
| Combined (weighted) | $53.66 | $81.34 | 60.2% | 0.995 |
| Combined (strict) | $53.66 | $81.34 | 60.2% | 0.995 |

Baseline monthly cost (no filter): $135.00

## Recommendations

1. **Use the Combined (strict) filter as Stage 1** — it requires either a matching title OR sufficient skill keywords, AND not being in a blacklisted industry. This gives the best balance of elimination rate and recall.
2. **The Combined (weighted) filter is the safest choice** if recall is paramount — it passes more jobs through but still eliminates a meaningful percentage.
3. **Title-only filtering is too aggressive** — it misses relevant jobs with non-standard titles (e.g., 'IT Specialist' doing SWE work).
4. **Industry blacklist alone has low impact** — it catches obviously irrelevant industries but many irrelevant jobs are in non-blacklisted sectors.
5. **Salary filter alone is nearly useless** — too many jobs lack salary data, so the filter passes most jobs through.

## Next Steps

- Validate findings against real scraped data (sample 500 real jobs)
- Implement the chosen filter strategy in the discovery pipeline
- Add monitoring to track false negative rate in production
- Consider adaptive thresholds that tune based on user feedback
