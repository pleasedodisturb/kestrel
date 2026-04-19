import asyncio
import sys

import pandas as pd
from jobspy import scrape_jobs

# Define our targeted search groups
SEARCHES = [
    # 1. Automotive / HCI
    {
        "term": "Product Manager automotive connected car HCI",
        "location": "Germany",
        "results": 10,
        "group": "Automotive/HCI",
    },
    # 2. IoT / Robotics / Wearables
    {
        "term": "Product Manager IoT robotics wearables",
        "location": "Germany",
        "results": 10,
        "group": "IoT/Robotics",
    },
    # 3. Food Delivery / Logistics
    {
        "term": "Product Manager food delivery Delivery Hero Flink",
        "location": "Germany",
        "results": 10,
        "group": "Food Delivery",
    },
    # 4. MongoDB specific
    {"term": "MongoDB Product Manager", "location": "Germany", "results": 5, "group": "MongoDB"},
]


async def run_searches():
    all_jobs = []

    for s in SEARCHES:
        print(f"Searching: {s['term']}...", file=sys.stderr)
        try:
            jobs = scrape_jobs(
                site_name=["linkedin", "indeed"],
                search_term=s["term"],
                location=s["location"],
                results_wanted=s["results"],
                country_indeed="Germany",
                hours_old=168,  # Last 7 days
            )

            if not jobs.empty:
                # Add group label
                jobs["search_group"] = s["group"]
                # Convert date objects to string
                if "date_posted" in jobs.columns:
                    jobs["date_posted"] = jobs["date_posted"].astype(str)

                all_jobs.append(jobs)
        except Exception as e:
            print(f"Error in {s['group']}: {e}", file=sys.stderr)

    if all_jobs:
        combined = pd.concat(all_jobs, ignore_index=True)
        # Select relevant columns
        cols = [
            "title",
            "company",
            "location",
            "job_url",
            "description",
            "date_posted",
            "search_group",
            "is_remote",
        ]
        # Handle missing columns gracefully
        existing_cols = [c for c in cols if c in combined.columns]

        # Output clean JSON
        print(combined[existing_cols].to_json(orient="records"))
    else:
        print("[]")


if __name__ == "__main__":
    asyncio.run(run_searches())
