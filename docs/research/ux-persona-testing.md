---
layout: default
title: Kestrel UX Research: Persona-Based Journey Analysis
permalink: /docs/ux-persona-testing
---

# Kestrel UX Research: Persona-Based Journey Analysis

**Author:** UX Research Team
**Date:** April 2026
**Version:** 1.0
**Purpose:** Identify and fix every friction point between a non-technical user and their first successful experience with Kestrel.

---

## 1. Primary Persona: "Alex"

### Demographics

- **Name:** Alex M.
- **Age:** 31
- **Location:** Berlin, Germany
- **Previous role:** Marketing Operations Manager at a mid-size tech company (Series B, ~200 employees)
- **Current status:** Laid off in February 2026 during an "AI restructuring" - the company automated most of their marketing ops workflows and eliminated the role
- **Education:** Bachelor's in Communications, minor in Business Analytics

### Technical Profile

Alex is what we'd call "tool-fluent but not technical." They can:

- Navigate Notion, Figma (as a reviewer), Slack, Google Workspace, HubSpot, Asana
- Build a basic formula in Google Sheets
- Set up a Zap in Zapier using the GUI
- Use ChatGPT to draft emails and brainstorm ideas

Alex has never:

- Opened a terminal/command line
- Written a line of code
- Heard the word "Docker" used outside of shipping logistics
- Visited GitHub for any reason
- Understood what an API key is or why you'd need one
- Installed software by typing commands

**Devices:** MacBook Air (M2), iPhone 15, uses iCloud for everything. Chrome is the default browser.

### Emotional State

Alex is in a rough spot. Getting laid off "because AI can do your job" is a specific kind of humiliation. They're:

- **Anxious:** Savings cover 4-5 months. The clock is ticking.
- **Skeptical:** "AI took my job and now AI tools want to help me find a new one?" The irony is not lost on them.
- **Exhausted:** Applied to ~40 jobs on LinkedIn in the last month. Got 2 responses, both rejections. The "Easy Apply" button feels like dropping applications into a void.
- **Desperate enough to try anything:** A Reddit thread said "this open-source tool changed my job search" - and here they are.
- **Low tolerance for bullshit:** If something doesn't work in the first 5 minutes, they'll close the tab and go back to doom-scrolling LinkedIn.

### How They Found Kestrel

Someone posted on r/jobsearchhacks: "I built an open-source tool that scores job listings against your profile so you stop wasting time on bad fits. It's called Kestrel." The post had 847 upvotes and comments like "this is actually good" and "finally something that's not another LinkedIn wrapper." Alex clicked the GitHub link.

---

## 2. Alex's Journey Map (Sunny Day)

### Step 1: Landing on the GitHub Repository

**What Alex sees:**
A page that looks like... a document? There's a green button that says "Code," a bunch of folders with weird names like `src/` and `alembic/`, some colored badges that say "Python 3.11+" and "Docker Ready." The main content is a formatted document (the README).

**What Alex thinks:**
"Okay this looks like a developer website. I see a logo and description - 'A self-hosted job search platform. Precision over volume.' That sounds cool. But what is all this other stuff? Why are there folders? Is this the app? Where do I click to start?"

**What Alex feels:**
Mild intimidation. This is clearly a developer environment. But the README heading "What is this?" is inviting.

**What Alex does:**
Scrolls down to read the README. Skips the badges entirely.

**Friction level:** 2/5
The GitHub page layout is unfamiliar but the README content is readable.

**What could go wrong:**
- Alex might look for a "Download" or "Get Started" button at the top and not find one
- The file listing above the README might confuse them ("do I need to click on these folders?")
- They might think this is documentation FOR developers, not a product they can use

**What would help:**
- A prominent "Get Kestrel" or "Install" button or link at the very top of the README
- A screenshot or GIF of the actual dashboard so Alex knows what they're working toward
- A one-line "No coding required" reassurance near the top

---

### Step 2: Reading the README

**What Alex sees:**
The "What is this?" section describes Kestrel clearly. Then "Quick Start" says:

```
Requires Docker (or OrbStack on Mac).
git clone https://github.com/pleasedodisturb/kestrel.git && cd kestrel
./setup.sh
```

**What Alex thinks:**
"Self-hosted job search platform - okay, it runs on my computer, cool, my data stays mine - I like that. 'Discovers jobs from multiple boards, scores them against your profile using AI' - YES, this is what I need."

Then they hit Quick Start: "Requires Docker. What the hell is Docker? And what is this `git clone` thing? Is that a command I type somewhere? Where?"

**What Alex feels:**
The product description built excitement. The Quick Start just killed it. Two sentences in and they're already lost.

**What Alex does:**
Googles "what is Docker" and "how to install Docker on Mac."

**Friction level:** 4/5
This is the first major wall. The README assumes the reader knows what Docker is, what a terminal is, and what `git clone` means. Alex knows none of these things.

**What could go wrong:**
- Alex closes the tab entirely ("this is for developers, not for me")
- Alex tries to click on the `git clone` text thinking it's a link
- Alex doesn't know what "OrbStack" is and wonders if they need both

**What would help:**
- A "Never used a terminal before?" expandable section right below Quick Start
- Step-by-step instructions: "1. Install OrbStack (click here, download, drag to Applications). 2. Open the Terminal app on your Mac (it's in Applications > Utilities). 3. Paste this command and press Enter."
- A screenshot of what Terminal looks like with the commands typed in
- Reassurance: "You won't need to write any code. These 2 commands are the only thing you'll type."

---

### Step 3: Understanding They Need Docker

**What Alex sees:**
The word "Docker" with a link to docker.com and an alternative called "OrbStack."

**What Alex thinks:**
"Docker... I've heard engineers mention this in standup meetings. Something about containers? Like... shipping containers? For code? I have absolutely no idea what this does or why I need it. Is this safe to install? Is it going to mess up my laptop?"

**What Alex feels:**
Anxiety. Installing unfamiliar software is a trust decision. Alex doesn't know if Docker is reputable, if it's free, or if it'll slow down their MacBook.

**What Alex does:**
Clicks the OrbStack link, lands on orbstack.dev, sees a clean simple page. Slightly reassured. Clicks Download.

**Friction level:** 3/5
Docker.com is professional enough that Alex trusts it. But they still don't understand WHY they need it.

**What could go wrong:**
- Alex downloads the wrong version (Intel vs Apple Silicon)
- Alex sees Docker's pricing page and thinks they need to pay
- Alex gets confused by Docker's own onboarding and creates an account they don't need
- Alex installs Docker but doesn't open it (daemon not running)

**What would help:**
- One sentence explaining Docker in human terms: "Docker is like a box that runs Kestrel on your computer without installing a bunch of separate pieces. Think of it as the thing that makes setup a one-click process."
- Direct download link to the correct Mac version (detect Apple Silicon vs Intel)
- "OrbStack is free for personal use. You do NOT need to create an account. Docker Desktop also works if you prefer."

---

### Step 4: Installing OrbStack (or Docker Desktop)

**What Alex sees:**
A .dmg file downloads. They open it, see the standard macOS "drag to Applications" screen.

**What Alex thinks:**
"Okay, this part I know - drag the icon to the folder. Done."

