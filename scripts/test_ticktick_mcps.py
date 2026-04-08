#!/usr/bin/env python3
"""
Test both TickTick MCP servers by sending tools/list via stdio.

Usage:
  python scripts/test_ticktick_mcps.py [felores|ticktick-sdk|both]

Requires valid credentials and network access.
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FELORES_CMD = [str(PROJECT_ROOT / ".venv" / "bin" / "ticktick-mcp-server"), "run"]
SDK_CMD = [str(PROJECT_ROOT / "ticktick-sdk" / ".venv" / "bin" / "ticktick-sdk"), "server"]
SDK_ENV = {
    "TICKTICK_CREDENTIALS_PATH": str(Path.home() / ".config" / "ticktick-sdk" / "credentials.json"),
}


def run_mcp_tools_list(cmd: list[str], env: dict | None = None, timeout: int = 15) -> dict | str:
    """Send tools/list to MCP server via stdio, return parsed response or error."""
    request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
    try:
        proc = subprocess.run(
            cmd,
            input=request.encode(),
            capture_output=True,
            timeout=timeout,
            env={**subprocess.os.environ, **(env or {})},
        )
        out = proc.stdout.decode(errors="replace")
        err = proc.stderr.decode(errors="replace")
        if proc.returncode != 0 and not out:
            return f"Exit {proc.returncode}\nstderr: {err}"
        for line in out.strip().split("\n"):
            try:
                data = json.loads(line)
                if "result" in data:
                    return data["result"]
                if "error" in data:
                    return f"Error: {data['error']}"
            except json.JSONDecodeError:
                continue
        return f"No valid JSON-RPC response. stdout: {out[:500]}"
    except subprocess.TimeoutExpired:
        return "Timeout"
    except FileNotFoundError:
        return f"Command not found: {cmd[0]}"
    except Exception as e:
        return str(e)


def main():
    target = (sys.argv[1] if len(sys.argv) > 1 else "both").lower()
    if target not in ("felores", "ticktick-sdk", "both"):
        print("Usage: python scripts/test_ticktick_mcps.py [felores|ticktick-sdk|both]")
        sys.exit(1)

    if target in ("felores", "both"):
        print("=== Felores (ticktick-mcp-server) ===\n")
        result = run_mcp_tools_list(FELORES_CMD)
        if isinstance(result, dict):
            tools = result.get("tools", [])
            print(f"Tools: {len(tools)}")
            for t in tools:
                print(f"  - {t.get('name', '?')}")
        else:
            print(f"Failed: {result}")
        print()

    if target in ("ticktick-sdk", "both"):
        print("=== TickTick-SDK ===\n")
        result = run_mcp_tools_list(SDK_CMD, env=SDK_ENV)
        if isinstance(result, dict):
            tools = result.get("tools", [])
            print(f"Tools: {len(tools)}")
            for t in tools:
                print(f"  - {t.get('name', '?')}")
        else:
            print(f"Failed: {result}")


if __name__ == "__main__":
    main()
