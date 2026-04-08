#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

// Load .env from repo root
const envPath = path.join(__dirname, "..", ".env");
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, "utf-8").split("\n")) {
    const match = line.match(/^([^#=]+)=(.*)$/);
    if (match && !process.env[match[1].trim()]) {
      process.env[match[1].trim()] = match[2].trim();
    }
  }
}

const { LinearClient } = require("@linear/sdk");

const LINEAR_API_KEY = process.env.LINEAR_API_KEY;
const PROJECT_ID = "164962c6-01b3-4e8e-99a5-9df574cd4529";

async function fetchLinearData() {
  if (!LINEAR_API_KEY) {
    console.warn("LINEAR_API_KEY not set -- using placeholder data");
    return generatePlaceholder();
  }

  const client = new LinearClient({ apiKey: LINEAR_API_KEY });

  const project = await client.project(PROJECT_ID);
  const milestones = await project.projectMilestones();
  const issues = await client.issues({
    filter: { project: { id: { eq: PROJECT_ID } } },
    orderBy: "priority",
  });

  const milestonesData = milestones.nodes.map((m) => ({
    id: m.id,
    name: m.name,
    description: m.description,
    sortOrder: m.sortOrder,
  }));

  const issuesData = await Promise.all(
    issues.nodes.map(async (i) => {
      const state = await i.state;
      const milestone = await i.projectMilestone;
      return {
        id: i.id,
        identifier: i.identifier,
        title: i.title,
        priority: i.priority,
        priorityLabel: i.priorityLabel,
        url: i.url,
        status: state?.name || "Unknown",
        statusType: state?.type || "unstarted",
        milestoneId: milestone?.id || null,
        milestoneName: milestone?.name || null,
        dueDate: i.dueDate,
        createdAt: i.createdAt,
      };
    })
  );

  return {
    project: {
      name: project.name,
      summary: project.description,
      url: project.url,
      state: project.state,
    },
    milestones: milestonesData.sort((a, b) => a.sortOrder - b.sortOrder),
    issues: issuesData,
    stats: computeStats(issuesData),
    generatedAt: new Date().toISOString(),
  };
}

function computeStats(issues) {
  const byStatus = {};
  for (const issue of issues) {
    byStatus[issue.status] = (byStatus[issue.status] || 0) + 1;
  }
  return {
    total: issues.length,
    byStatus,
    completed: issues.filter((i) => i.statusType === "completed").length,
    inProgress: issues.filter((i) => i.statusType === "started").length,
    todo: issues.filter((i) => i.statusType === "unstarted").length,
    backlog: issues.filter((i) => i.statusType === "backlog").length,
  };
}

function generatePlaceholder() {
  return {
    project: {
      name: "Job Search HQ",
      summary: "Searching for the right role",
      url: "https://linear.app/abandoned-yachts/project/job-search-hq-9bcd78537fa9",
      state: "started",
    },
    milestones: [
      { id: "1", name: "Foundation Complete", description: "Profile, tools, first applications", sortOrder: 0 },
      { id: "2", name: "Active Pipeline", description: "10+ applications, interviews scheduled", sortOrder: 1 },
      { id: "3", name: "Offer Secured", description: "Competitive offer in hand", sortOrder: 2 },
    ],
    issues: [],
    stats: { total: 0, byStatus: {}, completed: 0, inProgress: 0, todo: 0, backlog: 0 },
    generatedAt: new Date().toISOString(),
    placeholder: true,
  };
}

async function loadActionLog() {
  const logPath = path.join(__dirname, "..", "tracking", "action-log.md");
  try {
    const content = fs.readFileSync(logPath, "utf-8");
    const entries = [];
    const entryRegex = /^## (\d{4}-\d{2}-\d{2}) \| (\w+) \| (.+)$/gm;
    let match;
    while ((match = entryRegex.exec(content)) !== null) {
      const idx = match.index;
      const nextMatch = entryRegex.exec(content);
      const end = nextMatch ? nextMatch.index : content.length;
      entryRegex.lastIndex = nextMatch ? nextMatch.index : content.length;
      const body = content
        .slice(idx + match[0].length, end)
        .trim()
        .split("\n")
        .filter((l) => l.startsWith("- "))
        .map((l) => l.slice(2));
      entries.push({ date: match[1], category: match[2], title: match[3], items: body });
    }
    return entries.reverse().slice(0, 10);
  } catch {
    return [];
  }
}

async function loadTargetCompanies() {
  const filePath = path.join(__dirname, "..", "profile", "target-roles.md");
  try {
    const content = fs.readFileSync(filePath, "utf-8");
    const tiers = [];
    const tierRegex = /### (.+?)\n([\s\S]*?)(?=###|$)/g;
    let match;
    while ((match = tierRegex.exec(content)) !== null) {
      if (match[1].includes("Tier")) {
        const companies = match[2]
          .split("\n")
          .filter((l) => l.startsWith("- "))
          .map((l) => l.slice(2));
        tiers.push({ tier: match[1], companies });
      }
    }
    return tiers;
  } catch {
    return [];
  }
}

async function loadApplicationStats() {
  const csvPath = path.join(__dirname, "..", "tracking", "applications.csv");
  try {
    const content = fs.readFileSync(csvPath, "utf-8");
    const lines = content.trim().split("\n").slice(1);
    const stats = { researching: 0, applied: 0, interviewing: 0, offered: 0, rejected: 0, total: 0 };
    for (const line of lines) {
      if (!line.trim()) continue;
      stats.total++;
      const status = line.split(",")[5]?.trim().toLowerCase() || "";
      if (status in stats) stats[status]++;
    }
    return stats;
  } catch {
    return { researching: 0, applied: 0, interviewing: 0, offered: 0, rejected: 0, total: 0 };
  }
}

async function main() {
  console.log("Building dashboard data...");

  const [linearData, actionLog, targetCompanies, appStats] = await Promise.all([
    fetchLinearData(),
    loadActionLog(),
    loadTargetCompanies(),
    loadApplicationStats(),
  ]);

  const data = {
    ...linearData,
    actionLog,
    targetCompanies,
    applicationStats: appStats,
  };

  const outPath = path.join(__dirname, "data.json");
  fs.writeFileSync(outPath, JSON.stringify(data, null, 2));
  console.log(`Dashboard data written to ${outPath}`);
  console.log(`  Issues: ${data.stats.total} | Milestones: ${data.milestones.length}`);
  console.log(`  Applications: ${appStats.total} | Action log entries: ${actionLog.length}`);
}

main().catch((err) => {
  console.error("Build failed:", err);
  process.exit(1);
});