**What Alex feels:**
Brief comfort - this is a normal Mac app install.

**What Alex does:**
Drags Docker to Applications, opens it. macOS asks for permissions. Docker starts downloading something. A whale icon appears in the menu bar.

**Friction level:** 2/5
Standard Mac install. Docker's own onboarding might be slightly confusing (it wants you to sign in, do a tutorial) but Alex can skip those.

**What could go wrong:**
- macOS blocks the install ("app from unidentified developer") - Alex needs to go to System Settings > Privacy
- Docker asks to install a "kernel extension" or similar - Alex doesn't know if they should allow it
- Docker takes 3-5 minutes to initialize and Alex thinks it's frozen
- Alex closes OrbStack / Docker Desktop and the daemon stops

**What would help:**
- Kestrel README note: "After installing OrbStack (or Docker Desktop), open it and wait for the icon in your menu bar to stop animating. That means it's ready."
- Note: "Keep OrbStack (or Docker Desktop) running in the background while using Kestrel."

---

### Step 5: Getting the Kestrel Code onto Their Machine

**What Alex sees:**
The README says `git clone https://github.com/pleasedodisturb/kestrel.git && cd kestrel`

**What Alex thinks:**
"git clone? What is git? What is clone? Do I type this somewhere? Where? What's `&&`? What's `cd`?"

Alternatively, Alex notices the green "Code" button on GitHub and sees "Download ZIP." That makes sense to them.

**What Alex feels:**
If they go the terminal route: lost. If they spot Download ZIP: cautiously optimistic.

**What Alex does:**
One of two paths:
1. **ZIP path:** Clicks Code > Download ZIP. Finds it in Downloads. Double-clicks to unzip. Has a folder called `kestrel-main`.
2. **Terminal path (if they read a tutorial):** Opens Terminal (finds it via Spotlight: Cmd+Space, type "Terminal"). Pastes the git clone command. Sees text scrolling. Has no idea what just happened.

**Friction level:** 4/5 (terminal path), 2/5 (ZIP path)
The git clone command is the second major wall for non-technical users. Download ZIP is the obvious alternative but the README doesn't mention it.

**What could go wrong:**
- Alex doesn't have git installed (macOS prompts to install Xcode Command Line Tools - a confusing dialog for non-developers)
- Alex clones/extracts to Downloads and can't find it later
- Alex unzips and doesn't know they need to "cd" into the folder
- The ZIP folder is named `kestrel-main` not `kestrel` - paths in later instructions won't match

**What would help:**
- Explicit alternative: "Don't want to use the command line? Click the green 'Code' button on this page, then 'Download ZIP.' Unzip it and open the folder."
- For terminal users: "Open the Terminal app (press Cmd+Space and type 'Terminal'). Then paste this command exactly as shown and press Enter."
- Suggest a location: "We recommend putting Kestrel in your home folder or Documents."

---

### Step 6: Running setup.sh

**What Alex sees:**
The README says `./setup.sh`

**What Alex thinks (ZIP path):**
"I have a folder with a bunch of files. One of them is called setup.sh. Do I double-click it? What's the ./ thing?"

**What Alex thinks (terminal path):**
"Okay I just did the clone thing. Now I type ./setup.sh? What does that mean?"

**What Alex feels:**
Peak uncertainty. They're about to run a command they don't understand.

**What Alex does:**

If they double-click setup.sh on Mac, it might open in TextEdit (showing the script code) instead of running it. This is a common macOS gotcha.

If they're in Terminal, they type `./setup.sh` and see:

```
Kestrel Setup
=============
Your AI-powered job search system

[ok] Docker is ready
[ok] Created .env from .env.example
     Edit .env to add API keys (optional - works without them)
[ok] Created config/personal.yaml
     Edit it with your name, email, and job preferences

Building and starting Kestrel (this takes 2-3 minutes the first time)...
```

**What Alex feels at this point:**
"Oh shit, it's actually doing something! The [ok] messages are reassuring. '2-3 minutes' - okay I can wait."

**Friction level:** 3/5
If Alex is already in Terminal and in the right directory, this step is actually smooth. The setup.sh output is clear and friendly. The problem is GETTING to this point.

**What could go wrong:**
- "permission denied" error - setup.sh isn't executable. Alex has no idea what `chmod +x setup.sh` means.
- Alex isn't in the right directory. They get "No such file or directory."
- They double-clicked the file instead of running it from Terminal
- They typed `setup.sh` instead of `./setup.sh`

**What would help:**
- The README should say: "In Terminal, make sure you're inside the kestrel folder. Type `ls` and press Enter - you should see setup.sh in the list. If you don't, type `cd ~/Downloads/kestrel-main` (if you downloaded the ZIP) and try again."
- Handle permission issues in the README: "If you get 'permission denied', type `bash setup.sh` instead."
- The setup.sh script itself is well-written. The error messages are clear and actionable. This is a strength.

---

### Step 7: Waiting for Docker to Build

**What Alex sees:**
Terminal output from Docker building images. Lots of scrolling text with unfamiliar terms: "Pulling layers," "Building wheel," "npm install," hash strings.

Then: "Waiting for backend to be ready..."

**What Alex thinks:**
"What is all this? Is it downloading something? Is it installing stuff? It's been 2 minutes and text is still scrolling. Is this normal?"

Then during the health check wait: "It's just sitting there... dots appearing... is it broken? Should I close it?"

**What Alex feels:**
Anxiety during the build. Relief when [ok] messages appear. The 2-3 minute estimate in setup.sh is crucial - without it, Alex would panic.

**What Alex does:**
Waits. Checks their phone. Refreshes LinkedIn out of habit.

**Friction level:** 2/5
The wait is manageable because setup.sh sets expectations ("2-3 minutes the first time"). The [ok] confirmation at the end is a good UX moment.

**What could go wrong:**
- Build takes longer than 3 minutes on a slower connection (downloading Docker images)
- A build step fails with a cryptic npm or pip error
- Alex gets impatient and Ctrl+C's the process
- Docker runtime runs out of disk space

**What would help:**
- Progress indicators during the build (setup.sh currently pipes to `tail -5`, which is good but could be better)
- "If this takes more than 5 minutes, that's okay - your internet connection might be slow. Do NOT close this window."
- A spinner or periodic "still working..." messages during the health check loop

---

### Step 8: Opening the Dashboard

**What Alex sees:**
Setup completes with:

```
Kestrel is running!

Dashboard:  http://localhost:8101
API docs:   http://localhost:8100/docs

Next steps:
1. Open http://localhost:8101
2. Go to Settings > Profiles and add your details
3. Add your first job application to the pipeline
```

Alex clicks or copies the URL, opens Chrome, sees the Kestrel dashboard.

**What Alex thinks:**
"Holy shit, it worked! There's an actual app in my browser! This looks like a real product, not some janky developer tool."

**What Alex feels:**
A dopamine hit. The transition from scary terminal stuff to a polished web UI is the emotional peak of the setup journey. This is Kestrel's "aha" moment.

**What Alex does:**
Clicks around. Looks at the navigation. Sees the Kanban board.

**Friction level:** 1/5
This is the lowest friction point. The browser interface is familiar territory for Alex.

