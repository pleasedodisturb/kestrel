#!/usr/bin/env python3
"""Generate 5 tailored CV PDFs from cv.yaml using RenderCV.

Creates a temporary YAML variant per role with a tailored summary,
renders it, and copies the PDF to the application folder.
"""

import copy
import shutil
import subprocess
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent / "cv"
APP_DIR = BASE_DIR / "applications"
RENDERCV = str(Path(__file__).resolve().parent.parent / ".venv" / "bin" / "rendercv")

# Tailored summaries per role
ROLES = {
    "example-ai-deployment-strategist": {
        "filename": "user-ai-strategist-cv",
        "summary": (
            "10+ years shipping complex technical programs across AI/ML, IoT, and hardware -- "
            "now focused on bringing AI from prototype to production. Built an AI-augmented "
            "program system integrating multiple LLMs with enterprise APIs. Ran ML model "
            "REDACTED. Shipped consumer hardware product to "
            "high volume across 10+ teams. REDACTED "
            "demos to executives, driving REDACTED. Based in Berlin. "
            "The pattern: take the ambiguous, cross-functional, hard-to-own problem and find "
            "the path through it. Builder first, operator by method."
        ),
    },
    "example-sr-product-engineer-ai": {
        "filename": "user-product-eng-cv",
        "summary": (
            "Builder who lives at the intersection of AI systems and product thinking. "
            "Built an AI agent operating system -- 6 LLMs orchestrated through 4 "
            "enterprise APIs, persistent context, RAG-adjacent document registry indexing "
            "1,000+ files, AI provenance tracking, write guardrails. Ran ML model deployment "
            "pipelines at scale. REDACTED "
            "to high volume. 15+ production Python tools, real API integration experience, "
            "end-to-end ownership instinct. The gap is the title -- the muscle is engineering-adjacent "
            "product building under real constraints."
        ),
    },
    "example-pm-developer-tools": {
        "filename": "user-devtools-pm-cv",
        "summary": (
            "Built an AI-powered workflow system -- 4 API keys, a code editor, and a repo "
            "that became a giant story about the program. Still fighting the context problem daily: "
            "multi-generation memory architecture, 4 layers, 2 laptops, still not solved. That's the "
            "product intuition developer tools need -- not from market research, from being the frustrated "
            "user every day. REDACTED to high volume. "
            "REDACTED -- REDACTED, REDACTED. Titles are ephemeral. The work is what matters."
        ),
    },
    "example-sr-developer-advocate": {
        "filename": "user-devrel-cv",
        "summary": (
            "I connect people and build things -- usually at the same time. 10 years bridging "
            "developers, scientists, and business teams across three continents. Built 15+ "
            "automation pipelines, ran REDACTED of automotive AI "
            "(messy, honest ones -- they worked 5x better than slide decks). I care about open "
            "source, honest documentation, and keeping engineering work at least 30% fun. "
            "REDACTED. REDACTED, "
            "currently in Berlin."
        ),
    },
    "example-technical-project-manager": {
        "filename": "user-tpm-cv",
        "summary": (
            "10+ years shipping enterprise-scale technical programs. Not a human calendar -- "
            "I build tools, automate mechanical work, and ship. REDACTED amid "
            "M&A acquisition chaos, audit logging, SOX compliance, zero "
            "critical bugs. REDACTED, 30 weeks "
            "ahead of schedule. Shipped hardware product across 10+ teams in 5 countries. "
            "ML REDACTED. I care about sustainable teams and long-term "
            "relationships. Berlin, available for customer travel."
        ),
    },
    "example-ai-native-tpm": {
        "filename": "user-ai-tpm-cv",
        "summary": (
            "AI-native builder -- four terminal panels, AI coding assistant, voice input, barely touching "
            "the keyboard. Built an AI-augmented program system from scratch: 6 LLMs, "
            "4 enterprise APIs, persistent context, 1,000+ documents indexed. No ticket, no budget "
            "-- just saw the problem and built the solution. Shipped consumer hardware from "
            "sensor research to high volume. Worked on a continuous-learning "
            "REDACTED. REDACTED; "
            "I've been disrupted. Not a cultist, not a Luddite -- I build with AI every day because "
            "it works. Zero-to-one is where I'm best. Working across Europe "
            "since 2016, currently in Berlin."
        ),
    },
    "example-ai-native-pm": {
        "filename": "user-ai-pm-cv",
        "summary": (
            "Same person, different hat. Also applied for the AI-Native TPM role -- writing "
            "separately because PM and TPM in a team like this are the same problem-solving "
            "persona on different days. 10+ years shipping across AI/ML, IoT, and hardware. "
            "Built AI agent system from scratch, drove REDACTED, "
            "shipped consumer hardware to high volume. I learn tools, frameworks, and measurement "
            "systems on the fly. The work is the same. Berlin-based, immediately available."
        ),
    },
    "example-sr-technical-pm-ai": {
        "filename": "user-sr-tpm-ai-cv",
        "summary": (
            "I sit between research teams that want to experiment forever and engineering teams "
            "that need to ship yesterday. Ran ASR REDACTED -- "
            "cut release SLA from multi-day to 1 business day. Worked on a continuous-learning "
            "ML framework made obsolete when LLMs arrived. I don't speculate "
            "about AI disruption; I've been disrupted. Built AI-augmented program system "
            "from scratch -- REDACTED, no ticket, no budget. Shipped consumer "
            "hardware to high volume. I care about REDACTED -- not as a slogan, "
            "but as genuine conviction. REDACTED, currently "
            "in Berlin."
        ),
    },
    "example-sr-swe-product-eng": {
        "filename": "user-swe-product-cv",
        "summary": (
            "Builder crossing from TPM into product engineering via AI tools. Built an AI agent "
            "operating system -- 15+ Python scripts, REDACTED, persistent "
            "context, custom enterprise search CLI, AI provenance tracking. End-to-end ownership: "
            "I research, spec, wireframe, build, and ship. Shipped hardware across 10+ teams in "
            "5 countries. Built demo fleet from nothing -- REDACTED. "
            "High ownership, minimal process, product thinking built from a decade of shipping."
        ),
    },
    "example-product-engineer": {
        "filename": "user-product-eng-crm-cv",
        "summary": (
            "CRM data platform owner. REDACTED "
            "acquisition -- custom objects, permissions models, SOX-compliant connectors, "
            "audit logging. 12+ stakeholders, 3 merging companies, REDACTED "
            "running blind without proper infrastructure. Built AI agent system in parallel -- 6 LLMs, "
            "enterprise APIs, REDACTED. I think about data models instinctively "
            "because I've had to build them. Founder mentality. Germany remote."
        ),
    },
    "example-tpm-science-ops": {
        "filename": "user-tpm-science-cv",
        "summary": (
            "Execution engine builder for research-to-production pipelines. Ran ML model "
            "REDACTED -- bridging Science and Engineering, cutting "
            "release SLA from multi-day to 1 business day. Split monolithic AWS account "
            "REDACTED -- 30 weeks ahead of schedule, zero downtime. "
            "Built AI-augmented program system with persistent context, automated synthesis, "
            "and retrospective-ready data capture. The pattern: structure ambiguity into coordinated "
            "execution without killing the science."
        ),
    },
    "example-tpm-engineering": {
        "filename": "user-tpm-eng-cv",
        "summary": (
            "10+ years driving cross-functional technical delivery at scale. REDACTED: "
            "shipped REDACTED, "
            "split monolithic AWS account into 25 certified services 30 weeks ahead of schedule, "
            "ran ML model REDACTED. Led Salesforce "
            "CRM migration with 12+ stakeholders, built AI-augmented program system from scratch. "
            "Development and deployment process ownership. Technical depth to sit in architecture "
            "reviews and add value."
        ),
    },
    "example-sr-tpm-remote": {
        "filename": "user-sr-tpm-remote-cv",
        "summary": (
            "Async-first TPM who writes documentation because it's how organizations remember "
            "what they decided and why. 10+ years running cross-functional programs across "
            "Engineering, Product, Finance, and Legal. Led CRM transformation amid "
            "M&A acquisition, 12+ stakeholders, built AI system with 1,000+-file "
            "document registry as a living handbook. Split monolithic AWS into 25 certified "
            "services, 30 weeks ahead. ML REDACTED. I build tools, "
            "automate mechanical work, and care about sustainable teams. Berlin, remote-ready."
        ),
    },
    "example-ai-ml-pm": {
        "filename": "user-ai-ml-pm-cv",
        "summary": (
            "REDACTED, not slide decks. 5 demo "
            "cars, REDACTED, 5x sales engagement. "
            "CRM transformation across 3 merging companies, 12+ stakeholders. ML "
            "deployment across multiple continents. I care about open-source AI and "
            "REDACTED, as genuine conviction. "
            "15+ Python tools, AI agent systems, API integrations. I sit in the room with the "
            "partner's ML team and add value. Berlin, EMEA remote."
        ),
    },
}


