# Website Screenshot CLI — Beginner-Friendly Guide

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

## Requirements (once per computer)
1. **Python 3.10+** (3.11 or 3.12 recommended)
   - **macOS**: Install Homebrew (if you don’t have it), then:
     ```bash
     /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
     brew install python
     ```
   - **Windows**: Download “Python (64‑bit)” from https://www.python.org/downloads/ and install. During install, **check “Add Python to PATH.”**

2. **Project files** (from your team ZIP or repo)
   - You should have a folder like `website-screenshot-cli` that contains an `app/` folder with `main.py`, `requirements.txt`, etc.

3. **Playwright browsers** (automatic web driver)
   - We’ll install this right after the Python dependencies (see Quick Start).

> If your company uses a proxy or secure network, you may need to connect to VPN first.

---

## Quick Start (copy/paste)
Open **Terminal (macOS)** or **Command Prompt / PowerShell (Windows)** and run these inside the project folder:

```bash
# 1) (Optional but recommended) Create and activate a virtual environment
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows (PowerShell):
# .venv\Scripts\Activate.ps1

# 2) Install dependencies
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

# 3) Install a Playwright browser (Chromium)
python -m playwright install chromium
```

Now you’re ready to run the tool.

---

## How to run

### A) One URL
```bash
python -m app.main "https://www.example.com" --defloat --isi-reached   --hide-selectors "#onetrust-banner-sdk,.otFlat,.ot-sdk-row,.ot-sdk-container,.onetrust-close-btn-handler,.ot-pc-refuse-all-handler"
```
**What this does**
- `--defloat` : Converts sticky/fixed elements so they don’t overlap in the screenshot.
- `--isi-reached` : Marks ISI sections as “reached” so they don’t float at the top before you scroll to them.
- `--hide-selectors` : Hides cookie banners and similar overlays (OneTrust example selectors shown).

### B) A list of URLs from a text file
Put your links into `urls.txt`. Lines can be separated by **new lines**, **tabs**, **commas**, or **spaces**. Comments starting with `#` are ignored.

```bash
python -m app.main --url-list urls.txt --defloat --isi-reached   --hide-selectors "#onetrust-banner-sdk,.otFlat,.ot-sdk-row,.ot-sdk-container,.onetrust-close-btn-handler,.ot-pc-refuse-all-handler"
```

### C) A sitemap XML file
If you have `sitemap.xml` in the project folder:
```bash
python -m app.main --sitemap-file sitemap.xml --defloat --isi-reached   --hide-selectors "#onetrust-banner-sdk,.otFlat,.ot-sdk-row,.ot-sdk-container,.onetrust-close-btn-handler,.ot-pc-refuse-all-handler"
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
- **ISI behavior**: adding the `reached` class to ISI sections so they render where they belong—**not** pinned at the top.
- **Deflating sticky elements**: turns `position:fixed/sticky` into a safe layout so they don’t overlap content in full‑page captures.
- **Cookie banners**: if you pass `--hide-selectors`, it hides the elements and also **clears leftover body offsets** many banners add.
- **Duplicate names**: when two pages share the same last URL segment (e.g., “thank-you-page”), we try `parent-child` first, then `slug-2`, `slug-3`, etc.
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
python -m app.main --url-list urls.txt -o shots --insecure --timeout-ms 120000   --defloat --isi-reached   --hide-selectors "#onetrust-banner-sdk,.otFlat,.ot-sdk-row,.ot-sdk-container,.onetrust-close-btn-handler,.ot-pc-refuse-all-handler"
```

**Sitemap excluding PDFs/images (default behavior):**
```bash
python -m app.main --sitemap-file sitemap.xml --defloat --isi-reached   --hide-selectors "#onetrust-banner-sdk,.otFlat,.ot-sdk-row,.ot-sdk-container,.onetrust-close-btn-handler,.ot-pc-refuse-all-handler"
```

