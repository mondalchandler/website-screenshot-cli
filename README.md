# Website Screenshot CLI — Beginner‑Friendly Guide

This tool captures **full‑page desktop and mobile screenshots** of one or many web pages and merges them into a single, timestamped PDF. It also handles common website quirks like sticky headers, cookie banners, animations, and “Important Safety Information (ISI)” blocks.

---

## What you’ll get
- A **PDF** named like `screenshots_YYYYMMDD-HHMMSS.pdf` in your chosen output folder.
- Individual images saved to two subfolders:
  - `output/desktop/…_dt.png`
  - `output/mobile/…_mb.png`
- A **progress meter** with an estimated time remaining (ETA).
- Automatic **cleanup** of old PNGs in `desktop/` and `mobile/` at the start of each run.
- Automatic **deduped filenames** (e.g., `parent-slug-child-slug` or `slug-2`, `slug-3`, …).

---

## Two ways to get the project

### Option A — Download the ZIP (no Git needed)
1. Get the ZIP from your team (or GitHub’s “Download ZIP”).  
2. Unzip it somewhere easy, like your Desktop. You should now have a folder such as `website-screenshot-cli/`.

### Option B — Use Git (recommended for updates)
> If you don’t have Git yet, install it in a few minutes and you’ll be able to update with a single command.

**Install Git**
- **macOS (with Homebrew):**
  ```bash
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  brew install git
  ```
  (If you don’t want Homebrew, you can also install Git via Xcode Command Line Tools: `xcode-select --install`.)

- **Windows:**
  1. Download the Git for Windows installer from https://git-scm.com/download/win
  2. Run it and keep the defaults. After install, re-open PowerShell or Command Prompt.

**Verify Git is installed**
```bash
git --version
```
You should see something like `git version 2.xx.x`.

**Clone the repository**
```bash
git clone https://github.com/mondalchandler/website-screenshot-cli.git
cd website-screenshot-cli
```

**Pull the latest updates (later on)**
```bash
cd website-screenshot-cli
git pull
```

---

## Requirements (once per computer)

1. **Python 3.10+** (3.11 or 3.12 recommended)
   - **macOS** (with Homebrew):
     ```bash
     brew install python
     ```
   - **Windows**: Download “Python (64‑bit)” from https://www.python.org/downloads/ and install. During install, **check “Add Python to PATH.”**

2. **Project files** (from the ZIP **or** `git clone` in the steps above)

3. **Playwright browsers** (automatic web driver)  
   We’ll install this right after the Python dependencies (see Quick Start).

> If your company uses a proxy or secure network, you may need to connect to VPN first.

---

## Quick Start (copy/paste)
Open **Terminal (macOS)** or **Command Prompt / PowerShell (Windows)** and run these inside the project folder:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Now you’re ready to run the tool.

---

## How to run

### A) One URL
```bash
python -m app.main "https://www.example.com" --defloat --isi-reached \
  --hide-selectors "#onetrust-banner-sdk,.otFlat,.ot-sdk-row,.ot-sdk-container,.onetrust-close-btn-handler,.ot-pc-refuse-all-handler"
```
**What this does**
- `--defloat` : Converts sticky/fixed elements so they don’t overlap in the screenshot.
- `--isi-reached` : Marks ISI sections as “reached” so they don’t float at the top before you scroll to them.
- `--hide-selectors` : Hides cookie banners and similar overlays (OneTrust example selectors shown).

### B) A list of URLs from a text file
Put your links into `urls.txt`. Lines can be separated by **new lines**, **tabs**, **commas**, or **spaces**. Comments starting with `#` are ignored.

```bash
python -m app.main --url-list urls.txt --defloat --isi-reached \
  --hide-selectors "#onetrust-banner-sdk,.otFlat,.ot-sdk-row,.ot-sdk-container,.onetrust-close-btn-handler,.ot-pc-refuse-all-handler"
```

### C) A sitemap XML file
If you have `sitemap.xml` in the project folder:
```bash
python -m app.main --sitemap-file sitemap.xml --defloat --isi-reached \
  --hide-selectors "#onetrust-banner-sdk,.otFlat,.ot-sdk-row,.ot-sdk-container,.onetrust-close-btn-handler,.ot-pc-refuse-all-handler"
```