def load_base_yaml():
    """Load and parse the base cv.yaml."""
    with open(BASE_DIR / "cv.yaml") as f:
        return yaml.safe_load(f)


def render_variant(role_key: str, role_config: dict, base_data: dict):
    """Create a tailored YAML, render it, copy PDF to application folder."""
    variant = copy.deepcopy(base_data)

    # Replace summary
    variant["cv"]["sections"]["summary"] = [role_config["summary"]]

    # Update output filename
    variant["settings"]["render_command"]["pdf_path"] = f"{role_config['filename']}.pdf"
    variant["settings"]["render_command"]["html_path"] = f"{role_config['filename']}.html"

    # Write temp YAML
    temp_yaml = BASE_DIR / f"cv_tailored_{role_key}.yaml"
    with open(temp_yaml, "w") as f:
        yaml.dump(variant, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Render
    print(f"\n  Rendering {role_key}...")
    result = subprocess.run(
        [RENDERCV, "render", str(temp_yaml)],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"  ERROR: {result.stderr}")
        return False

    # Copy PDF to application folder
    src_pdf = BASE_DIR / f"{role_config['filename']}.pdf"
    dst_dir = APP_DIR / role_key
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_pdf = dst_dir / f"{role_config['filename']}.pdf"

    if src_pdf.exists():
        shutil.copy2(src_pdf, dst_pdf)
        print(f"  ✓ {dst_pdf}")
        # Clean up temp files from base dir
        src_pdf.unlink()
        src_html = BASE_DIR / f"{role_config['filename']}.html"
        if src_html.exists():
            src_html.unlink()
    else:
        print(f"  ERROR: PDF not found at {src_pdf}")
        return False

    # Clean up temp YAML
    temp_yaml.unlink()

    return True


def main():
    print("Loading base cv.yaml...")
    base_data = load_base_yaml()

    successes = 0
    for role_key, role_config in ROLES.items():
        if render_variant(role_key, role_config, base_data):
            successes += 1

    print(f"\n{'=' * 50}")
    print(f"Done: {successes}/{len(ROLES)} CVs generated successfully")


if __name__ == "__main__":
    main()
