# Help - Troubleshooting Kestrel

## Quick diagnosis

**What's happening?**

- [I can't install it](#installation-problems)
- [It was working but now it's not](#it-stopped-working)
- [The dashboard looks weird or empty](#dashboard-issues)
- [AI scoring isn't working](#ai-scoring-issues)
- [I have no idea what went wrong](#i-have-no-idea)

---

## Installation problems

### "Docker not found" or "Docker is not installed"

Docker is a free app that Kestrel needs to run. Install it:
- **Mac:** https://www.docker.com/products/docker-desktop/
- **Windows:** Same link, pick the Windows version
- Install it like any normal app. You do NOT need a Docker account.

### "Docker is installed but not running"

Open the Docker Desktop app. On Mac, look for a whale icon in your menu bar (top of screen). Wait for it to stop animating. Then try again.

### "permission denied" when running setup.sh

Use `bash setup.sh` instead of `./setup.sh`. This is a Mac/Linux quirk.

### "No such file or directory"

You're not in the Kestrel folder. In Terminal, type:
```
cd ~/Downloads/kestrel-main
```
(Replace with wherever you put the Kestrel folder.)

Then try `bash setup.sh` again.

### "Port 8100 is already in use"

Another program is using that port. Either:
1. Close the other program, or
2. Open the `.env` file and change `PORT=8100` to `PORT=8200`
3. Run setup again

### Build fails with a wall of red text

This usually means a network issue. Check your internet connection and try again:
```
docker compose down -v
bash setup.sh
```

If it keeps failing, you might be low on disk space (Kestrel needs about 2 GB).

---

## It stopped working

### "I closed Terminal and now Kestrel is gone"

Kestrel is still there. Open Terminal and type:
```
cd ~/Downloads/kestrel-main
docker compose up -d
```

Then open http://localhost:8101. Your data is still there.

### "I restarted my computer"

Same as above - you just need to start Docker Desktop and then run `docker compose up -d`.

### "The page won't load (connection refused)"

Docker might have stopped. Check:
1. Is Docker Desktop running? (whale icon in menu bar)
2. Open Terminal and type: `docker compose up -d`
3. Wait 30 seconds, then try http://localhost:8101 again

---

## Dashboard issues

### "The Kanban board is empty"

That's normal on first run! You haven't added any applications yet. Click "Add Application" to add your first one, or try Discovery to find jobs automatically.

### "Everything shows Demo Mode / mock data"

Kestrel starts in Demo Mode by default - all AI features work but return simulated data. This is free and works offline. To get real AI scoring, see [AI scoring issues](#ai-scoring-issues) below.

### "The page is blank (white screen)"

The frontend might not be ready yet. Wait 30 seconds and refresh. If it persists:
```
docker compose logs frontend
```
Look for error messages.

---

## AI scoring issues

### "Scores don't seem personalized"

If you're in Demo Mode (the default), scores are simulated - they look real but aren't based on YOUR profile. To get real scoring:

1. Sign up at https://openrouter.ai
2. Get an API key (starts with `sk-or-`)
3. Open the `.env` file in a text editor:
   - On Mac, files starting with `.` are hidden. In Terminal, type: `open .env`
   - Or use: `nano .env` (save with Ctrl+O, exit with Ctrl+X)
4. Change these two lines:
   ```
   AI_PROVIDER=openrouter
   OPENROUTER_API_KEY=sk-or-your-key-here
   ```
5. Restart: `docker compose down && docker compose up -d`

### "I set the API key but it still looks like demo mode"

- Make sure there are no spaces before or after the key in `.env`
- Make sure the key starts with `sk-or-`
- Check: `curl http://localhost:8100/api/ai/health` - it should say `openrouter`

### "What does OpenRouter cost?"

Typical job search usage costs $1-3/month. You can set a spending limit on openrouter.ai so you never get a surprise bill. Kestrel tries to be efficient with API calls.

---

## I have no idea

If none of the above helps, try these in order:

### 1. Start fresh
```
docker compose down -v
bash setup.sh
```
This rebuilds everything from scratch. Your settings (.env, personal.yaml) are preserved.

### 2. Ask an AI for help
Paste this into ChatGPT, Claude, or any AI assistant:

> I'm trying to use Kestrel, a self-hosted job search tool that runs with Docker. Here's my problem: [describe what you see]. The tool runs on [Mac/Windows]. I ran `bash setup.sh` and [describe what happened]. Can you help me fix it?

### 3. Open an issue
Go to https://github.com/pleasedodisturb/kestrel/issues and click "New Issue." Describe what you tried and what happened. Include:
- Your operating system (Mac/Windows/Linux)
- What command you ran
- What error message you saw (screenshot or copy-paste)

Someone will help you.

---

## Useful commands reference

| What you want to do | Command |
|---------------------|---------|
| Start Kestrel | `docker compose up -d` |
| Stop Kestrel | `docker compose down` |
| Restart Kestrel (after env changes) | `docker compose down && docker compose up -d` |
| See what's happening | `docker compose logs backend` |
| Check if it's running | `curl http://localhost:8100/health` |
| Start completely fresh | `docker compose down -v && bash setup.sh` |
| Open the settings file | `open .env` (Mac) or `notepad .env` (Windows) |
