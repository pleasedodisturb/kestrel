#!/usr/bin/env python3
"""Create a rich, standard-compliant Linear ticket from the @claude intake bot.

Reads Claude's structured output (STRUCTURED env) plus GitHub context, then
creates a team-G ticket with project, labels (incl. route/*), priority, estimate,
a full 7-section body + preliminary plan, links the source issue/PR as an
attachment, and relates any referenced Linear tickets. Stdlib only.
"""
import json, os, re, sys, urllib.request, urllib.error

API = "https://api.linear.app/graphql"
TOKEN = os.environ["LINEAR_API_TOKEN"]


def gql(query, variables=None):
    data = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        API, data=data,
        headers={"Authorization": TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.load(r)
    if out.get("errors"):
        print("Linear API errors:", json.dumps(out["errors"])[:500], file=sys.stderr)
    return out.get("data") or {}


def md_section(title, body):
    return f"## {title}\n\n{body}\n\n" if body else ""


def md_list(title, items):
    if not items:
        return ""
    rows = "\n".join(f"- {i if isinstance(i, str) else json.dumps(i)}" for i in items)
    return f"## {title}\n\n{rows}\n\n"


def md_ordered(title, items):
    if not items:
        return ""
    rows = "\n".join(f"{i+1}. {c}" for i, c in enumerate(items))
    return f"## {title}\n\n{rows}\n\n"


def main():
    s = json.loads(os.environ["STRUCTURED"])
    repo = os.environ.get("REPO", "")
    src_url = os.environ.get("REQ_URL", "")
    src_title = os.environ.get("REQ_TITLE", "")

    # --- resolve team G + its labels ---
    team = gql('{ teams(filter:{key:{eq:"G"}}){ nodes{ id labels{ nodes{ id name parent{ name } } } } } }')
    tnode = team["teams"]["nodes"][0]
    team_id = tnode["id"]
    label_index = {}
    for l in tnode["labels"]["nodes"]:
        label_index[l["name"].lower()] = l["id"]
        if l.get("parent"):
            label_index[f'{l["parent"]["name"].lower()}/{l["name"].lower()}'] = l["id"]

    # --- map suggested labels (existing only) ---
    label_ids, unmatched_labels = [], []
    for name in (s.get("labels") or []):
        key = name.strip().lower()
        lid = label_index.get(key) or label_index.get(key.split("/")[-1])
        (label_ids.append(lid) if lid else unmatched_labels.append(name))

    # --- map project by name (fuzzy contains) ---
    project_id, project_note = None, ""
    want = (s.get("project") or "").strip().lower()
    if want and want != "standalone":
        projs = gql("{ projects(first:200){ nodes{ id name } } }")["projects"]["nodes"]
        for p in projs:
            if want == p["name"].lower() or want in p["name"].lower() or p["name"].lower() in want:
                project_id = p["id"]; break
        if not project_id:
            project_note = f'_Suggested project: **{s.get("project")}** (no exact match — set manually)._'

    # --- build description body (7 sections + plan + metadata) ---
    files = s.get("files_to_modify") or []
    body = ""
    body += md_section("Problem / Goal", s.get("problem_goal", ""))
    body += md_section("Context", s.get("context", ""))
    body += md_ordered("Acceptance Criteria", s.get("acceptance_criteria") or [])
    body += md_ordered("Preliminary Plan", s.get("preliminary_plan") or [])
    body += md_list("Verification Commands", [f"`{c}`" for c in (s.get("verification_commands") or [])])
    if files:
        rows = "\n".join(f"- `{f.get('path', f)}` — {f.get('what','')}" if isinstance(f, dict) else f"- `{f}`" for f in files)
        body += f"## Files to Investigate / Modify\n\n{rows}\n\n"
    body += md_list("Constraints", s.get("constraints"))
    body += md_list("Root-cause Hypotheses", s.get("root_cause_hypotheses"))
    body += md_list("Definition of Done", s.get("definition_of_done"))
    body += md_section("Tests", s.get("tests_required"))
    # execution metadata
    meta = []
    for k, label in [("scope", "Scope"), ("parallel_safe", "Parallel-safe"), ("worktree", "Worktree")]:
        if s.get(k) is not None:
            meta.append(f"- **{label}:** {s[k]}")
    if meta:
        body += "## Execution Metadata\n\n" + "\n".join(meta) + "\n\n"
    # related
    rel = []
    for u in (s.get("related_github") or []):
        rel.append(f"- {u}")
    for g in (s.get("related_linear") or []):
        rel.append(f"- {g}")
    if rel:
        body += "## Related\n\n" + "\n".join(rel) + "\n\n"
    if unmatched_labels:
        body += f"_Unmatched suggested labels: {', '.join(unmatched_labels)}._\n\n"
    if project_note:
        body += project_note + "\n\n"
    body += f"---\n_Intake by the @claude bot in `{repo}` from {src_url}. Review and refine before assigning._"

    # --- create the issue ---
    inp = {"teamId": team_id, "title": s["title"], "description": body}
    if project_id:
        inp["projectId"] = project_id
    if label_ids:
        inp["labelIds"] = label_ids
    if isinstance(s.get("priority"), int):
        inp["priority"] = s["priority"]
    if isinstance(s.get("estimate"), int):
        inp["estimate"] = s["estimate"]
    res = gql(
        "mutation($i:IssueCreateInput!){ issueCreate(input:$i){ issue{ id identifier url } } }",
        {"i": inp})
    issue = res["issueCreate"]["issue"]
    iid, identifier, iurl = issue["id"], issue["identifier"], issue["url"]
    print(f"Created {identifier} -> {iurl}")

    # --- attach the source GitHub issue/PR ---
    try:
        if src_url:
            gql("mutation($i:AttachmentCreateInput!){ attachmentCreate(input:$i){ success } }",
                {"i": {"issueId": iid, "title": f"GitHub: {src_title}"[:60], "url": src_url}})
    except Exception as e:
        print("attachment skipped:", e, file=sys.stderr)

    # --- relate referenced Linear tickets ---
    for g in (s.get("related_linear") or []):
        m = re.match(r"[A-Za-z]+-(\d+)", g.strip())
        if not m:
            continue
        try:
            q = gql('query($n:Float){ issues(filter:{team:{key:{eq:"G"}}, number:{eq:$n}}){ nodes{ id } } }',
                    {"n": int(m.group(1))})
            nodes = q["issues"]["nodes"]
            if nodes:
                gql("mutation($i:IssueRelationCreateInput!){ issueRelationCreate(input:$i){ success } }",
                    {"i": {"issueId": iid, "relatedIssueId": nodes[0]["id"], "type": "related"}})
        except Exception as e:
            print(f"relation {g} skipped:", e, file=sys.stderr)

    # expose for the reply step
    with open(os.environ["GITHUB_ENV"], "a") as fh:
        fh.write(f"LINEAR_ID={identifier}\nLINEAR_URL={iurl}\n")


if __name__ == "__main__":
    main()