**What could go wrong:**
- Alex types "localhost:8101" without "http://" and the browser searches Google for it
- Alex bookmarks it and later opens the bookmark when Docker isn't running - gets a connection refused error with no explanation
- Port 8101 is in use by something else

**What would help:**
- Make the URL clickable in the terminal output (most terminals support this)
- setup.sh could auto-open the browser: `open http://localhost:8101` on Mac
- A "Kestrel isn't loading?" link in the README troubleshooting section

---

### Step 9: Seeing the Empty Kanban Board

**What Alex sees:**
A Kanban board with columns (Bookmarked, Applied, Interviewing, etc.) but no cards. An empty state.

**What Alex thinks:**
"Okay, this is like Trello. I get the concept. But it's empty. What do I do now? Do I add jobs manually? Where's the AI that finds jobs for me?"

**What Alex feels:**
Slight deflation. They came here for automated job discovery and AI scoring, but they're looking at an empty board with no obvious "get started" action.

**What Alex does:**
Looks for a button that says "Find Jobs" or "Discover" or "Search." Clicks around the navigation.

**Friction level:** 3/5
Empty states are always a UX risk. The user has momentum from a successful install - the empty board can kill it.

**What could go wrong:**
- Alex doesn't know where to start and feels overwhelmed
- Alex tries to manually add a job but gives up because it feels like data entry
- Alex expects AI-powered job discovery to work immediately and doesn't realize they need to set up a profile first

**What would help:**
- An onboarding wizard or welcome modal: "Welcome to Kestrel! Let's get you set up in 3 steps: 1. Tell us about you, 2. Set your job preferences, 3. Find your first matches"
- Empty state content on the Kanban board: "Your pipeline is empty. Add your first job application, or set up Discovery to find jobs automatically."
- A "Quick Add" button that's prominent and inviting
- A sample/demo application already in the pipeline so the board doesn't look dead

---

### Step 10: Setting Up Their Profile

**What Alex sees:**
The setup.sh output mentioned "Go to Settings > Profiles and add your details." Alex navigates to Settings and finds profile fields.

**What Alex thinks:**
"Name, email, job preferences - this makes sense. Target roles, locations, salary range - oh nice, I can tell it exactly what I'm looking for."

**What Alex feels:**
Engaged. This is familiar territory - filling out a profile, like any other platform.

**What Alex does:**
Fills in their details. Name, email, target roles ("Marketing Operations Manager," "Marketing Manager," "Growth Marketing"), location (Berlin, Remote), salary range (65,000-85,000 EUR).

**Friction level:** 1/5
Profile setup is straightforward and familiar. This is a UX strength.

**What could go wrong:**
- Alex doesn't know what format to use for salary (yearly? monthly? with or without EUR symbol?)
- The profile fields reference technical concepts Alex doesn't understand
- Alex fills it out but doesn't realize this feeds the AI scoring system

**What would help:**
- Inline hints: "This is what the AI uses to score job listings against your background."
- Pre-filled example values (greyed out) showing the expected format
- A "Why does this matter?" tooltip explaining how the profile connects to scoring

---

### Step 11: Understanding AI Provider Options

**What Alex sees:**
Somewhere in the UI or in the terminal output, mentions of "mock AI" vs "real AI" and "OpenRouter."

**What Alex thinks:**
"Mock AI? Is that fake AI? What does 'mock' mean? It says I can use it offline - that's good I guess? But I want the REAL AI that scores jobs properly. What's OpenRouter? Another thing I need to sign up for?"

**What Alex feels:**
Confused by the terminology. "Mock" sounds negative - like "mockery" or "fake." They want the real thing but don't want to deal with yet another signup.

**What Alex does:**
Tries the mock provider first (since it's the default). Sees that scoring returns data. Wonders if it's "real" or just placeholder numbers.

**Friction level:** 3/5
The mock vs real AI distinction is clear to developers but confusing to regular users. "Mock" is jargon.

**What could go wrong:**
- Alex uses mock mode, gets scores, trusts them, and makes decisions based on fake data
- Alex doesn't realize mock mode exists and thinks the AI is broken
- Alex wants real AI but gets overwhelmed by the API key process

**What would help:**
- Rename "mock" to something clearer: "Demo Mode" or "Offline Mode" or "Preview Mode"
- A clear indicator in the UI: "You're using Demo Mode. Scores are simulated. Connect a real AI provider for personalized results."
- A one-click path to enable real AI from within the UI (Settings > AI > "Enable real AI scoring")

---

### Step 12: Getting an OpenRouter API Key

**What Alex sees:**
Instructions to "Sign up at openrouter.ai and grab an API key."

**What Alex thinks:**
"What IS an API key? Is it like a password? Why do I need a key for AI? How much does this cost? Am I going to get charged a lot of money?"

**What Alex feels:**
Financial anxiety layered on top of technical confusion. They're unemployed and watching every euro.

**What Alex does:**
Goes to openrouter.ai. Creates an account. Navigates to the API key section. Copies a string that looks like `sk-or-v1-abc123...`. Goes back to the .env file. Realizes they need to edit a text file.

**Friction level:** 4/5
This step combines multiple unknowns: what an API key is, what it costs, where to put it, and how to edit a .env file. It's the third major wall.

**What could go wrong:**
- Alex doesn't understand OpenRouter's pricing and fears a surprise bill
- Alex copies the key with extra whitespace or newlines
- Alex doesn't know how to edit the .env file (it's a hidden file on macOS - Finder won't show it by default)
- Alex edits the wrong file or puts the key in the wrong place
- Alex restarts the wrong thing or doesn't restart at all

**What would help:**
- Cost transparency: "OpenRouter charges per AI call. Typical usage for job searching costs $1-3 per month. You can set a spending limit."
- Step-by-step with screenshots: "1. Go to openrouter.ai and create a free account. 2. Click 'API Keys' in the sidebar. 3. Click 'Create Key.' 4. Copy the key (it starts with sk-or-)."
- A way to enter the API key through the web UI instead of editing a .env file
- Explain .env: "The .env file is a settings file in your Kestrel folder. To edit it, open Terminal, type `open .env` and press Enter. It'll open in TextEdit."

---

### Step 13: Adding Their First Job Application

**What Alex sees:**
An "Add Application" button or form. Fields for company name, role, URL, salary, notes.

**What Alex thinks:**
"This is like a CRM for my job search. Okay, I can do this. Let me add that Spotify role I applied to last week."

**What Alex feels:**
Competent. This is data entry they understand.

**What Alex does:**
Adds a job: Company "Spotify," Role "Marketing Operations Lead," URL from LinkedIn, salary range, notes about the role.

**Friction level:** 1/5
Adding a single application is straightforward. This is familiar from Notion, Airtable, or any other tool.

**What could go wrong:**
- Alex doesn't know what "stage" to put it in (Bookmarked? Applied? What's the difference?)
- The form requires fields Alex doesn't have (like a specific salary number)
- It feels like manual data entry - "I thought this was automated?"

**What would help:**
- Smart defaults: if no stage is selected, default to "Bookmarked"
- Optional fields should be clearly marked as optional
- A "paste a job URL and we'll fill in the details" feature would be the dream

---

### Step 14: Setting Up Job Discovery

**What Alex sees:**
A Discovery section where they can create "search profiles" - defining roles, locations, keywords, and salary ranges to search for.

