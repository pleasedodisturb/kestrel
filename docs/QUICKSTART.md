# Getting Started with Kestrel

This guide assumes you have never used a terminal before. Every step is explained. If you get stuck, check the [Common Problems](#common-problems) section at the bottom or the [FAQ](FAQ.md).

---

## What you need

- A computer (Mac or Windows)
- About 15 minutes for first-time setup
- 2 GB of free disk space
- An internet connection (for the initial download)
- **Docker Desktop** - a free app that runs Kestrel on your computer. Think of Docker as a box that keeps everything Kestrel needs bundled together, so you don't have to install a dozen separate things. You install Docker once, and it handles the rest.

That's it. You don't need to know how to code.

---

## Step 1: Install Docker Desktop

Docker Desktop is free for personal use. Download it, install it like any other app.

**Mac (Apple Silicon - M1, M2, M3, M4):**
https://desktop.docker.com/mac/main/arm64/Docker.dmg

**Mac (Intel):**
https://desktop.docker.com/mac/main/amd64/Docker.dmg

Not sure which Mac you have? Click the Apple menu in the top-left corner of your screen, then "About This Mac." If it says "Apple M1" or "Apple M2" (or M3, M4), use the Apple Silicon link. If it says "Intel," use the Intel link.

**Windows:**
https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe

### After downloading

- **Mac:** Open the .dmg file. Drag Docker to your Applications folder. Open Docker Desktop from Applications. If macOS says it can't open it because it's from an unidentified developer, go to System Settings > Privacy & Security and click "Open Anyway."
- **Windows:** Run the installer. Follow the prompts. It may ask you to enable WSL2 - say yes. Restart your computer if it asks.

Docker will take a minute or two to start up the first time. You'll see a whale icon in your menu bar (Mac) or system tray (Windows). Wait for it to stop animating - that means it's ready.

**Skip the account creation if Docker asks you to sign in. You don't need an account.**

Keep Docker Desktop running in the background while using Kestrel. It's the engine that powers everything.

---

## Step 2: Download Kestrel

Pick whichever option feels more comfortable.

### Option A: Download as ZIP (recommended if you've never used a terminal)

1. Go to https://github.com/pleasedodisturb/kestrel
2. Click the green **Code** button near the top of the page
3. Click **Download ZIP**
4. Find the downloaded file (probably in your Downloads folder) and double-click it to unzip
5. You now have a folder called `kestrel-main`

### Option B: Use the command line (if you know what Terminal is)

```
git clone https://github.com/pleasedodisturb/kestrel.git
```

This creates a folder called `kestrel` wherever you ran the command.

---

## Step 3: Open Terminal (Mac) or PowerShell (Windows)

This is where you'll type the setup command. You only need to do this once.

**Mac:**
Press **Cmd + Space** to open Spotlight search. Type **Terminal** and press Enter. A window with a text cursor will open. That's Terminal.

**Windows:**
Click the Start menu. Type **PowerShell** and open it. A blue window with a text cursor will open.

Don't worry about all the text already in the window. You'll just type one or two things and be done.

---

## Step 4: Navigate to the Kestrel folder

The terminal doesn't know where your Kestrel files are. You need to tell it by using the `cd` command, which stands for "change directory" (directory = folder).

**If you downloaded the ZIP (Option A):**

The folder is probably in your Downloads. Type this and press Enter:

Mac:
```
cd ~/Downloads/kestrel-main
```

Windows:
```
cd $HOME\Downloads\kestrel-main
```

**If you used git clone (Option B):**

The folder is wherever you ran the command. If you ran it without changing directories first, it's in your home folder:

Mac:
```
cd ~/kestrel
```

Windows:
```
cd $HOME\kestrel
```

### How to check you're in the right place

Type `ls` (Mac) or `dir` (Windows) and press Enter. You should see a list of files including `setup.sh`, `docker-compose.yml`, and a `src/` folder. If you don't see those, you're in the wrong folder.

**Common locations to try:**
- `~/Downloads/kestrel-main` (ZIP download on Mac)
- `~/Documents/kestrel-main` (if you moved it)
- `~/kestrel` (git clone on Mac)
- `$HOME\Downloads\kestrel-main` (ZIP download on Windows)

---

## Step 5: Run the setup

Type this and press Enter:

```
bash setup.sh
```

(Why `bash setup.sh` instead of `./setup.sh`? The `bash` version is more reliable, especially if this is your first time using a terminal. It avoids a common "permission denied" error.)

### What to expect

- The setup takes about 2-3 minutes. On a slower internet connection, it could take up to 5. This is normal.
- You'll see text scrolling by. Some of it looks technical and weird. That's fine. It's downloading and setting up everything Kestrel needs.
- You'll see `[ok]` messages as each step completes. These are good.
- **Do not close the terminal window while this is running.**

### What success looks like

When it's done, you'll see something like:

```
Kestrel is running!

Dashboard:  http://localhost:8101
API docs:   http://localhost:8100/docs
```

That means it worked.

---

## Step 6: Open Kestrel

Open your browser (Chrome, Firefox, Safari, Edge - any of them work) and go to:

**http://localhost:8101**

Make sure you include the `http://` part. If you just type `localhost:8101`, some browsers will search Google for it instead of opening it.

You should see the Kestrel dashboard - a real web app running on your computer. There's a pipeline board, settings, and more.

**You won't need to type anything else in the terminal after this. Everything from here is in your browser.**

---

## What to do next

1. **Set up your profile** - Go to Settings and add your name, target roles, preferred locations, and salary range. This is what Kestrel uses to score jobs for you.
2. **Explore the pipeline** - The Kanban board is where you'll track applications. It starts empty.
3. **Try discovery** - Search for jobs across multiple boards at once. Kestrel will score them against your profile.

Kestrel starts in **Demo Mode**, which means AI features show example data so you can explore everything without needing an API key. When you're ready for real, personalized AI scoring, see the FAQ on [how to add a real AI provider](FAQ.md#how-do-i-add-a-real-ai-provider).

---

## Common Problems

### "Docker not found" or Docker errors

**What you see:** An error mentioning Docker is not installed or not running.

**What to do:** Make sure Docker Desktop is installed (Step 1) and actually open. Look for the whale icon in your menu bar (Mac) or system tray (Windows). If the whale is still animating, Docker is still starting up - wait for it to finish.

### "Permission denied"

**What you see:** `permission denied: ./setup.sh` or similar.

**What to do:** Use `bash setup.sh` instead of `./setup.sh`. This is the most common first-timer issue and the fix is that simple.

### "No such file or directory"

**What you see:** `No such file or directory: setup.sh` or `can't open setup.sh`.

**What to do:** You're not in the right folder. Type `ls` (Mac) or `dir` (Windows) and press Enter. If you don't see `setup.sh` in the list, you need to navigate to the Kestrel folder first. Go back to Step 4.

### Port already in use

**What you see:** An error about port 8100 or 8101 being in use.

**What to do:** Something else on your computer is using the same port. The quickest fix: close other development tools or servers you might have running. If you're not sure what's using the port, restart your computer and try again.

### Blank page when I open localhost:8101

**What you see:** A white page or "connection refused" in your browser.

**What to do:** Kestrel might still be starting up. Wait 30 seconds and refresh the page. If it still doesn't load:

1. Go back to your terminal and check if there are any error messages
2. Try running `docker compose ps` - you should see containers listed as "running"
3. If containers aren't running, try `docker compose up -d` and wait a minute

### Hidden files on Mac

Files starting with a dot (like `.env`) are hidden on Mac by default. They're there, you just can't see them in Finder. If you need to see them, press **Cmd + Shift + .** (period) in Finder to toggle hidden files.

### "git clone" doesn't work / I don't have git

Skip git entirely. Use the ZIP download method in Step 2, Option A. It does the same thing.

### If something goes wrong during setup

Don't panic. Your computer is fine. Kestrel runs inside Docker, which is a sandbox - it can't break anything on your system. If the setup failed partway through, you can safely run `bash setup.sh` again. It will pick up where it left off or start fresh.

---

## How to Start and Stop Kestrel

After the initial setup, you don't need to run `setup.sh` again. Here's how to manage Kestrel going forward.

### Start Kestrel

Open Terminal (or PowerShell), navigate to your Kestrel folder, and type:

```
docker compose up -d
```

Then open http://localhost:8101 in your browser.

### Stop Kestrel

```
docker compose down
```

### Your data persists

Stopping Kestrel does not delete anything. Your profile, applications, scores - all of it is saved in a database file on your computer. When you start Kestrel again, everything is exactly where you left it.

You can also close the terminal window after running `docker compose up -d`. Kestrel keeps running in the background. It only stops when you explicitly run `docker compose down` or when you quit Docker Desktop.
