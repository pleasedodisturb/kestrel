# SonarCloud MCP Server

An MCP server that gives Claude Code on-demand access to SonarCloud code quality data — issues, quality gates, metrics, security hotspots, and analysis history.

Works with both the **CLI** and **VS Code IDE** versions of Claude Code.

## Setup

### 1. Generate a SonarCloud token

1. Go to [sonarcloud.io](https://sonarcloud.io) → **My Account** → **Security**
2. Generate a new token (type: **User**)
3. Copy the token — you'll need it below

### 2. Install dependencies

```bash
cd /path/to/kestrel
python -m venv .venv_mcp
source .venv_mcp/bin/activate
pip install mcp httpx
```

### 3. Configure Claude Code

Copy the MCP config example and add your token:

```bash
cp mcp-configs/on-demand.json.example .mcp.json
```

Edit `.mcp.json` and update the `sonarcloud` entry:

```json
{
  "mcpServers": {
    "sonarcloud": {
      "command": ".venv_mcp/bin/python",
      "args": ["tools/sonarcloud-mcp/server.py"],
      "env": {
        "SONAR_TOKEN": "your-token-here"
      }
    }
  }
}
```

Both Claude Code CLI and the VS Code extension read `.mcp.json` from the project root.

## Available Tools

| Tool | Description |
|------|-------------|
| `sonar_quality_gate` | Quality gate status (PASS/FAIL) with condition details |
| `sonar_issues` | Search bugs, vulnerabilities, and code smells with filtering |
| `sonar_issue_detail` | Full details for a specific issue (comments, rule info) |
| `sonar_hotspots` | Security hotspots needing review |
| `sonar_metrics` | Numeric metrics: coverage, duplication, complexity, ratings |
| `sonar_project_status` | Project overview and last analysis date |
| `sonar_analysis_history` | Recent analysis history for tracking trends |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SONAR_TOKEN` | Yes | — | SonarCloud user token |
| `SONAR_PROJECT_KEY` | No | `pleasedodisturb_kestrel` | SonarCloud project key |
| `SONAR_ORGANIZATION` | No | `pleasedodisturb` | SonarCloud organization |

## Testing

Test the server interactively with the MCP Inspector:

```bash
source .venv_mcp/bin/activate
SONAR_TOKEN=your-token npx @modelcontextprotocol/inspector python tools/sonarcloud-mcp/server.py
```

This opens a browser UI where you can invoke each tool and see the formatted output.