**What Alex thinks:**
"Oh, THIS is the automated part! I tell it what I'm looking for and it goes out and finds jobs? Like a recruiter that works for me? Hell yes."

**What Alex feels:**
Excited again. This is the core value proposition hitting home.

**What Alex does:**
Creates a search profile: "Marketing Operations" roles, Berlin + Remote, 65k-85k EUR. Hits "Run Search" or equivalent.

**Friction level:** 2/5
The concept is clear. The UX depends on how the search profile form is designed.

**What could go wrong:**
- Alex uses search terms that are too specific or too broad
- The search takes a while and there's no progress indicator
- Results come back but Alex doesn't understand the scoring
- No results come back and Alex thinks it's broken (search terms might not match board formatting)

**What would help:**
- Example search profiles or templates: "Here's what a typical Marketing professional's search looks like"
- Real-time feedback: "Searching 4 job boards... Found 23 new listings... Scoring..."
- Explanations next to scores: "This role scored 7.2/10 because: strong skill match (8/10), salary in range (7/10), location match (9/10)"

---

### Step 15: Seeing Their First Scored Results

**What Alex sees:**
A list of job postings, each with a score from 0-10, pulled from multiple job boards. The highest-scoring ones rise to the top.

**What Alex thinks:**
"Wait, this actually works? It found 15 marketing ops roles in Berlin and ranked them for ME? The top one is an 8.4 at a company I've never heard of - but looking at the breakdown, it's actually a great fit. I would have never found this on LinkedIn."

**What Alex feels:**
The "holy shit" moment. This is the Time To First Value - the point where Kestrel proves itself. If Alex reaches this moment, they're a retained user.

**What Alex does:**
Clicks into the top-scoring results. Reads the detailed breakdowns. Bookmarks the ones they want to apply to. Maybe drags one to "Applied" on the Kanban board.

**Friction level:** 1/5
Browsing scored results is intuitive. The value is immediately apparent.

**What could go wrong:**
- Mock AI scores don't feel personalized (because they aren't) - Alex questions the value
- Real AI scores require OpenRouter to be set up - Alex hasn't done that yet
- Scores are numbers without explanation, making them meaningless
- Results are stale or from job boards Alex already checked

**What would help:**
- Score breakdowns should be visible without clicking: "Skill match: 8, Seniority: 7, Salary: 9, Location: 10"
- A clear label: "AI-scored based on YOUR profile" (reinforces personalization)
- Quick action buttons: "Save to Pipeline" / "Dismiss" / "Apply Now"

---

## 3. Alex's Journey Map (Rainy Day)

### Failure 1: Docker Daemon Isn't Running

**What happens:**
Alex runs `./setup.sh` and gets:

```
Docker is installed but not running.

  Start OrbStack or Docker Desktop, then run this script again.
```

**What Alex sees:**
An error message, but a clear one.

**What Alex feels:**
"Oh, I need to start Docker first. Where is it?" Mild annoyance but not panic.

**Current recovery path:**
The error message tells them to start OrbStack or Docker Desktop. This is good — it's clear and actionable.

**Ideal recovery path:**
Current path is actually solid. Could be improved with: "Look for the OrbStack icon or whale icon in your menu bar (top of screen). If it's not there, open OrbStack (or Docker Desktop) from your Applications folder." On Mac, `setup.sh` attempts to start the Docker runtime automatically: `open -a OrbStack` or `open -a Docker`.

---

### Failure 2: Port 8100 Already in Use

**What happens:**
Docker starts but port 8100 is used by another service. The backend container fails.

**What Alex sees:**
Docker build output completes, then the health check times out:

```
Backend didn't respond in 60 seconds. This might be normal on first run.

  Check logs:    docker compose logs backend
  Retry:         docker compose restart backend
  Start fresh:   docker compose down -v && docker compose up -d --build
```

**What Alex feels:**
"What the fuck? It said it was building and then it failed. Check logs? I don't know how to read logs. What's a 'compose'?"

**Current recovery path:**
The error message gives commands to try but doesn't diagnose the actual problem (port conflict). The user has to run `docker compose logs backend` and interpret the output themselves.

**Ideal recovery path:**
`setup.sh` should check if port 8100 is in use BEFORE trying to start:

```bash
if lsof -i :8100 >/dev/null 2>&1; then
    echo "Port 8100 is already in use by another program."
    echo "Either close that program, or edit .env and change PORT to 8200."
    echo "Then run this script again."
    exit 1
fi
```

Human-readable error with a specific fix.

---

### Failure 3: They Typed the Wrong Command

**What happens:**
Alex types `setup.sh` instead of `./setup.sh`, or `sh setup.sh`, or they're in the wrong directory.

**What Alex sees:**

