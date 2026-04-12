# kestrel-app

One-command installer for [Kestrel](https://github.com/pleasedodisturb/kestrel) — an AI-powered job search platform that runs on your computer.

## Usage

```bash
npx kestrel-app
```

This will:

1. Check for Python 3.11+ (required)
2. Install Kestrel via pip/pipx
3. Launch the web interface in your browser

## What is Kestrel?

Kestrel discovers jobs, scores them with AI, tracks your pipeline, and preps you for interviews — all running locally. Your data stays on your machine.

## Other install methods

```bash
# curl one-liner
curl -fsSL https://raw.githubusercontent.com/pleasedodisturb/kestrel/main/install.sh | bash

# pip (if you have Python 3.11+)
pip install kestrel-app && kestrel start

# Homebrew (macOS)
brew install pleasedodisturb/kestrel/kestrel

# Docker
git clone https://github.com/pleasedodisturb/kestrel.git && cd kestrel && bash setup.sh
```

## License

MIT
