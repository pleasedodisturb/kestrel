document.addEventListener("DOMContentLoaded", async () => {
  let data;
  try {
    const resp = await fetch("data.json");
    data = await resp.json();
  } catch {
    document.getElementById("subtitle").textContent = "Failed to load data";
    return;
  }

  renderHeader(data);
  renderPipeline(data.applicationStats);
  renderMilestones(data.milestones, data.issues);
  renderActivity(data.actionLog);
  renderCompanies(data.targetCompanies);
  renderFooter(data);
});

function renderHeader(data) {
  document.getElementById("subtitle").textContent =
    data.project?.summary?.split("\n")[0] || "Job Search Command Center";
  document.getElementById("linear-link").href = data.project?.url || "#";
  if (data.generatedAt) {
    const d = new Date(data.generatedAt);
    document.getElementById("last-updated").textContent =
      `Updated ${d.toLocaleDateString("en-DE", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}`;
  }
}

function renderPipeline(stats) {
  if (!stats) return;
  document.getElementById("stat-researching").textContent = stats.researching || 0;
  document.getElementById("stat-applied").textContent = stats.applied || 0;
  document.getElementById("stat-interviewing").textContent = stats.interviewing || 0;
  document.getElementById("stat-offered").textContent = stats.offered || 0;
}

function renderMilestones(milestones, issues) {
  const container = document.getElementById("milestones-container");
  if (!milestones?.length) {
    container.innerHTML = '<p class="text-white/30 text-sm">No milestones yet</p>';
    return;
  }

  const unassigned = issues?.filter((i) => !i.milestoneId) || [];

  let html = milestones
    .map((m) => {
      const mIssues = issues?.filter((i) => i.milestoneId === m.id) || [];
      const completed = mIssues.filter((i) => i.statusType === "completed").length;
      const pct = mIssues.length ? Math.round((completed / mIssues.length) * 100) : 0;

      return `
      <div class="mb-5">
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-sm font-semibold text-white/80">${esc(m.name)}</h3>
          <span class="text-xs text-white/40">${completed}/${mIssues.length} done</span>
        </div>
        <div class="w-full bg-white/5 rounded-full h-1.5 mb-3">
          <div class="bg-accent rounded-full h-1.5 transition-all" style="width: ${pct}%"></div>
        </div>
        ${mIssues.length ? renderIssueList(mIssues) : '<p class="text-white/20 text-xs ml-2">No tasks yet</p>'}
      </div>`;
    })
    .join("");

  if (unassigned.length) {
    html += `
    <div class="mb-5">
      <h3 class="text-sm font-semibold text-white/40 mb-2">No Milestone</h3>
      ${renderIssueList(unassigned)}
    </div>`;
  }

  container.innerHTML = html;
}

function renderIssueList(issues) {
  return `<div class="space-y-1.5">${issues.map((i) => {
    const statusColor = {
      completed: "bg-emerald-500/20 text-emerald-300",
      started: "bg-blue-500/20 text-blue-300",
      unstarted: "bg-white/10 text-white/50",
      backlog: "bg-white/5 text-white/30",
      canceled: "bg-red-500/20 text-red-300",
    }[i.statusType] || "bg-white/10 text-white/50";

    const priorityIcon = { 1: "!!", 2: "!", 3: "", 4: "" }[i.priority] || "";

    return `
    <a href="${esc(i.url)}" target="_blank"
       class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/5 transition group">
      <span class="status-pill ${statusColor}">${esc(i.status)}</span>
      <span class="text-sm text-white/70 group-hover:text-white transition flex-1">
        ${priorityIcon ? `<span class="text-urgent font-bold mr-1">${priorityIcon}</span>` : ""}
        ${esc(i.title)}
      </span>
      <span class="text-xs text-white/20">${esc(i.identifier)}</span>
    </a>`;
  }).join("")}</div>`;
}

function renderActivity(entries) {
  const container = document.getElementById("activity-container");
  if (!entries?.length) {
    container.innerHTML = '<p class="text-white/30 text-sm">No activity logged yet</p>';
    return;
  }

  container.innerHTML = entries
    .map((e) => {
      const catColor = {
        setup: "text-blue-400",
        profile: "text-purple-400",
        application: "text-emerald-400",
        interview: "text-amber-400",
        networking: "text-pink-400",
        learning: "text-cyan-400",
        tooling: "text-orange-400",
        research: "text-indigo-400",
      }[e.category] || "text-white/40";

      return `
      <div class="border-l-2 border-white/10 pl-3">
        <div class="flex items-center gap-2 text-xs mb-0.5">
          <span class="text-white/30">${esc(e.date)}</span>
          <span class="${catColor} font-medium">${esc(e.category)}</span>
        </div>
        <div class="text-sm text-white/70 font-medium">${esc(e.title)}</div>
        ${e.items?.length ? `<ul class="text-xs text-white/40 mt-1 space-y-0.5">${e.items.slice(0, 3).map((item) => `<li>- ${esc(item)}</li>`).join("")}${e.items.length > 3 ? `<li class="text-white/20">+${e.items.length - 3} more</li>` : ""}</ul>` : ""}
      </div>`;
    })
    .join("");
}

function renderCompanies(tiers) {
  const container = document.getElementById("companies-container");
  if (!tiers?.length) {
    container.innerHTML = '<p class="text-white/30 text-sm">No companies loaded</p>';
    return;
  }

  container.innerHTML = tiers
    .map(
      (t) => `
    <div>
      <h4 class="text-xs font-semibold text-white/50 mb-1">${esc(t.tier)}</h4>
      <p class="text-sm text-white/60">${t.companies.map((c) => esc(c)).join(" &middot; ")}</p>
    </div>`
    )
    .join("");
}

function renderFooter(data) {
  const s = data.stats || {};
  document.getElementById("issue-stats").textContent =
    `${s.total || 0} issues | ${s.completed || 0} done | ${s.inProgress || 0} in progress | ${s.todo || 0} todo | ${s.backlog || 0} backlog`;
}

function esc(str) {
  if (!str) return "";
  const el = document.createElement("span");
  el.textContent = str;
  return el.innerHTML;
}