- `setup.sh: command not found` (if they omit `./`)
- `No such file or directory` (if they're in the wrong directory)
- Nothing at all (if they typed it into Spotlight instead of Terminal)

**What Alex feels:**
"I did exactly what it said and it doesn't work. Typical." Frustration building.

**Current recovery path:**
None. The README doesn't anticipate these errors.

**Ideal recovery path:**
Add to README:
- "Make sure you're in the Kestrel folder. If you're not sure, type `pwd` and press Enter - it should end with `/kestrel`"
- "If you get 'command not found', try `bash setup.sh` instead"
- "If you get 'No such file or directory', type `cd` followed by the path to where you put Kestrel. For example: `cd ~/Downloads/kestrel-main`"

---

### Failure 4: setup.sh Fails Midway

**What happens:**
Docker build fails due to network issues, npm install failure, or Python dependency conflict.

**What Alex sees:**
A wall of red error text. Words like "FATAL," "ERROR," "failed to fetch," hash strings, version numbers.

**What Alex feels:**
"I have no idea what any of this means. It's broken. I broke it. This tool is not for people like me."

This is the highest drop-off risk in the entire journey.

**Current recovery path:**
The setup script doesn't handle mid-build failures gracefully. Docker's error output is aimed at developers.

**Ideal recovery path:**
- `setup.sh` should catch common failure modes and translate them:
  - Network failure: "Looks like the download failed - check your internet connection and try again."
  - Disk space: "Docker needs about 2 GB of disk space. You might need to free up some room."
  - Generic: "Something went wrong during the build. This is usually temporary. Try running `./setup.sh` again. If it keeps failing, copy the last 10 lines of output and open an issue at [link]."
- Add a `--verbose` flag for debugging, keep default output minimal and human-readable

---

### Failure 5: API Key Pasted Wrong

**What happens:**
Alex copies the OpenRouter API key but accidentally includes a trailing space, newline, or only copies part of it.

**What Alex sees:**
After restarting, AI features silently return errors or fall back to mock data. No obvious indication that the key is wrong.

**What Alex feels:**
"I set it up but it's still giving me the same fake-looking scores. Did it even work?"

**Current recovery path:**
The health endpoint (`/api/ai/health`) would show the provider status, but Alex doesn't know this exists.

**Ideal recovery path:**
- Validate the API key format on startup: "Your OPENROUTER_API_KEY doesn't look right (it should start with 'sk-or-'). Please check .env and try again."
- Show provider status in the UI Settings page: a green/red indicator with "Connected to OpenRouter" or "API key invalid"
- Test the key immediately after the user enters it (before requiring a restart)

---

### Failure 6: Browser Shows a Blank Page

**What happens:**
Alex opens `http://localhost:8101` and sees a white page, or a "connection refused" error.

**What Alex sees:**
Chrome's "This site can't be reached" error, or a blank white page with nothing on it.

**What Alex feels:**
"All that work for nothing. It's broken." Defeat.

**Current recovery path:**
The README troubleshooting says to wait 30 seconds and check backend logs. Not very helpful for someone who doesn't know what logs are.

**Ideal recovery path:**
- A simple diagnostic page: if the frontend loads but can't reach the backend, show "Kestrel is starting up... please wait" instead of a blank page
- `setup.sh` already waits for the health check - if it passed, the page should work. If it didn't pass, setup.sh already gives instructions.
- Add a "Is Kestrel running?" check the user can do: "Open a new Terminal window and type: `docker ps`. You should see two containers with 'kestrel' in the name."

---

### Failure 7: They Don't Understand the Scoring System

**What happens:**
Alex gets scores back (7.2, 5.8, 3.1) but doesn't know what they mean or trust them.

**What Alex sees:**
Numbers next to job listings. Maybe a breakdown with categories they don't fully understand.

**What Alex feels:**
"Why did this one get a 5 and that one got an 8? The 5-rated one actually looks good to me. Is this thing even accurate?"

**Current recovery path:**
Score breakdowns exist but the criteria might not be intuitive to a non-technical user.

**Ideal recovery path:**
- Plain-language score explanations: "This role scored high because it matches your marketing background, the salary is in your range, and you'd be working in Berlin."
- "You rated higher than 80% of applicants we'd expect for this role" (confidence framing)
- Let users give feedback: "Is this score wrong? Tell us why and we'll improve." This builds trust even if the feedback mechanism is simple.

---

### Failure 8: Alex Feels Overwhelmed and Wants to Quit

**What happens:**
At any point in the journey, the accumulated friction becomes too much. Alex feels like this tool wasn't made for them.

**What Alex sees:**
Any of the above errors, or simply too many features, too many settings, too much jargon.

**What Alex feels:**
"This is a developer tool pretending to be a product. I'm not a developer. I'm wasting time I should be spending on applications."

**Current recovery path:**
None. There's no "I'm lost" escape hatch.

**Ideal recovery path:**
- A persistent "Need help?" link in the footer of the UI
- A "Stuck? Here's what to try" section that's always one click away
- A community link (Discord, GitHub Discussions) where they can ask questions
- A "Give me the simplest version" mode that hides advanced features
- Honestly: a hosted version that requires zero setup. That's the real answer for Alex.

---

## 4. Friction Heatmap

| Step | Description | Friction (1-5) | Drop-off Risk | Current Mitigation | Recommended Fix | Priority |
|:-----|:------------|:---------------|:--------------|:-------------------|:----------------|:---------|
| 1 | Landing on GitHub | 2 | Low | README is readable | Add screenshot/GIF of dashboard, "no coding required" badge | P2 |
| 2 | Reading README Quick Start | 4 | **Critical** | Clear 2-step instructions | Add "New to command line?" expandable section | P0 |
| 3 | Understanding Docker | 3 | High | Link to docker.com | One-sentence human explanation of Docker | P1 |
| 4 | Installing OrbStack / Docker Desktop | 2 | Medium | Standard Mac install | Note about waiting for icon, keeping Docker runtime open | P2 |
| 5 | Getting code (clone/ZIP) | 4 | **Critical** | git clone command | Add Download ZIP path, explain Terminal basics | P0 |
| 6 | Running setup.sh | 3 | High | Good error messages in script | Add "permission denied" fix, directory navigation help | P1 |
| 7 | Waiting for build | 2 | Low | Time estimate in script | Add "don't close this window" note, periodic status | P3 |
| 8 | Opening dashboard | 1 | Low | URL printed clearly | Auto-open browser, clickable URL | P3 |
| 9 | Empty Kanban board | 3 | High | None | Onboarding wizard, empty state guidance, sample data | P1 |
| 10 | Profile setup | 1 | Low | Guided via setup output | Inline hints connecting profile to scoring | P3 |
| 11 | Understanding mock vs real AI | 3 | Medium | README explains it | Rename "mock" to "Demo Mode", in-UI indicator | P1 |
| 12 | Getting OpenRouter API key | 4 | **Critical** | Instructions in README | In-app API key entry, cost transparency, step-by-step guide | P0 |
| 13 | Adding first application | 1 | Low | Standard form | URL auto-fill, smart defaults | P3 |
| 14 | Setting up discovery | 2 | Medium | Search profile form | Templates, example profiles, progress indicator | P2 |
| 15 | Seeing scored results | 1 | Low | Scores displayed | Plain-language explanations, trust-building UI | P2 |

**Critical drop-off points (P0):** Steps 2, 5, and 12. These three moments lose the most users. Fix these first.

---

## 5. The Jargon Barrier

| Term | Where It Appears | What Alex Thinks It Means | What It Actually Means | Suggested Replacement or Explanation |
|:-----|:-----------------|:--------------------------|:-----------------------|:-------------------------------------|
| GitHub | Landing page URL | "Some kind of website for code?" | A platform for hosting and collaborating on code projects | No replacement needed, but add: "GitHub is where Kestrel's code lives. Think of it as the download page." |
| Repository (repo) | GitHub page, CONTRIBUTING.md | "A library? A storage place?" | A project folder tracked by git version control | "project" or "folder" |
| Clone | README Quick Start | "Make a copy? Like cloning a sheep?" | Download a copy of the code from GitHub to your computer | "download" - literally say "Download Kestrel to your computer" |
| Fork | CONTRIBUTING.md | "A fork in the road?" | Create your own copy of the project on GitHub to make changes | Only relevant for contributors, not users |
| CLI | README, various | "No idea" | Command Line Interface - a text-based way to interact with software | "terminal commands" or just "commands you type" |
| Terminal | Implied in Quick Start | "The TV show? Oh wait, the black screen thing hackers use in movies" | The application on macOS where you type commands | "Terminal (the app on your Mac where you type commands - find it by pressing Cmd+Space and typing Terminal)" |
| Docker | README Quick Start | "Something with shipping containers and whales" | Software that packages applications so they run the same on any computer | "Docker is an app that runs Kestrel in a self-contained box on your computer. Install it like any other app." |
| Container | README, error messages | "Like a shipping container?" | An isolated environment where an application runs | "Kestrel's environment" or just don't expose this term to users |
| API | Throughout | "Vaguely technical - something apps use to talk to each other?" | Application Programming Interface - a way for software to communicate | "connection" or "service" depending on context |
| API Key | README, .env | "A password for the API?" | A secret string that authenticates you with a service | "Your personal access code" or "your secret key (like a password)" |
| Token | .env.example | "Like an arcade token?" | Same as API key in most contexts | "key" or "access code" |
| Environment Variable | README Configuration | "No idea whatsoever" | A setting stored outside the code that configures how the app behaves | "setting" - and explain: "Environment variables are settings stored in the .env file" |
| .env file | README, setup.sh | "What file? I don't see any .env file in the folder" | A hidden configuration file (macOS hides files starting with a dot) | "settings file (.env)" - and explain that it's hidden on Mac: "Files starting with a dot are hidden on macOS. It's there, you just can't see it in Finder by default." |
| YAML | config/personal.yaml | "Yet Another... something?" | A human-readable data format for configuration files | "settings file" - users don't need to know the format name |
| JSON | API docs | "Probably a person's name" | A data format used for sending information between computers | Not user-facing, no change needed |
| SQLite | README, .env | "SQL-ite? Sequel light?" | A lightweight database that stores data in a single file | "database" - users don't need to know which kind |
| FastAPI | README badges | "Fast API? A fast connection?" | A Python web framework for building APIs | Not user-facing, don't expose this to users |
| React | README badges | "Heard of it - Facebook thing?" | A JavaScript library for building user interfaces | Not user-facing, don't expose this to users |
| Mock provider | README, .env | "Mock as in fake? It's giving me fake results?" | A simulated AI that returns realistic but pre-generated data for testing | "Demo Mode" or "Offline Mode" or "Preview Mode" |
| OpenRouter | README | "A router for the internet? A networking thing?" | A service that gives you access to multiple AI models through one account | "OpenRouter (an AI service - think of it as one account that connects you to ChatGPT, Claude, and other AIs)" |
| Health check | setup.sh, API | "Like a doctor's visit?" | An automated test to see if the application is running correctly | "checking if Kestrel is ready" |
| Endpoint | API docs | "End... point?" | A specific URL where the API responds to requests | Not user-facing, no change needed |
| Kanban | README, UI | "A Japanese word? Something from Toyota?" | A visual project management method using columns and cards | "Pipeline board" or just "your job board" - the visual is self-explanatory |
| Pipeline | Throughout | "Like a plumbing pipe?" | The series of stages an application goes through (bookmarked to offer to accepted) | "Your application tracker" or "stages" |
| Scoring | Throughout | "Like a test score?" | AI-generated rating of how well a job matches your profile | "fit rating" or "match score" - actually "score" is fine, it's intuitive |
| docker compose | Error messages, README | "Compose like music?" | A Docker tool for running multiple containers together | "restart Kestrel" instead of "docker compose restart" |
| Alembic | Project structure | "An alchemy thing?" | A database migration tool that updates the database structure | Never expose this to users |
| Pydantic | Project structure | "No idea" | A Python library for data validation | Never expose this to users |
| Uvicorn | CONTRIBUTING.md, DEPLOY.md | "A unicorn?" | A Python web server | Never expose this to users |

---

## 6. FAQ for Non-Technical Users

### Do I need to know how to code to use this?

No. You'll need to type a total of 2 commands in the Terminal app to get Kestrel running. After that, everything happens through a normal web interface in your browser - point, click, drag, and drop. The terminal commands are copy-paste, not coding.

### What is Docker and why do I need it?

Docker is an app you install on your computer. Think of it as a box that runs Kestrel inside it, keeping everything tidy and self-contained. Without Docker, you'd need to install Python, Node.js, and a bunch of other developer tools. Docker does all of that for you.

OrbStack (recommended on Mac) and Docker Desktop are both free for personal use. You don't need to create an account (skip the sign-up screen if one appears).

### Is my data safe? Where does it go?

Your data stays entirely on your computer. Kestrel stores everything in a local database file (it's in the `data/` folder inside your Kestrel directory). Nothing is uploaded to the cloud, no account is needed, and no one can see your applications, scores, or profile. That's the whole point of "self-hosted."

The only external connection Kestrel makes is to job boards (to find listings) and to the AI service (if you enable real AI scoring). Even then, the AI service only sees the job description and your profile summary, not your personal details.

### What does "Demo Mode" (mock AI) mean? Is it fake?

When you first install Kestrel, it runs in Demo Mode. This means the AI features (scoring, coaching, interview prep) return pre-generated example data instead of real AI analysis. It's designed so you can explore all the features without needing to sign up for anything or spend money.

The data looks realistic but it's not personalized to you. To get real, personalized AI scoring, you'll need to connect an AI provider (we recommend OpenRouter - takes about 5 minutes to set up).

### Do I have to pay for anything?

Kestrel itself is completely free and open source.

If you want real AI scoring (recommended), you'll need an OpenRouter account. OpenRouter charges per AI call - typical job search usage costs around $1-3 per month, sometimes less. You can set a spending limit on your account so you never get a surprise bill.

Everything else - the pipeline board, application tracking, discovery, calendar integration - works without any paid service.

### I'm stuck at the "git clone" step. What do I do?

Skip it. On the Kestrel GitHub page, click the green "Code" button, then click "Download ZIP." This downloads Kestrel as a regular folder. Unzip it (double-click the .zip file), and you'll have a folder called `kestrel-main`.

Then open Terminal (press Cmd+Space, type "Terminal", press Enter), and type:

```
cd ~/Downloads/kestrel-main
bash setup.sh
```

Press Enter after each line.

### I'm stuck at the "./setup.sh" step. What do I do?

A few common issues:

1. **"permission denied"** - Type `bash setup.sh` instead of `./setup.sh`
2. **"No such file or directory"** - You're in the wrong folder. Type `ls` and press Enter. If you don't see `setup.sh` in the list, you need to navigate to the Kestrel folder first. Type `cd ~/Downloads/kestrel-main` (or wherever you put it).
3. **"Docker not found"** - Install OrbStack from https://orbstack.dev (or Docker Desktop from https://docker.com) first.
4. **"Docker is installed but not running"** - Open OrbStack or Docker Desktop and wait for the icon in your menu bar to stop animating.

### Can I use this on Windows?

Yes. Install Docker Desktop for Windows (it's on the docker.com download page — OrbStack is Mac-only). Instead of Terminal, you'll use PowerShell or Command Prompt. The setup commands are the same. Windows users might want to use WSL2 (Windows Subsystem for Linux) for the best experience — Docker Desktop for Windows will prompt you to enable it.

### What if I just want to try it without all the setup?

We hear you. A hosted demo where you can click a link and start using Kestrel without installing anything is on the roadmap. For now, the Docker setup is the only path - but it's genuinely a 5-10 minute process once you have Docker installed.

If you're technical enough to have a GitHub account, you can try GitHub Codespaces - it runs everything in the cloud and you don't install anything on your machine.

### How is this different from LinkedIn or Indeed?

LinkedIn and Indeed show you the same jobs they show everyone else. You apply, your resume goes into a pile with hundreds of others, and you mostly hear nothing back. "Easy Apply" is easy for everyone, which means more competition per role.

Kestrel is different in three ways:

1. **It searches multiple boards at once** - Indeed, LinkedIn, Glassdoor, and more, in one search. You find jobs that aren't on the platform you usually check.
2. **It scores jobs against YOUR profile** - Instead of scrolling through 200 listings and guessing which ones fit, Kestrel tells you which ones are actually worth your time. A 9/10 match is worth an hour crafting the perfect application. A 4/10 is not.
3. **Your data is yours** - No recruiter spam, no data selling, no "premium" upsell. It runs on your computer.

### I closed Terminal/restarted my computer. How do I start Kestrel again?

Open Terminal and type:

```
cd ~/Downloads/kestrel-main
docker compose up -d
```

Then open http://localhost:8101 in your browser. Your data is still there - nothing is lost.

To stop Kestrel: open Terminal and type `docker compose down`

### What does the score number (0-10) actually mean?

The AI analyzes the job listing and compares it to your profile across several factors:

- **Skill match** - Do your skills match what they're asking for?
- **Seniority fit** - Is this the right level for your experience?
- **Salary alignment** - Is the compensation in your target range?
- **Location** - Does it match your preferred locations (including remote)?
- **Career trajectory** - Does this role move you in the direction you want to go?

A score of 8+ means "strong fit - worth applying." 5-7 means "decent fit, review the details." Below 5 means "probably not worth your time."

In Demo Mode, scores are simulated. With a real AI provider connected, they're personalized to your specific background.

---

## 7. Recommended Product Changes

### README Changes (P0 - Do First)

1. **Add a hero screenshot or GIF** at the top of the README showing the dashboard with data. Alex needs to see what they're working toward.

2. **Rewrite Quick Start for two audiences:**

```markdown
## Quick Start

### Option A: I'm comfortable with the command line
Requires [Docker](https://docker.com).
\`\`\`bash
git clone https://github.com/pleasedodisturb/kestrel.git && cd kestrel
./setup.sh
\`\`\`

### Option B: I've never used a terminal before
1. Install [OrbStack](https://orbstack.dev) (recommended for Mac) or [Docker Desktop](https://www.docker.com/products/docker-desktop/) — it's a free app, install it like any other Mac/Windows app
2. Open the app and wait for it to finish starting (icon in menu bar stops animating)
3. Download Kestrel: click the green "Code" button above, then "Download ZIP"
4. Unzip the downloaded file (double-click it)
5. Open Terminal (Mac: press Cmd+Space, type "Terminal", press Enter)
6. Type these two commands, pressing Enter after each:
   \`\`\`
   cd ~/Downloads/kestrel-main
   bash setup.sh
   \`\`\`
7. Wait 2-3 minutes. When it says "Kestrel is running!", open http://localhost:8101
```

3. **Add a "No coding required" badge** next to the tech badges at the top.

4. **Rename "mock" to "Demo Mode"** everywhere in the README and .env.example.

5. **Add a "What you'll need" section** before Quick Start:
   - A computer (Mac, Windows, or Linux)
   - About 15 minutes for first-time setup
   - 2 GB of free disk space
   - An internet connection (for the initial setup)

### setup.sh Improvements (P1)

1. **Add port conflict detection** before starting Docker:
   ```bash
   if lsof -i :8100 >/dev/null 2>&1; then
       echo "Port 8100 is already in use."
       echo "Close the other program using it, or edit .env to change PORT."
       exit 1
   fi
   ```

2. **Auto-open the browser on success** (Mac):
   ```bash
   if [[ "$OSTYPE" == "darwin"* ]]; then
       open "http://localhost:8101"
   fi
   ```

3. **Add periodic "still working" messages** during the Docker build.

4. **Add a `--reset` flag** that cleanly tears down and rebuilds everything.

5. **Print a "Common issues" section** when the health check fails, not just docker commands.

### New Files Needed (P1)

1. **QUICKSTART.md** - A standalone getting-started guide for non-technical users, with screenshots. Link to it prominently from the README.

2. **TROUBLESHOOTING.md** - An expanded version of the README troubleshooting section, covering every error message a user might see with plain-language explanations.

3. **docs/getting-an-api-key.md** - Step-by-step guide (with screenshots) for creating an OpenRouter account and getting an API key. Include cost information.

### UI Changes (P0-P1)

1. **Welcome/onboarding wizard** (P0) - On first launch (empty database), show a 3-step wizard:
   - Step 1: "Tell us about you" (profile basics)
   - Step 2: "What are you looking for?" (role, location, salary)
   - Step 3: "Find your first matches" (run discovery)

2. **Empty state guidance on Kanban board** (P1) - When the pipeline is empty, show helpful content instead of empty columns: "Your pipeline is empty. Here are three ways to get started: [Add a job manually] [Set up auto-discovery] [Import from a spreadsheet]"

3. **AI provider status indicator** (P1) - A small badge in the header or settings showing "Demo Mode" or "AI Connected (OpenRouter)" so users always know which mode they're in.

4. **In-app API key configuration** (P0) - Let users enter their OpenRouter API key through the Settings page instead of editing .env files manually. Save it to .env and restart the backend.

5. **Score explanations** (P1) - Next to every score, a tooltip or expandable section explaining WHY this job got this score in plain language.

6. **"I'm stuck" help button** (P2) - Persistent help link in the footer with common solutions and community links.

### Documentation Additions (P2)

1. **Video walkthrough** - A 5-minute video showing the entire setup process from scratch. Host on YouTube, embed in README.

2. **Screenshot walkthrough** - For users who prefer reading, a visual step-by-step in QUICKSTART.md with annotated screenshots of every stage.

3. **Glossary page** - Based on the Jargon Barrier section above, an in-app or docs glossary that defines terms in human language.

### Alternative Install Paths (P1-P2)

1. **GitHub Codespaces support** (P1) - Add a `.devcontainer/devcontainer.json` so users can click "Open in Codespaces" and get a running instance without installing anything locally. This is the single biggest friction reducer for non-technical users with a GitHub account.

2. **Cloud-hosted demo** (P2) - A read-only demo instance at `demo.kestrel.app` (or similar) where people can explore the UI without installing anything. Pre-populated with sample data.

3. **One-click deploy buttons** (P2) - "Deploy to Railway" / "Deploy to Fly.io" buttons in the README. DEPLOY.md already has instructions - make them more prominent and add actual one-click buttons.

---

## 8. Test Scenarios

### Automated (CI/Script-Based)

| ID | Scenario | Test Method | Pass Criteria |
|:---|:---------|:------------|:--------------|
| A1 | Fresh clone to running instance | Shell script | `setup.sh` completes, health check passes, frontend returns 200 on `:8101` |
| A2 | Download ZIP to running instance | Shell script | Same as A1 but starting from extracted ZIP (folder named `kestrel-main`) |
| A3 | setup.sh with Docker not running | Shell script | Script exits with clear error message containing "Docker" and "not running" |
| A4 | setup.sh with port 8100 in use | Shell script (bind port first) | Script exits with clear error about port conflict |
| A5 | setup.sh re-run (idempotent) | Shell script | Running setup.sh twice doesn't break anything, skips already-done steps |
| A6 | Invalid API key in .env | Shell script | Backend starts, health endpoint reports provider error, UI shows Demo Mode |
| A7 | Profile creation via API | HTTP test | POST to profile endpoint returns 201, data persists |
| A8 | Discovery run with mock provider | HTTP test | Search returns scored results with mock data |
| A9 | Application CRUD cycle | HTTP test | Create, read, update status, delete - all return expected codes |
| A10 | Time to first health check pass | Shell script with timer | Under 180 seconds on a modern machine with cached Docker images |

### Manual (Human Tester Checklist)

**Tester profile:** Non-technical person who has never used a terminal. Ideally someone currently job searching.

Pre-test: Provide tester with only the GitHub URL. No other instructions.

- [ ] **M1:** Can the tester find the "how to install" instructions within 60 seconds of landing on the GitHub page?
- [ ] **M2:** Can the tester install OrbStack (or Docker Desktop) without assistance? Note time taken.
- [ ] **M3:** Can the tester download/clone Kestrel without assistance? Which method did they choose?
- [ ] **M4:** Can the tester run setup.sh without assistance? Note any errors encountered.
- [ ] **M5:** Does the tester open the correct URL after setup completes?
- [ ] **M6:** Can the tester navigate to profile setup without assistance?
- [ ] **M7:** Can the tester add their first job application within 5 minutes of seeing the dashboard?
- [ ] **M8:** Can the tester set up job discovery without assistance?
- [ ] **M9:** Does the tester understand what the scores mean?
- [ ] **M10:** Does the tester understand the difference between Demo Mode and real AI?
- [ ] **M11:** If they want real AI, can they set up an OpenRouter key without assistance?
- [ ] **M12:** After 30 minutes total, does the tester say they would keep using the tool?
- [ ] **M13:** What questions did the tester ask during the session? (Record all of them - these become FAQ entries)
- [ ] **M14:** At what point (if any) did the tester want to give up? Why?

### Metrics to Track

| Metric | Target | How to Measure |
|:-------|:-------|:---------------|
| Time to first value (TTFV) | Under 15 minutes | From GitHub page to first scored job result |
| Setup completion rate | 80%+ | Track how many people who start setup.sh finish successfully |
| Drop-off point | Identify top 3 | Survey/observation: where do people stop? |
| Support questions asked | Under 3 per user | Count questions in Discord/Issues during beta |
| "Would you keep using this?" | 70%+ yes | Post-test survey |
| NPS (Net Promoter Score) | 30+ | "How likely are you to recommend Kestrel?" (0-10) |
| Time in Demo Mode before upgrading | Under 1 session | Track how quickly users connect a real AI provider |

---

## 9. The "Lost User" Safety Net

### In-App "I'm Stuck" System

Add a persistent help icon (question mark) in the bottom-right corner of every page. Clicking it shows:

**Quick Help Panel:**

1. **Kestrel isn't loading**
   - "Make sure your Docker runtime is running (look for the OrbStack icon or Docker whale in your menu bar)"
   - "Open Terminal and type: `docker compose up -d`"
   - "Then reload this page"

2. **I don't understand the scores**
   - Link to score explanation page
   - "Scores are based on how well this job matches your profile. Higher is better. 8+ is a strong match."

3. **I want real AI, not Demo Mode**
   - "Go to Settings > AI Provider"
   - Link to API key setup guide

4. **Something else is wrong**
   - "Describe your problem to ChatGPT or Claude with this prompt:" (see below)
   - "Ask the community:" link to Discord/Discussions

### AI-Assisted Troubleshooting Prompts

Give users pre-written prompts they can paste into ChatGPT or Claude:

**Setup issues:**
```
I'm trying to install an app called Kestrel (a job search tool) on my Mac.
I followed the instructions but I'm getting this error:

[PASTE ERROR HERE]

The setup instructions say to run these commands in Terminal:
cd ~/Downloads/kestrel-main
bash setup.sh

I'm not a developer. Can you help me fix this in simple terms?
```

**Usage questions:**
```
I'm using a job search app called Kestrel. It runs locally on my Mac
using Docker. I have a question about how to use it:

[DESCRIBE YOUR QUESTION]

The app has a Kanban board for tracking applications, AI scoring for
jobs, and auto-discovery from job boards. Can you help?
```

### Troubleshooting Decision Tree

```
Kestrel won't start
|
+-- Did setup.sh complete successfully?
|   |
|   +-- YES --> Is your Docker runtime running? (OrbStack or Docker Desktop icon in menu bar)
|   |           |
|   |           +-- YES --> Open Terminal, type: docker compose up -d
|   |           |           Then try http://localhost:8101 again
|   |           |
|   |           +-- NO --> Open OrbStack or Docker Desktop, wait 30 seconds, try again
|   |
|   +-- NO --> What error did you see?
|       |
|       +-- "Docker not found" --> Install OrbStack from orbstack.dev (or Docker Desktop from docker.com)
|       +-- "Docker not running" --> Open OrbStack or Docker Desktop, wait, retry
|       +-- "Permission denied" --> Use: bash setup.sh (instead of ./setup.sh)
|       +-- "No such file" --> You're in the wrong folder. Use: cd ~/Downloads/kestrel-main
|       +-- Something else --> Copy the error, paste it into ChatGPT with the prompt above
|
Kestrel is running but something looks wrong
|
+-- Blank page at localhost:8101
|   --> Wait 30 seconds and refresh. Backend might still be starting.
|
+-- Scores all look the same
|   --> You're in Demo Mode. Set up a real AI provider in Settings.
|
+-- "Connection refused" error
|   --> Kestrel probably isn't running. Open Terminal, type: docker compose up -d
|
+-- Can't find jobs in discovery
|   --> Check your search profile settings. Try broader terms (e.g., "Marketing" not "Marketing Operations Specialist II")
```

### Community Safety Net

- **GitHub Discussions:** Enable Discussions on the repo with a "Q&A" category specifically for setup help.
- **Discord server:** Create a #setup-help channel where users can post screenshots of their errors.
- **Issue templates:** Add a "I'm stuck during setup" issue template that pre-fills with diagnostic questions (OS, Docker version, error message).

### The Nuclear Option: "Just Show Me"

For users who truly cannot get through setup, provide escape hatches:

1. **GitHub Codespaces** - "Click this button to run Kestrel in your browser without installing anything." (Requires a GitHub account but zero local setup.)
2. **Video walkthrough** - "Watch someone else do it, then follow along." A 5-minute real-time screen recording of the entire setup.
3. **Ask a friend** - Honestly, sometimes the best UX is: "Know someone technical? Send them this link and ask them to set it up for you. It takes 5 minutes for someone who knows Docker."

---

## Summary of Priorities

| Priority | What | Impact |
|:---------|:-----|:-------|
| **P0** | Rewrite README Quick Start with non-technical path | Prevents the #1 drop-off |
| **P0** | Add welcome/onboarding wizard in the UI | Converts setup success into active usage |
| **P0** | In-app API key configuration | Eliminates the .env editing wall |
| **P1** | Port conflict detection in setup.sh | Prevents silent failures |
| **P1** | Rename "mock" to "Demo Mode" everywhere | Reduces confusion and distrust |
| **P1** | GitHub Codespaces support | Zero-install path for the truly stuck |
| **P1** | Empty state guidance on Kanban board | Bridges the "now what?" gap |
| **P1** | QUICKSTART.md with screenshots | Visual learners, non-English speakers |
| **P2** | Hero screenshot in README | Shows the destination, builds motivation |
| **P2** | Video walkthrough | Most accessible format for non-technical users |
| **P2** | Cloud-hosted demo | Try before you install |
| **P2** | Score explanation tooltips | Builds trust in the AI scoring |
| **P3** | Auto-open browser after setup | Small convenience, nice polish |
| **P3** | Periodic build status messages | Reduces anxiety during Docker build |

---

*This document should be revisited after each round of user testing. Every FAQ entry that gets asked twice should trigger a product change so it never needs to be asked again.*
