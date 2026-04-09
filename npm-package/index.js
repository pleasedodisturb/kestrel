#!/usr/bin/env node

// Kestrel installer for npx
// Usage: npx kestrel-app

"use strict";

const { execSync, spawn } = require("child_process");
const os = require("os");

const MIN_PYTHON = [3, 13];

// ── Helpers ──

function print(msg) {
  console.log(msg);
}

function banner() {
  print("");
  print("  Kestrel Installer");
  print("  =================");
  print("  AI-powered job search, running on your computer.");
  print("");
}

function getPythonCommand() {
  for (const cmd of ["python3", "python"]) {
    try {
      const output = execSync(`${cmd} --version 2>&1`, {
        encoding: "utf-8",
        timeout: 5000,
      }).trim();
      const match = output.match(/(\d+)\.(\d+)(?:\.(\d+))?/);
      if (match) {
        const major = parseInt(match[1], 10);
        const minor = parseInt(match[2], 10);
        if (
          major > MIN_PYTHON[0] ||
          (major === MIN_PYTHON[0] && minor >= MIN_PYTHON[1])
        ) {
          return { cmd, version: `${major}.${minor}` };
        }
      }
    } catch {
      // Command not found or failed, try next
    }
  }
  return null;
}

function commandExists(cmd) {
  try {
    execSync(
      os.platform() === "win32" ? `where ${cmd}` : `command -v ${cmd}`,
      { encoding: "utf-8", timeout: 5000, stdio: "pipe" }
    );
    return true;
  } catch {
    return false;
  }
}

function printPythonHelp() {
  print(`  Python ${MIN_PYTHON.join(".")}+ is required but was not found.`);
  print("");

  const platform = os.platform();
  if (platform === "darwin") {
    print("  Install with Homebrew:");
    print("    brew install python@3.13");
    print("");
    print("  Or download from: https://www.python.org/downloads/");
  } else if (platform === "linux") {
    print("  On Ubuntu/Debian:");
    print("    sudo add-apt-repository ppa:deadsnakes/ppa");
    print("    sudo apt-get update");
    print("    sudo apt-get install python3.13 python3.13-venv");
    print("");
    print("  On Fedora:");
    print("    sudo dnf install python3.13");
    print("");
    print("  Or download from: https://www.python.org/downloads/");
  } else {
    print("  Download from: https://www.python.org/downloads/");
  }
  print("");
}

// ── Main ──

function main() {
  banner();

  // Check Python
  const python = getPythonCommand();
  if (!python) {
    printPythonHelp();
    process.exit(1);
  }
  print(`[ok] Python ${python.version} found (${python.cmd})`);

  // Install kestrel-app
  print("");
  print("Installing Kestrel...");

  try {
    if (commandExists("pipx")) {
      print("  Using pipx for isolated install...");
      execSync("pipx install kestrel-app", { stdio: "inherit", timeout: 300000 });
    } else {
      print(`  Using ${python.cmd} -m pip...`);
      execSync(`${python.cmd} -m pip install kestrel-app`, {
        stdio: "inherit",
        timeout: 300000,
      });
    }
  } catch (err) {
    print("");
    print("  Installation failed. Try manually:");
    print("    pip install kestrel-app && kestrel start");
    print("");
    print("  Report issues: https://github.com/pleasedodisturb/kestrel/issues");
    process.exit(1);
  }

  // Launch
  print("");
  print("================================================");
  print("");
  print("  Kestrel is installed!");
  print("  Starting Kestrel...");
  print("  Your browser will open automatically.");
  print("");
  print("  Data stored in: ~/.kestrel/");
  print("  To stop: press Ctrl+C");
  print("  To start again: kestrel start");
  print("");
  print("================================================");
  print("");

  const child = spawn("kestrel", ["start"], {
    stdio: "inherit",
    shell: true,
  });

  child.on("error", () => {
    print("Failed to start Kestrel. Try running: kestrel start");
    process.exit(1);
  });

  child.on("exit", (code) => {
    process.exit(code || 0);
  });
}

main();
