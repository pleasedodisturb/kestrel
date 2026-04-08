# CV Templates

This directory contains sample CV and cover letter templates for Kestrel.

## Getting Started

1. Copy the sample CV to the cv/ root:
   ```bash
   cp cv/sample/sample-cv.yaml cv/cv.yaml
   ```

2. Edit `cv/cv.yaml` with your real information

3. Build your CV (requires RenderCV):
   ```bash
   pip install rendercv
   rendercv render cv/cv.yaml
   ```

## Per-Company Applications

For tailored applications, create a folder per company:
```
cv/applications/
  acme-senior-engineer/
    cv.yaml          # Tailored CV variant
    cover-letter.md  # Company-specific cover letter
    cover-letter.pdf # Generated PDF
```

## Cover Letters

Use `sample-cover-letter.md` as a starting point. The key rules:
- Be specific to the company (no generic letters)
- Lead with what you can do for them, not what you want
- Keep it under one page
- Use your own voice, not corporate speak