**Single page quick test:**
```bash
python -m app.main "https://www.uzedy.com/living-with-schizophrenia" --defloat --isi-reached   --hide-selectors "#onetrust-banner-sdk,.otFlat,.ot-sdk-row,.ot-sdk-container,.onetrust-close-btn-handler,.ot-pc-refuse-all-handler"
```

---

## Tips
- If a popup appears on first load, use `--hide-selectors` for its closeable container if you want only the underlying page. (If your team later adds dedicated “popup‑only” capture logic, the README can be updated.)
- For **very long** or **heavy** pages, increase `--timeout-ms` and try again.
- If animations still appear mid‑transition, remove `--no-settle` (or don’t use it). The default behavior already tries to finish animations for you.

---

## Troubleshooting

**❌ “net::ERR_CERT_AUTHORITY_INVALID”**
- Use `--insecure` for staging/dev sites with custom or invalid certificates.

**❌ Playwright complains about missing browsers**
- Run: `python -m playwright install chromium`

**❌ Command not found / permissions (macOS)**
- Prefix with `python -m` exactly as shown.
- If your company blocks downloads, connect to VPN before installing.

**❌ Screenshots look “shifted” after hiding a cookie banner**
- Make sure you included `--hide-selectors` with the OneTrust selectors shown above. The tool also clears banner‑added top offsets automatically.

**❌ Very slow pages**
- Bump timeout: `--timeout-ms 120000` or `180000`.
- Close unused apps or browser tabs.

---

## Updating the tool
When your teammates receive an updated ZIP or repo, do this inside the project folder:
```bash
# If using a venv, activate it first (see Quick Start)
python -m pip install -r requirements.txt
python -m playwright install chromium
```

---

## Cleaning up (optional)
To remove the virtual environment and cached files:
```bash
deactivate 2>/dev/null || true
rm -rf .venv
rm -rf output
```

---

## Need help?
Share:
- Your exact command
- A sample URL
- The Terminal output/error
This helps the team reproduce and fix quickly.

## Installing Homebrew (macOS)

> **Note:** Homebrew is optional for this project. You can install Python directly from python.org and skip Brew. These steps are provided in case you prefer managing tools with Homebrew.

### 1) Install Apple Command Line Tools (recommended)
This ensures `git`, compilers, and headers are available.
```bash
xcode-select --install
```

### 2) Install Homebrew
Paste the official installer command into Terminal (no smart quotes, no extra characters):
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 3) Add Homebrew to your PATH
- Apple Silicon (M1/M2/M3):
  ```bash
  echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
  eval "$(/opt/homebrew/bin/brew shellenv)"
  ```
- Intel mac:
  ```bash
  echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zprofile
  eval "$(/usr/local/bin/brew shellenv)"
  ```

Verify:
```bash
brew --version
brew doctor
```

### Troubleshooting SSL errors during install (corporate networks)
If you see `curl: (60) SSL certificate problem: unable to get local issuer certificate` when running the installer, your network may be intercepting TLS.

Try these, in order:

1. **Simple checks**
   - Make sure your Mac’s date/time are correct.
   - Disconnect from VPN or try a different network (hotspot) to confirm it’s a network policy issue.

2. **Use macOS system trust store for curl**
   ```bash
   /usr/bin/security find-certificate -a -p /System/Library/Keychains/SystemRootCertificates.keychain > ~/cacert.pem
   export SSL_CERT_FILE=~/cacert.pem
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

3. **If your company provides a corporate root certificate (preferred)**
   - Import it into Keychain Access and set to **Always Trust**.
   - Export the certificate to a file (e.g., `~/corp_root_ca.pem`), then:
     ```bash
     export SSL_CERT_FILE=~/corp_root_ca.pem
     /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
     ```

If none of the above helps, install Homebrew from a home/hotspot network once. It will continue to work on the corporate network afterward.

### Linux
Homebrew also supports Linux (“Linuxbrew”). See the official docs:
https://docs.brew.sh/Homebrew-on-Linux
