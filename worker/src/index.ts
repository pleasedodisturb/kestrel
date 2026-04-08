export interface Env {
  LINEAR_API_KEY: string;
  LINEAR_WEBHOOK_SECRET: string;
  LINEAR_TEAM_ID: string;
  LINEAR_PROJECT_ID: string;
  TICKTICK_ACCESS_TOKEN: string;
  TICKTICK_PROJECT_ID: string;
  CF_PAGES_DEPLOY_HOOK: string;
}

// --- Linear status <-> TickTick status mapping ---

const LINEAR_TO_TICKTICK_STATUS: Record<string, number> = {
  "In Progress": 1, // active
  "In Review": 1,
  Todo: 0, // normal/not started
  Done: 2, // completed
  Canceled: -1, // skip
  Backlog: -1, // skip (don't sync backlog to keep TickTick clean)
};

const TICKTICK_COMPLETED_STATUS = 2;

// --- HTTP handler: Linear webhooks ---

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return new Response("ok", { status: 200 });
    }

    if (url.pathname === "/webhook/linear" && request.method === "POST") {
      return handleLinearWebhook(request, env);
    }

    if (url.pathname === "/sync" && request.method === "POST") {
      const result = await syncTickTickToLinear(env);
      await triggerDashboardRebuild(env);
      return Response.json(result);
    }

    if (url.pathname === "/calendar.ics") {
      return handleCalendarFeed(env);
    }

    return new Response("Not found", { status: 404 });
  },

  // --- Cron handler: poll TickTick -> update Linear ---
  async scheduled(_event: ScheduledEvent, env: Env, _ctx: ExecutionContext): Promise<void> {
    await syncTickTickToLinear(env);
    await triggerDashboardRebuild(env);
  },
};

// --- Linear Webhook Handler ---

async function handleLinearWebhook(request: Request, env: Env): Promise<Response> {
  const body = await request.text();

  // Verify webhook signature
  const signature = request.headers.get("linear-signature");
  if (env.LINEAR_WEBHOOK_SECRET && signature) {
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(env.LINEAR_WEBHOOK_SECRET),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );
    const sig = await crypto.subtle.sign("HMAC", key, encoder.encode(body));
    const expected = Array.from(new Uint8Array(sig))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    if (expected !== signature) {
      return new Response("Invalid signature", { status: 401 });
    }
  }

  const payload = JSON.parse(body);

  if (payload.type === "Issue" && payload.action === "update") {
    const issue = payload.data;
    const newState = issue.state?.name;
    if (!newState) return new Response("No state change", { status: 200 });

    const ticktickStatus = LINEAR_TO_TICKTICK_STATUS[newState];
    if (ticktickStatus === -1 || ticktickStatus === undefined) {
      return new Response("Status not synced", { status: 200 });
    }

    try {
      await syncLinearIssueToTickTick(issue, ticktickStatus, env);
      await triggerDashboardRebuild(env);
      return new Response("Synced", { status: 200 });
    } catch (err) {
      console.error("Sync error:", err);
      return new Response("Sync failed", { status: 500 });
    }
  }

  return new Response("OK", { status: 200 });
}

// --- Linear -> TickTick sync ---

async function syncLinearIssueToTickTick(
  issue: { id: string; identifier: string; title: string; description?: string },
  ticktickStatus: number,
  env: Env
): Promise<void> {
  const existingTask = await findTickTickTaskByLinearId(issue.identifier, env);

  if (existingTask) {
    await updateTickTickTask(existingTask.id, { status: ticktickStatus }, env);
  } else if (ticktickStatus !== 2) {
    // Don't create a new task if it's already completed
    await createTickTickTask(
      {
        title: `[${issue.identifier}] ${issue.title}`,
        content: `Linear: ${issue.identifier}\n${issue.description || ""}`.slice(0, 500),
        projectId: env.TICKTICK_PROJECT_ID,
        status: ticktickStatus,
      },
      env
    );
  }
}

// --- TickTick -> Linear sync ---

async function syncTickTickToLinear(env: Env): Promise<{ synced: number; errors: number }> {
  let synced = 0;
  let errors = 0;

  try {
    const tasks = await getTickTickProjectTasks(env);
    const completedTasks = tasks.filter(
      (t: any) => t.status === TICKTICK_COMPLETED_STATUS && extractLinearId(t.title)
    );

    for (const task of completedTasks) {
      const linearId = extractLinearId(task.title);
      if (!linearId) continue;

      try {
        const issue = await getLinearIssue(linearId, env);
        if (issue && issue.state?.type !== "completed") {
          await updateLinearIssueStatus(issue.id, "Done", env);
          synced++;
        }
      } catch (err) {
        console.error(`Error syncing ${linearId}:`, err);
        errors++;
      }
    }
  } catch (err) {
    console.error("TickTick fetch error:", err);
    errors++;
  }

  return { synced, errors };
}

// --- TickTick API helpers ---

async function getTickTickProjectTasks(env: Env): Promise<any[]> {
  const resp = await fetch(
    `https://api.ticktick.com/open/v1/project/${env.TICKTICK_PROJECT_ID}/data`,
    { headers: { Authorization: `Bearer ${env.TICKTICK_ACCESS_TOKEN}` } }
  );
  if (!resp.ok) throw new Error(`TickTick API error: ${resp.status}`);
  const data = await resp.json() as any;
  return data.tasks || [];
}

async function findTickTickTaskByLinearId(linearId: string, env: Env): Promise<any | null> {
  const tasks = await getTickTickProjectTasks(env);
  return tasks.find((t: any) => t.title?.includes(`[${linearId}]`)) || null;
}

