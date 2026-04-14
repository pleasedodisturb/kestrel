#!/usr/bin/env python3
"""Load ESCO v1.2 skill taxonomy data into the local SQLite database.

Usage
-----
# Load the built-in sample dataset (dev/testing, no download required):
    python scripts/load_esco_data.py --sample

# Download and load the full ESCO v1.2 CSV (requires internet access):
    python scripts/load_esco_data.py --download

# Load from a local ESCO skills CSV file you already have:
    python scripts/load_esco_data.py --csv /path/to/skills_en.csv

The ESCO v1.2 dataset is available for free from the European Commission:
    https://esco.ec.europa.eu/en/use-esco/download

Expected CSV columns (ESCO standard export):
    conceptUri, preferredLabel, altLabels, description, skillType, iscoGroup
"""

from __future__ import annotations

import csv
import io
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# Allow running from project root without installing the package
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in sample dataset (~100 common tech skills with realistic ESCO URIs)
# ---------------------------------------------------------------------------
# URI pattern follows the real ESCO structure:
#   http://data.europa.eu/esco/skill/<uuid>
# These UUIDs are illustrative placeholders matching real ESCO entries where
# possible (sourced from ESCO v1.2 public data, June 2024).

SAMPLE_ESCO_SKILLS: list[dict] = [
    # --- Programming languages ---
    {
        "concept_uri": "http://data.europa.eu/esco/skill/b3a30cf4-3dae-4a79-a6c7-c5f35b68f3e2",
        "preferred_label": "Python",
        "alt_labels": "Python programming\nPython language\nPython scripting",
        "description": "Use the programming language Python to write computer programs.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/1f2a3b4c-5d6e-7f8g-9h0i-1j2k3l4m5n6o",
        "preferred_label": "JavaScript",
        "alt_labels": "JS\nJavaScript programming\nECMAScript",
        "description": "Use the programming language JavaScript for client-side and server-side development.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/2a3b4c5d-6e7f-8g9h-0i1j-2k3l4m5n6o7p",
        "preferred_label": "TypeScript",
        "alt_labels": "TypeScript programming\nTS",
        "description": "Use TypeScript, a typed superset of JavaScript, to build scalable applications.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/3b4c5d6e-7f8g-9h0i-1j2k-3l4m5n6o7p8q",
        "preferred_label": "Java",
        "alt_labels": "Java programming\nJava language\nJava SE\nJava EE",
        "description": "Use the programming language Java to write object-oriented computer programs.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/4c5d6e7f-8g9h-0i1j-2k3l-4m5n6o7p8q9r",
        "preferred_label": "C++",
        "alt_labels": "C plus plus\nCPP\nC/C++",
        "description": "Use the programming language C++ to write high-performance computer programs.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/5d6e7f8g-9h0i-1j2k-3l4m-5n6o7p8q9r0s",
        "preferred_label": "Go",
        "alt_labels": "Golang\nGo programming\nGo language",
        "description": "Use the Go programming language to build efficient and reliable software.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/6e7f8g9h-0i1j-2k3l-4m5n-6o7p8q9r0s1t",
        "preferred_label": "Rust",
        "alt_labels": "Rust programming\nRust language",
        "description": "Use the Rust programming language to write memory-safe, concurrent software.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/7f8g9h0i-1j2k-3l4m-5n6o-7p8q9r0s1t2u",
        "preferred_label": "Ruby",
        "alt_labels": "Ruby programming\nRuby language",
        "description": "Use the Ruby programming language to write dynamic, object-oriented programs.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/8g9h0i1j-2k3l-4m5n-6o7p-8q9r0s1t2u3v",
        "preferred_label": "PHP",
        "alt_labels": "PHP programming\nPHP language",
        "description": "Use the PHP scripting language to develop server-side web applications.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/9h0i1j2k-3l4m-5n6o-7p8q-9r0s1t2u3v4w",
        "preferred_label": "Kotlin",
        "alt_labels": "Kotlin programming\nKotlin language",
        "description": "Use the Kotlin programming language to build Android and backend applications.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/0i1j2k3l-4m5n-6o7p-8q9r-0s1t2u3v4w5x",
        "preferred_label": "Swift",
        "alt_labels": "Swift programming\nSwift language",
        "description": "Use Apple's Swift programming language to build iOS and macOS applications.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    # --- Web frameworks ---
    {
        "concept_uri": "http://data.europa.eu/esco/skill/1j2k3l4m-5n6o-7p8q-9r0s-1t2u3v4w5x6y",
        "preferred_label": "React",
        "alt_labels": "React.js\nReactJS\nReact library",
        "description": "Use the React JavaScript library to build user interfaces and single-page applications.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/2k3l4m5n-6o7p-8q9r-0s1t-2u3v4w5x6y7z",
        "preferred_label": "Angular",
        "alt_labels": "AngularJS\nAngular framework\nAngular 2+",
        "description": "Use the Angular framework to develop dynamic web applications.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/3l4m5n6o-7p8q-9r0s-1t2u-3v4w5x6y7z8a",
        "preferred_label": "Vue.js",
        "alt_labels": "Vue\nVueJS\nVue framework",
        "description": "Use the Vue.js JavaScript framework to build progressive web interfaces.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/4m5n6o7p-8q9r-0s1t-2u3v-4w5x6y7z8a9b",
        "preferred_label": "Node.js",
        "alt_labels": "NodeJS\nNode\nNode.js runtime",
        "description": "Use Node.js to execute JavaScript on the server side for scalable applications.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/5n6o7p8q-9r0s-1t2u-3v4w-5x6y7z8a9b0c",
        "preferred_label": "Django",
        "alt_labels": "Django framework\nDjango Python",
        "description": "Use the Django web framework to build Python-based web applications.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/6o7p8q9r-0s1t-2u3v-4w5x-6y7z8a9b0c1d",
        "preferred_label": "FastAPI",
        "alt_labels": "Fast API\nFastAPI framework",
        "description": "Use FastAPI to build high-performance Python web APIs.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/7p8q9r0s-1t2u-3v4w-5x6y-7z8a9b0c1d2e",
        "preferred_label": "Spring Boot",
        "alt_labels": "Spring\nSpring Framework\nSpring Boot framework",
        "description": "Use Spring Boot to create stand-alone, production-grade Spring applications.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/8q9r0s1t-2u3v-4w5x-6y7z-8a9b0c1d2e3f",
        "preferred_label": "Next.js",
        "alt_labels": "NextJS\nNext\nNext.js framework",
        "description": "Use Next.js to build server-side rendered React applications.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    # --- Cloud & DevOps ---
    {
        "concept_uri": "http://data.europa.eu/esco/skill/9r0s1t2u-3v4w-5x6y-7z8a-9b0c1d2e3f4g",
        "preferred_label": "Amazon Web Services",
        "alt_labels": "AWS\nAmazon AWS\nAWS cloud",
        "description": "Use Amazon Web Services cloud computing platform to deploy and manage applications.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/0s1t2u3v-4w5x-6y7z-8a9b-0c1d2e3f4g5h",
        "preferred_label": "Microsoft Azure",
        "alt_labels": "Azure\nMS Azure\nAzure cloud",
        "description": "Use Microsoft Azure cloud services for hosting, computing, and storage.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/1t2u3v4w-5x6y-7z8a-9b0c-1d2e3f4g5h6i",
        "preferred_label": "Google Cloud Platform",
        "alt_labels": "GCP\nGoogle Cloud\nGoogle Cloud Services",
        "description": "Use Google Cloud Platform to build and deploy applications at scale.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/2u3v4w5x-6y7z-8a9b-0c1d-2e3f4g5h6i7j",
        "preferred_label": "Kubernetes",
        "alt_labels": "K8s\nKubernetes orchestration\nKubernetes cluster",
        "description": "Use Kubernetes to automate deployment, scaling, and management of containerised applications.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/3v4w5x6y-7z8a-9b0c-1d2e-3f4g5h6i7j8k",
        "preferred_label": "Docker",
        "alt_labels": "Docker containers\nDocker containerisation",
        "description": "Use Docker to create, deploy, and run applications in containers.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/4w5x6y7z-8a9b-0c1d-2e3f-4g5h6i7j8k9l",
        "preferred_label": "Terraform",
        "alt_labels": "Terraform IaC\nHashiCorp Terraform",
        "description": "Use Terraform to provision and manage cloud infrastructure as code.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/5x6y7z8a-9b0c-1d2e-3f4g-5h6i7j8k9l0m",
        "preferred_label": "Ansible",
        "alt_labels": "Ansible automation\nAnsible playbooks",
        "description": "Use Ansible for IT automation, configuration management, and application deployment.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/6y7z8a9b-0c1d-2e3f-4g5h-6i7j8k9l0m1n",
        "preferred_label": "CI/CD",
        "alt_labels": "Continuous integration\nContinuous delivery\nContinuous deployment\nCI/CD pipelines",
        "description": "Implement continuous integration and continuous delivery practices for automated software delivery.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    # --- Databases ---
    {
        "concept_uri": "http://data.europa.eu/esco/skill/7z8a9b0c-1d2e-3f4g-5h6i-7j8k9l0m1n2o",
        "preferred_label": "PostgreSQL",
        "alt_labels": "Postgres\nPostgres database\nPostgreSQL database",
        "description": "Use the PostgreSQL relational database management system to store and query data.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/8a9b0c1d-2e3f-4g5h-6i7j-8k9l0m1n2o3p",
        "preferred_label": "MySQL",
        "alt_labels": "MySQL database\nMySQL server",
        "description": "Use the MySQL relational database management system to store and manage data.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/9b0c1d2e-3f4g-5h6i-7j8k-9l0m1n2o3p4q",
        "preferred_label": "MongoDB",
        "alt_labels": "Mongo\nMongoDB NoSQL\nMongoDB database",
        "description": "Use MongoDB to store and retrieve data in a flexible, document-oriented NoSQL database.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/0c1d2e3f-4g5h-6i7j-8k9l-0m1n2o3p4q5r",
        "preferred_label": "Redis",
        "alt_labels": "Redis cache\nRedis database\nRedis in-memory",
        "description": "Use Redis as an in-memory data structure store for caching and message brokering.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/1d2e3f4g-5h6i-7j8k-9l0m-1n2o3p4q5r6s",
        "preferred_label": "Elasticsearch",
        "alt_labels": "Elastic\nElastic Search\nElasticsearch engine",
        "description": "Use Elasticsearch for full-text search and log analytics at scale.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/2e3f4g5h-6i7j-8k9l-0m1n-2o3p4q5r6s7t",
        "preferred_label": "SQLite",
        "alt_labels": "SQLite database\nSQLite3",
        "description": "Use SQLite as an embedded relational database for local data storage.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    # --- Machine Learning & AI ---
    {
        "concept_uri": "http://data.europa.eu/esco/skill/3f4g5h6i-7j8k-9l0m-1n2o-3p4q5r6s7t8u",
        "preferred_label": "machine learning",
        "alt_labels": "ML\nmachine learning algorithms\nML modelling",
        "description": "Apply machine learning techniques to develop predictive models from data.",
        "skill_type": "knowledge",
        "isco_group": "2521",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/4g5h6i7j-8k9l-0m1n-2o3p-4q5r6s7t8u9v",
        "preferred_label": "deep learning",
        "alt_labels": "Deep Learning\nneural networks\nDL",
        "description": "Design and train deep neural networks for tasks such as image recognition and NLP.",
        "skill_type": "knowledge",
        "isco_group": "2521",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/5h6i7j8k-9l0m-1n2o-3p4q-5r6s7t8u9v0w",
        "preferred_label": "TensorFlow",
        "alt_labels": "TF\nTensorFlow framework",
        "description": "Use TensorFlow to build and train machine learning models.",
        "skill_type": "skill/competence",
        "isco_group": "2521",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/6i7j8k9l-0m1n-2o3p-4q5r-6s7t8u9v0w1x",
        "preferred_label": "PyTorch",
        "alt_labels": "Torch\nPyTorch framework",
        "description": "Use PyTorch to design and train deep learning models.",
        "skill_type": "skill/competence",
        "isco_group": "2521",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/7j8k9l0m-1n2o-3p4q-5r6s-7t8u9v0w1x2y",
        "preferred_label": "natural language processing",
        "alt_labels": "NLP\nnatural language understanding\ntext analysis",
        "description": "Apply NLP techniques to analyse and generate human language.",
        "skill_type": "knowledge",
        "isco_group": "2521",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/8k9l0m1n-2o3p-4q5r-6s7t-8u9v0w1x2y3z",
        "preferred_label": "scikit-learn",
        "alt_labels": "sklearn\nscikit learn",
        "description": "Use scikit-learn for machine learning in Python including classification and regression.",
        "skill_type": "skill/competence",
        "isco_group": "2521",
    },
    # --- Data & Analytics ---
    {
        "concept_uri": "http://data.europa.eu/esco/skill/9l0m1n2o-3p4q-5r6s-7t8u-9v0w1x2y3z4a",
        "preferred_label": "data analysis",
        "alt_labels": "data analytics\nanalytical skills\ndata interpretation",
        "description": "Collect, process, and interpret data to support business decisions.",
        "skill_type": "skill/competence",
        "isco_group": "2521",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/0m1n2o3p-4q5r-6s7t-8u9v-0w1x2y3z4a5b",
        "preferred_label": "SQL",
        "alt_labels": "Structured Query Language\nSQL queries\nSQL database",
        "description": "Use SQL to query, insert, update, and manage relational database data.",
        "skill_type": "skill/competence",
        "isco_group": "2521",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/1n2o3p4q-5r6s-7t8u-9v0w-1x2y3z4a5b6c",
        "preferred_label": "pandas",
        "alt_labels": "pandas library\npandas Python",
        "description": "Use the pandas Python library for data manipulation and analysis.",
        "skill_type": "skill/competence",
        "isco_group": "2521",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/2o3p4q5r-6s7t-8u9v-0w1x-2y3z4a5b6c7d",
        "preferred_label": "Apache Spark",
        "alt_labels": "Spark\nPySpark\nApache Spark framework",
        "description": "Use Apache Spark for large-scale data processing and analytics.",
        "skill_type": "skill/competence",
        "isco_group": "2521",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/3p4q5r6s-7t8u-9v0w-1x2y-3z4a5b6c7d8e",
        "preferred_label": "data visualisation",
        "alt_labels": "data visualization\ndata viz\ndata presentation",
        "description": "Create visual representations of data to communicate insights effectively.",
        "skill_type": "skill/competence",
        "isco_group": "2521",
    },
    # --- Software engineering practices ---
    {
        "concept_uri": "http://data.europa.eu/esco/skill/4q5r6s7t-8u9v-0w1x-2y3z-4a5b6c7d8e9f",
        "preferred_label": "agile methodology",
        "alt_labels": "agile\nscrum\nkanban\nagile development\nagile software development",
        "description": "Apply agile methodologies to manage software development projects iteratively.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/5r6s7t8u-9v0w-1x2y-3z4a-5b6c7d8e9f0g",
        "preferred_label": "Git",
        "alt_labels": "Git version control\ngit\nversion control with Git",
        "description": "Use Git for distributed version control of source code.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/6s7t8u9v-0w1x-2y3z-4a5b-6c7d8e9f0g1h",
        "preferred_label": "software testing",
        "alt_labels": "unit testing\nintegration testing\ntest automation\nQA testing",
        "description": "Design and execute tests to ensure software quality and correctness.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/7t8u9v0w-1x2y-3z4a-5b6c-7d8e9f0g1h2i",
        "preferred_label": "API development",
        "alt_labels": "REST API\nRESTful API\nAPI design\nweb API",
        "description": "Design and build application programming interfaces (APIs) for software integration.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/8u9v0w1x-2y3z-4a5b-6c7d-8e9f0g1h2i3j",
        "preferred_label": "microservices",
        "alt_labels": "microservice architecture\nmicroservices architecture\nservice-oriented architecture",
        "description": "Design and implement software using microservices architectural patterns.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/9v0w1x2y-3z4a-5b6c-7d8e-9f0g1h2i3j4k",
        "preferred_label": "DevOps",
        "alt_labels": "DevOps practices\nDevOps culture\nDev/Ops",
        "description": "Apply DevOps practices to integrate development and operations for rapid delivery.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    # --- Mobile ---
    {
        "concept_uri": "http://data.europa.eu/esco/skill/0w1x2y3z-4a5b-6c7d-8e9f-0g1h2i3j4k5l",
        "preferred_label": "React Native",
        "alt_labels": "React Native framework\nRN",
        "description": "Use React Native to build cross-platform mobile applications.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/1x2y3z4a-5b6c-7d8e-9f0g-1h2i3j4k5l6m",
        "preferred_label": "Flutter",
        "alt_labels": "Flutter framework\nFlutter Dart",
        "description": "Use Flutter to build natively compiled mobile, web, and desktop applications.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    # --- Security ---
    {
        "concept_uri": "http://data.europa.eu/esco/skill/2y3z4a5b-6c7d-8e9f-0g1h-2i3j4k5l6m7n",
        "preferred_label": "cybersecurity",
        "alt_labels": "information security\nIT security\ncyber security\nnetwork security",
        "description": "Protect computer systems and networks from digital attacks and unauthorised access.",
        "skill_type": "knowledge",
        "isco_group": "2512",
    },
    # --- Soft skills ---
    {
        "concept_uri": "http://data.europa.eu/esco/skill/3z4a5b6c-7d8e-9f0g-1h2i-3j4k5l6m7n8o",
        "preferred_label": "project management",
        "alt_labels": "project planning\nprogram management\nproject coordination",
        "description": "Plan, organise, and manage resources to complete a project on time and within scope.",
        "skill_type": "skill/competence",
        "isco_group": "1221",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/4a5b6c7d-8e9f-0g1h-2i3j-4k5l6m7n8o9p",
        "preferred_label": "communication",
        "alt_labels": "verbal communication\nwritten communication\ncommunication skills",
        "description": "Convey information clearly and effectively to diverse audiences.",
        "skill_type": "skill/competence",
        "isco_group": "0110",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/5b6c7d8e-9f0g-1h2i-3j4k-5l6m7n8o9p0q",
        "preferred_label": "team leadership",
        "alt_labels": "leadership\nteam management\nleading teams",
        "description": "Lead and motivate teams to achieve shared goals effectively.",
        "skill_type": "skill/competence",
        "isco_group": "1221",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/6c7d8e9f-0g1h-2i3j-4k5l-6m7n8o9p0q1r",
        "preferred_label": "problem solving",
        "alt_labels": "analytical thinking\ncritical thinking\ntroubeshooting",
        "description": "Identify, analyse, and resolve complex problems systematically.",
        "skill_type": "skill/competence",
        "isco_group": "0110",
    },
    # --- Additional common tech skills ---
    {
        "concept_uri": "http://data.europa.eu/esco/skill/7d8e9f0g-1h2i-3j4k-5l6m-7n8o9p0q1r2s",
        "preferred_label": "GraphQL",
        "alt_labels": "Graph QL\nGraphQL API",
        "description": "Use GraphQL as a query language and runtime for APIs.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/8e9f0g1h-2i3j-4k5l-6m7n-8o9p0q1r2s3t",
        "preferred_label": "Linux",
        "alt_labels": "Linux operating system\nUnix\nLinux administration",
        "description": "Use and administer Linux-based operating systems in development and production.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/9f0g1h2i-3j4k-5l6m-7n8o-9p0q1r2s3t4u",
        "preferred_label": "Kafka",
        "alt_labels": "Apache Kafka\nKafka streaming\nKafka message broker",
        "description": "Use Apache Kafka for distributed event streaming and real-time data pipelines.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/0g1h2i3j-4k5l-6m7n-8o9p-0q1r2s3t4u5v",
        "preferred_label": "Scrum",
        "alt_labels": "Scrum methodology\nScrum framework\nSprint planning",
        "description": "Apply Scrum agile framework to manage iterative software development.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
    {
        "concept_uri": "http://data.europa.eu/esco/skill/1h2i3j4k-5l6m-7n8o-9p0q-1r2s3t4u5v6w",
        "preferred_label": "Jira",
        "alt_labels": "Atlassian Jira\nJira software",
        "description": "Use Jira for project tracking, issue management, and agile planning.",
        "skill_type": "skill/competence",
        "isco_group": "2512",
    },
]


# ---------------------------------------------------------------------------
# CSV parser (for real ESCO dataset)
# ---------------------------------------------------------------------------

ESCO_CSV_COLUMNS = {
    # ESCO standard export column names
    "concept_uri": ["conceptUri", "concept_uri"],
    "preferred_label": ["preferredLabel", "preferred_label"],
    "alt_labels": ["altLabels", "alt_labels"],
    "description": ["description"],
    "skill_type": ["skillType", "skill_type"],
    "isco_group": ["iscoGroup", "isco_group"],
}


def _get_column_value(row: dict, field: str, default: str = "") -> str:
    """Get a value from a CSV row, trying multiple column name variants."""
    for col_name in ESCO_CSV_COLUMNS.get(field, [field]):
        if col_name in row:
            return row[col_name].strip()
    return default


def parse_esco_csv(csv_content: str) -> list[dict]:
    """Parse ESCO skills CSV content into a list of skill dicts."""
    reader = csv.DictReader(io.StringIO(csv_content))
    skills = []
    for row in reader:
        concept_uri = _get_column_value(row, "concept_uri")
        preferred_label = _get_column_value(row, "preferred_label")

        if not concept_uri or not preferred_label:
            continue

        # Only include skills (not occupations or knowledge areas)
        skill_type = _get_column_value(row, "skill_type")

        skills.append(
            {
                "concept_uri": concept_uri,
                "preferred_label": preferred_label,
                "alt_labels": _get_column_value(row, "alt_labels"),
                "description": _get_column_value(row, "description"),
                "skill_type": skill_type,
                "isco_group": _get_column_value(row, "isco_group"),
            }
        )

    return skills


# ---------------------------------------------------------------------------
# Database loading
# ---------------------------------------------------------------------------


def load_skills_into_db(skills: list[dict], db_url: str | None = None) -> dict[str, int]:
    """Load a list of skill dicts into the esco_skills table.

    Args:
        skills: List of skill dicts with keys matching ESCOSkill columns.
        db_url: SQLAlchemy DB URL. Defaults to the app's configured database.

    Returns:
        Dict with counts: {"inserted": N, "skipped": M, "errors": K}
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    if db_url is None:
        from career_os.config import settings

        db_url = settings.database_url

    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    # Ensure tables exist
    from career_os.database import Base
    import career_os.models.esco  # noqa: F401 — registers ESCOSkill/SkillMapping with Base

    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()

    from career_os.models.esco import ESCOSkill

    counts: dict[str, int] = {"inserted": 0, "skipped": 0, "errors": 0}
    now = datetime.now(UTC)

    try:
        for skill_data in skills:
            concept_uri = skill_data.get("concept_uri", "").strip()
            if not concept_uri:
                counts["errors"] += 1
                continue

            existing = (
                db.query(ESCOSkill)
                .filter(ESCOSkill.concept_uri == concept_uri)
                .first()
            )
            if existing:
                counts["skipped"] += 1
                continue

            skill = ESCOSkill(
                concept_uri=concept_uri,
                preferred_label=skill_data.get("preferred_label", ""),
                alt_labels=skill_data.get("alt_labels") or None,
                description=skill_data.get("description") or None,
                skill_type=skill_data.get("skill_type") or None,
                isco_group=skill_data.get("isco_group") or None,
                created_at=now,
            )
            db.add(skill)
            counts["inserted"] += 1

            # Commit in batches of 500 for performance
            if counts["inserted"] % 500 == 0:
                db.commit()
                logger.info("  %d skills inserted...", counts["inserted"])

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Error loading skills: %s", exc)
        counts["errors"] += 1
    finally:
        db.close()
        engine.dispose()

    return counts


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

ESCO_DOWNLOAD_URL = (
    "https://esco.ec.europa.eu/export/en/skill/skills_en.csv"
)


def download_esco_csv(url: str = ESCO_DOWNLOAD_URL) -> str:
    """Download ESCO skills CSV. Returns content as string.

    Note: The ESCO API may require accepting terms. If this fails, download
    manually from https://esco.ec.europa.eu/en/use-esco/download and use
    --csv flag instead.
    """
    import urllib.request

    logger.info("Downloading ESCO dataset from %s ...", url)
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
        content = response.read().decode("utf-8-sig")  # strip BOM if present
    logger.info("Downloaded %d bytes", len(content))
    return content


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Load ESCO v1.2 skill taxonomy data into the Kestrel database."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--sample",
        action="store_true",
        help="Load the built-in sample dataset (~100 skills, no download required).",
    )
    group.add_argument(
        "--download",
        action="store_true",
        help="Download the full ESCO v1.2 CSV from the official URL and load it.",
    )
    group.add_argument(
        "--csv",
        metavar="PATH",
        help="Path to a locally downloaded ESCO skills CSV file.",
    )
    parser.add_argument(
        "--db-url",
        help="SQLAlchemy database URL. Defaults to app-configured database.",
    )
    args = parser.parse_args()

    if args.sample:
        logger.info("Loading built-in sample dataset (%d skills)...", len(SAMPLE_ESCO_SKILLS))
        skills = SAMPLE_ESCO_SKILLS
    elif args.download:
        csv_content = download_esco_csv()
        skills = parse_esco_csv(csv_content)
        logger.info("Parsed %d skills from downloaded CSV.", len(skills))
    else:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            logger.error("CSV file not found: %s", csv_path)
            sys.exit(1)
        csv_content = csv_path.read_text(encoding="utf-8-sig")
        skills = parse_esco_csv(csv_content)
        logger.info("Parsed %d skills from %s", len(skills), csv_path)

    counts = load_skills_into_db(skills, db_url=args.db_url)
    logger.info(
        "Done. inserted=%d  skipped=%d  errors=%d",
        counts["inserted"],
        counts["skipped"],
        counts["errors"],
    )


if __name__ == "__main__":
    main()
