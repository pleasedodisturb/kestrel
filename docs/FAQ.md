---
layout: default
permalink: /docs/FAQ
title: Frequently Asked Questions
---

<p align="center"><img src="../assets/illustrations/hero-yellow.webp" alt="Kestrel" width="300"></p>

# Frequently Asked Questions

---

### Do I need to know how to code?

No. You'll type a total of 2 commands in the Terminal app to get Kestrel running. After that, everything happens through a normal web interface in your browser - point, click, drag, drop. The terminal commands are copy-paste, not coding.

If you've ever used a web app like Notion, Trello, or Google Sheets, you can use Kestrel.

---

### What is Docker and why do I need it?

Docker is an app you install on your computer. Think of it as a box that runs Kestrel inside it, keeping everything tidy and self-contained. Without Docker, you'd need to install Python, Node.js, a database, and a bunch of other developer tools separately. Docker bundles all of that together so you don't have to deal with it.

To use Docker, you install a runtime app: [OrbStack](https://orbstack.dev) (recommended on Mac — lighter and faster) or [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Mac/Windows). Both are free for personal use. You don't need to create an account — skip the sign-up screen if one appears.

It uses about 1-2 GB of disk space. You can quit OrbStack or Docker Desktop when you're not using Kestrel to free up memory.

---

### Is my data safe? Where does it go?

Your data stays entirely on your computer. Kestrel stores everything in a local database file inside the `data/` folder in your Kestrel directory. Nothing is uploaded to the cloud, no account is needed, and nobody can see your applications, scores, or profile. That's the whole point of "self-hosted."

The only external connections Kestrel makes:
- **Job boards** (to search for listings) - it sends your search criteria, not your personal info
- **AI service** (only if you enable real AI scoring) - it sends the job description and a summary of your profile, not your full personal details

If you never set up an AI provider, Kestrel makes no external calls beyond job board searches.

---

### What does Demo Mode mean? Is it fake?

When you first install Kestrel, it runs in Demo Mode. The AI features (scoring, coaching, interview prep) return pre-generated example data instead of real AI analysis. This lets you explore every feature without signing up for anything or spending money.

The data looks realistic but it's not personalized to you. The scores, the coaching tips, the interview questions - they're all generic examples.

To get real, personalized AI results, you need to connect an AI provider. See [How do I add a real AI provider?](#how-do-i-add-a-real-ai-provider) below.

---

### Do I have to pay for anything?

Kestrel itself is completely free and open source.

If you want real AI scoring (recommended once you've decided Kestrel is useful to you), you'll need an OpenRouter account. OpenRouter charges per AI call - typical job search usage costs around $1-3 per month, sometimes less. You can set a spending limit on your account so you never get a surprise bill.

Everything else - the pipeline board, application tracking, discovery, job search across multiple boards - works without paying for anything.

---

### I'm stuck at "git clone." What do I do?

Skip it. You don't need git.

1. Go to the Kestrel page on GitHub: https://github.com/pleasedodisturb/kestrel
2. Click the green **Code** button
3. Click **Download ZIP**
4. Find the download (probably in your Downloads folder) and double-click to unzip it
5. You now have a folder called `kestrel-main`

Then open Terminal (Mac: press Cmd+Space, type "Terminal") and type:

```
cd ~/Downloads/kestrel-main
bash setup.sh
```

Press Enter after each line. That's it.

---

### I'm stuck at setup.sh. What do I do?

Here are the most common problems and their fixes:

**"Permission denied"**
Type `bash setup.sh` instead of `./setup.sh`. This is the most common issue and the fix is that simple.

**"No such file or directory"**
You're in the wrong folder. Type `ls` and press Enter. If you don't see `setup.sh` in the list of files, you need to navigate to where you put Kestrel. Try:
```
cd ~/Downloads/kestrel-main
```
Then run `bash setup.sh` again.

**"Docker not found" or "Cannot connect to Docker daemon"**
Your Docker runtime isn't installed or isn't running. On Mac, install OrbStack from https://orbstack.dev (recommended) or Docker Desktop from https://docker.com. Open the app and wait for it to start before trying again.

**It just sits there doing nothing**
The Docker build can take 2-5 minutes, especially the first time. It's downloading things. Don't close the window. If it's been more than 10 minutes with no new text appearing, something might be wrong - try pressing Ctrl+C to stop it and running `bash setup.sh` again.

**Something else entirely**
See question 17 at the bottom for how to get help.

---

### Can I use this on Windows?

Yes. Install Docker Desktop for Windows from the same docker.com download page. It may ask you to enable WSL2 (Windows Subsystem for Linux) during installation - say yes, it makes Docker work better on Windows.

Instead of Terminal, you'll use **PowerShell**. Click the Start menu, type "PowerShell," and open it. The setup commands are the same:

```
cd $HOME\Downloads\kestrel-main
bash setup.sh
```

If `bash` isn't recognized, you may need to use WSL. Open PowerShell and type `wsl` first, then run the commands.

---

### What if I just want to try it without any setup?

There isn't a hosted demo yet - it's on the roadmap, but not ready.

For now, the Docker setup is the only way. The good news is it's genuinely a 10-15 minute process, and most of that time is waiting for things to download. You type two commands and wait. The [Quickstart guide](QUICKSTART.md) walks you through every step.

If you have a GitHub account and want to skip local setup, you can try **GitHub Codespaces** - it runs Kestrel in the cloud inside your browser. On the Kestrel GitHub page, click the green Code button, then the Codespaces tab, then "Create codespace." This takes a few minutes but doesn't install anything on your machine.

---

### How is this different from LinkedIn or Indeed?

LinkedIn and Indeed show you the same jobs they show everyone else. You apply, your resume goes into a pile with hundreds of others, and you mostly hear nothing back. "Easy Apply" is easy for everyone, which means more competition per role.

Kestrel works differently:

1. **It searches multiple boards at once.** Indeed, LinkedIn, Glassdoor, and more, in one search. You find listings you'd miss by only checking one site.
2. **It scores jobs against your profile.** Instead of scrolling through 200 listings and guessing which ones are worth your time, Kestrel tells you. A 9/10 match is worth crafting a great application for. A 4/10 is not.
3. **Your data stays on your computer.** No recruiter spam, no data selling, no premium upsell to see who viewed your profile. Kestrel doesn't have accounts, servers, or a business model that depends on your attention.

It's not a replacement for LinkedIn (you still need a profile there). It's a tool that makes your search smarter and less exhausting.

---

### I closed Terminal. How do I start Kestrel again?

Open Terminal (Mac: Cmd+Space, type "Terminal") or PowerShell (Windows), then type:

```
cd ~/Downloads/kestrel-main
docker compose up -d
```

(Replace the path with wherever your Kestrel folder is.)

Then open http://localhost:8101 in your browser. Your data is still there - nothing is lost when you close Terminal or restart your computer.

To stop Kestrel later:

```
docker compose down
```

---

### What does the score number mean?

The AI looks at the job listing and compares it to your profile across several factors:

- **Skill match** - Do your skills line up with what they're asking for?
- **Seniority fit** - Is this the right level for your experience?
- **Salary alignment** - Is the pay in your target range (if listed)?
- **Location** - Does it match your preferences, including remote?
- **Career trajectory** - Does this role move you in the direction you actually want to go?

**8-10:** Strong fit. Worth spending real time on the application.
**5-7:** Decent fit. Read the details before deciding.
**Below 5:** Probably not worth your time.

In Demo Mode, the scores are generic examples. Once you connect a real AI provider, they're personalized to your actual background and goals.

---

### How do I add a real AI provider?

The recommended provider is **OpenRouter**, which gives you access to multiple AI models through one account.

1. Go to https://openrouter.ai and create a free account
2. Go to https://openrouter.ai/keys and create a new API key
3. Copy the key (it starts with `sk-or-`)
4. In Kestrel, go to **Settings** in the web UI and look for the AI provider section
5. Paste your OpenRouter API key there and save

If Settings doesn't have an API key field (older versions), you'll need to edit the `.env` file in your Kestrel folder:
1. Open the `.env` file in a text editor (on Mac, you can use TextEdit; on Windows, Notepad)
2. Find the line that says `OPENROUTER_API_KEY=` and paste your key after the `=`
3. Save the file
4. Restart Kestrel: run `docker compose down` then `docker compose up -d`

OpenRouter charges per AI call. Set a monthly spending limit on your OpenRouter account (under Billing) so there are no surprises. Typical usage is $1-3/month.

---

### I set up the API key but scoring still looks fake.

A few things to check:

1. **Did you restart Kestrel after adding the key?** If you edited `.env` directly, you need to run `docker compose down && docker compose up -d` for the change to take effect (`docker compose restart` does not reload env vars).
2. **Is the key correct?** OpenRouter keys start with `sk-or-`. Make sure there are no extra spaces before or after the key in your `.env` file.
3. **Does your OpenRouter account have credits?** Log into OpenRouter and check your balance. New accounts sometimes need you to add a payment method before API calls work.
4. **Are you looking at old scores?** Jobs that were scored before you added the key still have their demo scores. Run a new discovery search or re-score existing jobs to see real results.

If the AI provider is connected properly, you should see it reflected in Settings or in the app header (it may say "AI Connected" or show the provider name instead of "Demo Mode").

---

### Can I use ChatGPT or Claude instead of OpenRouter?

Not directly. Kestrel uses OpenRouter as its AI gateway, which actually gives you access to many models including GPT-4, Claude, Mistral, Llama, and others. When you use OpenRouter, you're choosing which underlying model to use - it's like a switchboard.

So if you want to use Claude for scoring, you'd still set up OpenRouter and then select an Anthropic model in your Kestrel settings.

Direct OpenAI or Anthropic API support may come in a future version, but OpenRouter is the simplest setup for now since it handles everything through one key.

---

### Is this really free? What's the catch?

Kestrel is open source under the MIT license. The code is free, the tool is free, there's no company behind it selling your data or planning to charge you later.

The only cost is if you choose to use real AI scoring through OpenRouter, which is a separate, third-party service. That's typically $1-3/month for normal job search usage. You can use Kestrel without it (Demo Mode works fine for tracking applications and searching job boards).

There's no catch. The author built this to solve their own job search problem and decided to share it.

---

### I closed my laptop / computer went to sleep. Is Kestrel still running?

Docker containers sometimes stop working after macOS sleep/wake. Open http://localhost:8101 — if it loads, you're fine. If not, open Terminal and run:

```
cd ~/Downloads/kestrel-main
docker compose up -d
```

If that doesn't work, make sure your Docker runtime is running (OrbStack or Docker Desktop), then try `docker compose down && docker compose up -d`.

Kestrel also includes a watchdog script that checks and restarts containers automatically: `bash scripts/docker-watchdog.sh`. See the [troubleshooting guide](HELP.md#my-mac-went-to-sleep-and-kestrel-stopped-working) for details.

Your data is never lost — it's saved in a file on your computer, not in Docker's memory.

---

### I forgot about Kestrel for a week. Is my data gone?

No. Your data is stored in a database file on your computer (data/career_os.db inside the Kestrel folder - the database file's internal name is career_os.db, this is normal). Even if Docker was stopped, restarted, or updated, your data is still there. Just run `docker compose up -d` and open the dashboard.

---

### How do I set up the daily job scan?

The daily scan runs as a GitHub Action - it uses GitHub's servers to scrape job boards every morning and score the results. To set it up:
1. Fork the Kestrel repo to your own GitHub account
2. Go to your fork's Settings > Secrets and variables > Actions
3. Add your AI key as a secret called OPENAI_API_KEY
4. The scan runs automatically Monday-Friday at 7am UTC
5. Results appear as commits in your repo's tracking/ folder

This is the most technical feature to set up. If GitHub Actions feels like too much, you can run the same thing manually: `docker compose exec backend python tools/daily_pipeline.py`

---

### My profile is empty. Will scoring still work?

Technically yes, but the scores won't be meaningful. AI scoring compares the job description against YOUR profile - if your profile is empty, there's nothing to compare against. Take 5 minutes to fill in your profile (Settings > Profiles): your target roles, skills, preferred location, and salary range. This makes a huge difference in score quality.

---

### I need help and this FAQ doesn't cover it.

A few options:

**Ask an AI for help.** Paste this into ChatGPT, Claude, or any AI assistant you use:

> I'm trying to set up Kestrel (a self-hosted job search tool that runs with Docker). I'm stuck at [describe your problem]. The error message I see is [paste it here]. I'm on [Mac/Windows]. Can you help me?

AI assistants are surprisingly good at debugging terminal and Docker issues. Give them the exact error message you see.

**Open a GitHub issue.** Go to https://github.com/pleasedodisturb/kestrel/issues and click "New Issue." Describe what you were trying to do, what happened instead, and paste any error messages. Someone will help.

**Check existing issues.** Someone else might have had the same problem. Search the issues page before creating a new one.