async function createTickTickTask(task: any, env: Env): Promise<any> {
  const resp = await fetch("https://api.ticktick.com/open/v1/task", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.TICKTICK_ACCESS_TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(task),
  });
  if (!resp.ok) throw new Error(`TickTick create error: ${resp.status}`);
  return resp.json();
}

async function updateTickTickTask(taskId: string, updates: any, env: Env): Promise<any> {
  const resp = await fetch(`https://api.ticktick.com/open/v1/task/${taskId}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.TICKTICK_ACCESS_TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(updates),
  });
  if (!resp.ok) throw new Error(`TickTick update error: ${resp.status}`);
  return resp.json();
}

// --- Linear API helpers ---

async function getLinearIssue(identifier: string, env: Env): Promise<any | null> {
  const query = `query { issueSearch(filter: { identifier: { eq: "${identifier}" } }, first: 1) { nodes { id identifier state { name type } } } }`;
  const resp = await fetch("https://api.linear.app/graphql", {
    method: "POST",
    headers: {
      Authorization: env.LINEAR_API_KEY,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ query }),
  });
  if (!resp.ok) throw new Error(`Linear API error: ${resp.status}`);
  const data = await resp.json() as any;
  return data.data?.issueSearch?.nodes?.[0] || null;
}

async function updateLinearIssueStatus(issueId: string, stateName: string, env: Env): Promise<void> {
  // First get the state ID for this team
  const stateQuery = `query { workflowStates(filter: { team: { id: { eq: "${env.LINEAR_TEAM_ID}" } }, name: { eq: "${stateName}" } }) { nodes { id name } } }`;
  const stateResp = await fetch("https://api.linear.app/graphql", {
    method: "POST",
    headers: { Authorization: env.LINEAR_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ query: stateQuery }),
  });
  const stateData = await stateResp.json() as any;
  const stateId = stateData.data?.workflowStates?.nodes?.[0]?.id;
  if (!stateId) throw new Error(`State "${stateName}" not found`);

  const mutation = `mutation { issueUpdate(id: "${issueId}", input: { stateId: "${stateId}" }) { success } }`;
  const resp = await fetch("https://api.linear.app/graphql", {
    method: "POST",
    headers: { Authorization: env.LINEAR_API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ query: mutation }),
  });
  if (!resp.ok) throw new Error(`Linear update error: ${resp.status}`);
}

// --- Dashboard rebuild trigger ---

async function triggerDashboardRebuild(env: Env): Promise<void> {
  if (!env.CF_PAGES_DEPLOY_HOOK) return;
  try {
    await fetch(env.CF_PAGES_DEPLOY_HOOK, { method: "POST" });
  } catch (err) {
    console.error("Dashboard rebuild trigger failed:", err);
  }
}

// --- Calendar Feed ---

async function handleCalendarFeed(env: Env): Promise<Response> {
  try {
    const query = `query {
      issues(filter: { project: { id: { eq: "${env.LINEAR_PROJECT_ID}" } } }, first: 50) {
        nodes { id identifier title description dueDate state { name type } priority priorityLabel url createdAt }
      }
    }`;

    const resp = await fetch("https://api.linear.app/graphql", {
      method: "POST",
      headers: { Authorization: env.LINEAR_API_KEY, "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });

    if (!resp.ok) throw new Error(`Linear API: ${resp.status}`);
    const data = await resp.json() as any;
    const issues = data.data?.issues?.nodes || [];

    const now = new Date();
    const lines = [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//Job Search HQ//Sync Worker//EN",
      "CALSCALE:GREGORIAN",
      "METHOD:PUBLISH",
      "X-WR-CALNAME:Job Search HQ",
    ];

    for (const issue of issues) {
      if (issue.state?.type === "canceled") continue;

      const dtStamp = formatICSDate(new Date(issue.createdAt));
      const due = issue.dueDate ? formatICSDate(new Date(issue.dueDate)) : null;
      const summary = `[${issue.identifier}] ${issue.title}`;
      const status = issue.state?.type === "completed" ? "COMPLETED" : "NEEDS-ACTION";

      lines.push("BEGIN:VTODO");
      lines.push(`UID:${issue.id}@job-search-hq`);
      lines.push(`DTSTAMP:${dtStamp}`);
      if (due) lines.push(`DUE;VALUE=DATE:${due}`);
      lines.push(`SUMMARY:${escapeICS(summary)}`);
      lines.push(`DESCRIPTION:${escapeICS((issue.description || "").slice(0, 200))}`);
      lines.push(`URL:${issue.url}`);
      lines.push(`STATUS:${status}`);
      lines.push(`PRIORITY:${mapPriority(issue.priority)}`);
      lines.push("END:VTODO");
    }

    lines.push("END:VCALENDAR");

    return new Response(lines.join("\r\n"), {
      headers: {
        "Content-Type": "text/calendar; charset=utf-8",
        "Content-Disposition": 'attachment; filename="job-search-hq.ics"',
        "Cache-Control": "public, max-age=900",
      },
    });
  } catch (err) {
    console.error("Calendar feed error:", err);
    return new Response("Calendar feed error", { status: 500 });
  }
}

function formatICSDate(date: Date): string {
  return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}

function escapeICS(text: string): string {
  return text.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
}

function mapPriority(linearPriority: number): number {
  // Linear: 1=Urgent, 2=High, 3=Medium, 4=Low; ICS: 1=High, 5=Medium, 9=Low
  return { 1: 1, 2: 3, 3: 5, 4: 9 }[linearPriority] || 0;
}

// --- Utility ---

function extractLinearId(title: string): string | null {
  const match = title?.match(/\[(JOB-\d+)\]/);
  return match?.[1] || null;
}