### Optional flags you might need
- `-o out` — choose a custom output folder (default is `./output`).
- `--insecure` — ignore HTTPS certificate errors (useful for staging/dev hosts).
- `--timeout-ms 90000` — increase navigation timeout for slow pages.
- `--include-nonhtml` — **don’t** skip PDFs/images in sitemap/list (off by default).
- `--no-settle` — **disable** animation-settling and “mark all viewed” logic (not recommended).

---

## What the app does for you (automatically)
- **Finishes animations**: it scrolls down the page and forces elements into their final “visible” state before capturing.
- **ISI behavior**: adds the `reached` class to ISI sections so they render where they belong—**not** pinned at the top.
- **Deflating sticky elements**: turns `position:fixed/sticky` into a safe layout so they don’t overlap content in full‑page captures.
- **Cookie banners**: when you pass `--hide-selectors`, the app hides the elements **and** clears leftover body offsets many banners add.
- **Duplicate names**: when two pages share the same last URL segment (e.g., “thank-you-page”), the app tries `parent-child` first, then `slug-2`, `slug-3`, etc.
- **Progress + ETA**: prints a friendly counter with estimated time remaining.
- **Cleans old PNGs**: removes any `*.png` from `output/desktop` and `output/mobile` at the start of each run.
- **PDF output name**: always `screenshots_YYYYMMDD-HHMMSS.pdf` in the output folder.

---

## Output structure
```
output/
  desktop/
    home_dt.png
    living-with-schizophrenia_dt.png
    ...
  mobile/
    home_mb.png
    living-with-schizophrenia_mb.png
    ...
  screenshots_20250101-104500.pdf
```

**Ordering in the PDF** matches your input order, alternating desktop → mobile per page:
```
page1_dt, page1_mb, page2_dt, page2_mb, ...
```

---

## Practical examples

**List of URLs with staging certs + longer timeout:**
```bash
python -m app.main --url-list urls.txt -o shots --insecure --timeout-ms 120000 \
  --defloat --isi-reached \
  --hide-selectors "#onetrust-banner-sdk,.otFlat,.ot-sdk-row,.ot-sdk-container,.onetrust-close-btn-handler,.ot-pc-refuse-all-handler"
```

**Sitemap excluding PDFs/images (default behavior):**
```bash
python -m app.main --sitemap-file sitemap.xml --defloat --isi-reached \
  --hide-selectors "#onetrust-banner-sdk,.otFlat,.ot-sdk-row,.ot-sdk-container,.onetrust-close-btn-handler,.ot-pc-refuse-all-handler"
```

**Single page quick test:**
```bash
python -m app.main "https://www.uzedy.com/living-with-schizophrenia" --defloat --isi-reached \
  --hide-selectors "#onetrust-banner-sdk,.otFlat,.ot-sdk-row,.ot-sdk-container,.onetrust-close-btn-handler,.ot-pc-refuse-all-handler"
```

---

## Updating (when you receive a new version)
If you cloned via Git:
```bash
git pull
python -m pip install -r requirements.txt
python -m playwright install chromium
```

If you downloaded a ZIP: replace the folder with the new one, then run:
```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
```

---

## Troubleshooting

**❌ “net::ERR_CERT_AUTHORITY_INVALID”**  
Use `--insecure` for staging/dev sites with custom or invalid certificates.

**❌ Playwright complains about missing browsers**  
Run: `python -m playwright install chromium`

**❌ Command not found / permissions (macOS)**  
Use the `python -m` form exactly as shown. If downloads are blocked, connect to VPN first.

**❌ Screenshots look “shifted” after hiding a cookie banner**  
Make sure you included `--hide-selectors` with the OneTrust selectors shown above. The app also clears banner‑added top offsets automatically.

**❌ Very slow pages**  
Bump timeout: `--timeout-ms 120000` or `180000`. Close unused apps or browser tabs.

---

## Cleaning up (optional)
To remove the virtual environment and cached files:
```bash
deactivate 2>/dev/null || true
rm -rf .venv
rm -rf output
```

---

## Contributing (Git users)
1. Create a new branch: `git checkout -b feature/my-change`
2. Commit small, focused changes: `git commit -m "feat: add popup-only capture"`
3. Push and open a PR: `git push origin feature/my-change`
4. Ask a teammate to review.

---

## Need help?
Share:
- Your exact command
- A sample URL
- The Terminal output/error

That info helps the team reproduce and fix quickly.
