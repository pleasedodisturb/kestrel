import json, subprocess, sys

result = subprocess.run(
    ['.venv/bin/python', 'tools/germany_jobs.py', '--preset', 'all', '--location', 'Frankfurt', '--limit', '25', '--output', 'json'],
    capture_output=True, text=True
)

jobs = json.loads(result.stdout.strip())
good = sorted([j for j in jobs if j.get('score', 0) >= 2], key=lambda x: -x.get('score', 0))

for j in good:
    stars = j.get('score', 0)
    print(f"{stars}pts | {j['title']} | {j['company']} | {j['location']} | {j.get('url','')}")

print("---")
print(f"Total scraped: {len(jobs)} | Score>=2: {len(good)}", file=sys.stderr)
