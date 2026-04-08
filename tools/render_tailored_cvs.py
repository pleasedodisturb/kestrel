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
    "mistral-ai-deployment-strategist": {
        "filename": "user-mistral-cv",
        "summary": (
            "10+ years shipping complex technical programs across AI/ML, IoT, and hardware -- "
            "now focused on bringing AI from prototype to production. Built an AI-augmented "
            "program system at Wolt integrating 6 LLMs with enterprise APIs. Ran ASR model "
            "deployment at Alexa across 3 continents. Shipped Ring Ultra radar camera to "
            "800k-2M units across 10+ teams in 5 countries. Conducted 200+ live AI product "
            "demos to OEM executives at CloudMade, driving $1M+ contracts. Based in Frankfurt. "
            "The pattern: take the ambiguous, cross-functional, hard-to-own problem and find "
            "the path through it. Builder first, operator by method."
        ),
    },
    "plain-sr-product-engineer-ai": {
        "filename": "user-plain-cv",
        "summary": (
            "Builder who lives at the intersection of AI systems and product thinking. "
            "Built an AI agent operating system at Wolt -- 6 LLMs orchestrated through 4 "
            "enterprise APIs, persistent context, RAG-adjacent document registry indexing "
            "1,140 files, AI provenance tracking, write guardrails. Ran ASR model deployment "
            "pipelines at Alexa scale. Shipped Ring Ultra radar camera from sensor research "
            "to 800k-2M units. 15+ production Python tools, real API integration experience, "
            "end-to-end ownership instinct. The gap is the title -- the muscle is engineering-adjacent "
            "product building under real constraints."
        ),
    },
    "jetbrains-pm-bonsai": {
        "filename": "user-jetbrains-cv",
        "summary": (
            "Built an AI version of myself at Wolt -- 4 API keys, a Cursor prompt, and a repo "
            "that became a giant story about the program. Still fighting the context problem daily: "
            "5th generation memory architecture, 4 layers, 2 laptops, still not solved. That's the "
            "product intuition Bonsai needs -- not from market research, from being the frustrated "
            "user every day. Ring Ultra: sensor research to 800k-2M units. CloudMade: 5 demo cars, "
            "200+ live drives, $1M+ contracts. Titles are ephemeral. The work is what matters."
        ),
    },
    "n8n-sr-developer-advocate": {
        "filename": "user-n8n-cv",
        "summary": (
            "I connect people and build things -- usually at the same time. 10 years bridging "
            "developers, scientists, and business teams across three continents. Built 15+ "
            "automation pipelines at Wolt, ran 200+ live demos of automotive AI at CloudMade "
            "(messy, honest ones -- they worked 5x better than slide decks). I care about open "
            "source, honest documentation, and keeping engineering work at least 30% fun. "
            "CliftonStrengths #1: Communication. Working in Europe all around since 2016, "
            "originally from Ukraine, currently in Frankfurt."
        ),
    },
    "mongodb-technical-project-manager": {
        "filename": "user-mongodb-cv",
        "summary": (
            "10+ years shipping enterprise-scale technical programs. Not a human calendar -- "
            "I build tools, automate mechanical work, and ship. Wolt: Salesforce CRM amid "
            "DoorDash/Deliveroo acquisition chaos, MongoDB audit logging, SOX compliance, zero "
            "critical bugs. Ring: split monolithic AWS account into 25 certified services, 30 weeks "
            "ahead of schedule. Shipped Ring Ultra across 10+ teams in 5 countries. Alexa: ML "
            "deployment across 3 continents. I care about sustainable teams and long-term "
            "relationships. Frankfurt, available for customer travel."
        ),
    },
    "shopware-ai-native-tpm": {
        "filename": "user-shopware-tpm-cv",
        "summary": (
            "AI-native builder -- four iTerm panels, Claude Code, Superwhisper, barely touching "
            "the keyboard. Built an AI-augmented program system at Wolt from scratch: 6 LLMs, "
            "4 enterprise APIs, persistent context, 1,140 documents indexed. No ticket, no budget "
            "-- just saw the problem and built the solution. Shipped Ring Ultra radar camera from "
            "sensor research to 800k-2M units. Worked on EverLearn at Alexa AGI -- a continuous-learning "
            "ML framework that became obsolete when LLMs arrived. I don't speculate about AI disruption; "
            "I've been disrupted. Not a cultist, not a Luddite -- I build with AI every day because "
            "it works. Zero-to-one is where I'm best. Originally from Ukraine, working across Europe "
            "since 2016, currently in Frankfurt."
        ),
    },
    "shopware-ai-native-pm": {
        "filename": "user-shopware-pm-cv",
        "summary": (
            "Same person, different hat. Also applied for the AI-Native TPM role -- writing "
            "separately because PM and TPM in a team like this are the same problem-solving "
            "persona on different days. 10+ years shipping across AI/ML, IoT, and hardware. "
            "Built AI agent system at Wolt from scratch, drove 200+ live demos at CloudMade, "
            "shipped Ring Ultra to 800k-2M units. I learn tools, frameworks, and measurement "
            "systems on the fly. The work is the same. Frankfurt-based, immediately available."
        ),
    },
    "deepl-sr-technical-pm-ai": {
        "filename": "user-deepl-cv",
        "summary": (
            "I sit between research teams that want to experiment forever and engineering teams "
            "that need to ship yesterday. At Alexa AGI, ran ASR deployment across Seattle, Aachen, "
            "and Bangalore -- cut release SLA from multi-day to 1 business day. Worked on EverLearn, "
            "a continuous-learning ML framework made obsolete when LLMs arrived. I don't speculate "
            "about AI disruption; I've been disrupted. Built AI-augmented program system at Wolt "
            "from scratch -- 6 LLMs, 4 enterprise APIs, no ticket, no budget. Shipped Ring Ultra "
            "radar camera to 800k-2M units. I care about European AI sovereignty -- not as a slogan, "
            "but as someone who stood at Maidan in 2013. Working across Europe since 2016, currently "
            "in Frankfurt."
        ),
    },
    "ashby-sr-swe-product-eng": {
        "filename": "user-ashby-cv",
        "summary": (
            "Builder crossing from TPM into product engineering via AI tools. Built an AI agent "
            "operating system at Wolt -- 15+ Python scripts, 6 LLMs, 4 enterprise APIs, persistent "
            "context, custom enterprise search CLI, AI provenance tracking. End-to-end ownership: "
            "I research, spec, wireframe, build, and ship. Shipped Ring Ultra across 10+ teams in "
            "5 countries. Built CloudMade demo car fleet from nothing -- 200+ live demos. "
            "High ownership, minimal process, product thinking built from a decade of shipping."
        ),
    },
    "attio-product-engineer": {
        "filename": "user-attio-cv",
        "summary": (
            "CRM data platform owner. Wolt: Pipedrive-to-Salesforce amid DoorDash/Deliveroo "
            "acquisition -- custom objects, permissions models, SOX-compliant connectors, MongoDB "
            "audit logging. 12+ stakeholders, 3 merging companies, hundreds of millions in revenue "
            "running blind without proper infrastructure. Built AI agent system in parallel -- 6 LLMs, "
            "enterprise APIs, 1,140-file document registry. I think about data models instinctively "
            "because I've had to build them. Founder mentality. Germany remote."
        ),
    },
    "mistral-tpm-science-ops": {
        "filename": "user-mistral-science-cv",
        "summary": (
            "Execution engine builder for research-to-production pipelines. Ran ASR model "
            "deployment at Alexa across 3 continents -- bridging Science and Engineering, cutting "
            "release SLA from multi-day to 1 business day. Split Ring's monolithic AWS account "
            "into 25 independently certified services -- 30 weeks ahead of schedule, zero downtime. "
            "Built AI-augmented program system at Wolt with persistent context, automated synthesis, "
            "and retrospective-ready data capture. The pattern: structure ambiguity into coordinated "
            "execution without killing the science."
        ),
    },
    "mistral-tpm-engineering": {
        "filename": "user-mistral-eng-cv",
        "summary": (
            "10+ years driving cross-functional technical delivery at scale. 7 years at Amazon: "
            "shipped Ring Ultra radar camera to 800k-2M units across 10+ teams in 5 countries, "
            "split monolithic AWS account into 25 certified services 30 weeks ahead of schedule, "
            "ran ASR model deployment at Alexa across 3 continents. At Wolt: managed Salesforce "
            "CRM migration with 12+ stakeholders, built AI-augmented program system from scratch. "
            "Development and deployment process ownership. Technical depth to sit in architecture "
            "reviews and add value."
        ),
    },
    "gitlab-sr-tpm-cto": {
        "filename": "user-gitlab-cv",
        "summary": (
            "Async-first TPM who writes documentation because it's how organizations remember "
            "what they decided and why. 10+ years running cross-functional programs across "
            "Engineering, Product, Finance, and Legal. Wolt: CRM transformation amid "
            "DoorDash/Deliveroo acquisition, 12+ stakeholders, built AI system with 1,140-file "
            "document registry as a living handbook. Ring: split monolithic AWS into 25 certified "
            "services, 30 weeks ahead. Alexa: ML deployment across 3 continents. I build tools, "
            "automate mechanical work, and care about sustainable teams. Frankfurt, remote-ready."
        ),
    },
    "huggingface-ai-ml-pm": {
        "filename": "user-huggingface-cv",
        "summary": (
            "Drove $1M+ partner deals by building things, not slide decks. CloudMade: 5 demo "
            "cars, 200+ live drives to OEM executives across 3 continents, 5x sales engagement. "
            "Wolt: CRM transformation across 3 merging companies, 12+ stakeholders. Alexa: ML "
            "deployment across Seattle, Aachen, Bangalore. I care about open-source AI and "
            "European sovereignty -- not as a slogan, as someone who stood at Maidan in 2013. "
            "15+ Python tools, AI agent systems, API integrations. I sit in the room with the "
            "partner's ML team and add value. Frankfurt, EMEA remote."
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
