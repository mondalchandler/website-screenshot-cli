#!/usr/bin/env python3
"""
website-screenshot-cli (desktop/mobile subfolders, modal-aware)

- Saves desktop PNGs to <out>/desktop/
- Saves mobile  PNGs to <out>/mobile/
- Merges in-order to a single PDF in the <out> root
- Supports single URL, --sitemap-file, and --url-list
- Animation settling, defloat, hide selectors, ISI reached
- Progress with ETA, timestamped PDF name: screenshots_YYYYMMDD-HHMMSS.pdf
- Clears old PNGs before each run
- Unique slug generation with parent-page fallback for duplicates
- Detects first-load modals: captures a tight popup image, closes it, then full-page
"""

import argparse
import re
import time
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path
from typing import List, Optional, Set
from xml.etree import ElementTree as ET

from PIL import Image
from playwright.sync_api import sync_playwright, Error as PWError

# ---------- time & cleanup ----------

def run_timestamp() -> str:
    # e.g., 2025-10-06 14:23:05 -> "20251006-142305"
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def clear_previous_pngs(out_dir: Path):
    """Remove all PNG screenshots in desktop/ and mobile/ before a new run."""
    for sub in ("desktop", "mobile"):
        d = out_dir / sub
        if d.exists():
            for p in d.glob("*.png"):
                try:
                    p.unlink()
                except Exception:
                    pass
        else:
            d.mkdir(parents=True, exist_ok=True)

# ---------- utility formatting ----------

def _fmt_eta(seconds: Optional[float]) -> str:
    if seconds is None or seconds != seconds or seconds < 0:
        return "estimating…"
    seconds = int(round(seconds))
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    if h > 0:
        return f"{h:d}h {m:02d}m {s:02d}s"
    return f"{m:d}m {s:02d}s"

# ---------- helpers ----------

def clean_hostname(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    host = re.sub(r"^www\.", "", host)
    host = re.sub(r"[^a-z0-9\.\-_]+", "_", host)
    return host or "site"

def ensure_scheme(url: str) -> str:
    if not re.match(r"^https?://", url, flags=re.I):
        return "https://" + url
    return url

def take_fullpage_screenshot(page, path: str):
    page.screenshot(path=path, full_page=True)

# ---------- JS helpers ----------

def js_clear_banner_offsets():
    return r"""
(() => {
  // Zero out offsets OneTrust often leaves behind
  const zero = (el) => {
    if (!el) return;
    el.style.top = '0px';
    el.style.marginTop = '0px';
    el.style.paddingTop = (el.style.paddingTop && el.style.paddingTop !== '0px') ? '0px' : el.style.paddingTop;
    if (el.style.position === 'relative') el.style.position = '';
  };
  zero(document.body);
  zero(document.documentElement);

  // Remove OT classes that can re-apply spacing
  const rm = (el, ...cls) => { if (el) el.classList.remove(...cls); };
  rm(document.documentElement, 'ot-shown','ot-bnr-shown','ot-sdk-show-settings');
  rm(document.body,           'ot-shown','ot-bnr-shown','ot-sdk-show-settings');

  // Any OT elements that might have inline top/margin pushing content?
  document.querySelectorAll('[id*="onetrust"],[class*="onetrust"],[class*="ot-"]').forEach(el => {
    el.style.top = '0px';
    el.style.marginTop = '0px';
  });

  // Common CSS var used by OT for banner height
  document.documentElement.style.setProperty('--ot-banner-height','0px','important');
  document.documentElement.style.setProperty('--ot-sdk-cookie-banner-height','0px','important');
})();
"""

def js_defloat_script():
    return r"""
(() => {
  const seen = new WeakSet();
  const makeAbsolute = (el) => {
    if (seen.has(el)) return;
    seen.add(el);
    const cs = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    el.setAttribute('data-defloated', '1');
    el.style.position = 'absolute';
    el.style.top = (rect.top + window.scrollY) + 'px';
    el.style.left = (rect.left + window.scrollX) + 'px';
    el.style.right = 'auto';
    el.style.bottom = 'auto';
    if (cs.width && cs.width.endsWith('px')) {
      el.style.width = cs.width;
    }
    if (!el.style.zIndex) {
      el.style.zIndex = String(parseInt(cs.zIndex || '1000', 10) || 1000);
    }
  };

  document.querySelectorAll('*').forEach((el) => {
    const cs = getComputedStyle(el);
    if (cs.position === 'fixed') makeAbsolute(el);
    if (cs.position === 'sticky') {
      el.setAttribute('data-desticky', '1');
      el.style.position = 'static';
      el.style.top = 'auto';
    }
  });
})();
"""

def js_hide_selectors(selectors: str):
    return f"""
(() => {{
  const sels = {selectors!r}.split(',').map(s=>s.trim()).filter(Boolean);
  for (const s of sels) {{
    try {{
      document.querySelectorAll(s).forEach(el => {{
        el.setAttribute('data-hidden-by-cli', '1');
        el.style.display = 'none';
      }});
    }} catch (e) {{/* ignore */}}
  }}
}})();
"""

def js_mark_isi_reached():
    return r"""
(() => {
  document.querySelectorAll('section.isi.js-isi').forEach(el => el.classList.add('reached'));
})();
"""

def js_mark_all_viewed_and_freeze():
    return r"""
(() => {
  const addClasses = (sel, cls) => {
    document.querySelectorAll(sel).forEach(el => el.classList.add(...cls));
  };
  addClasses('.js-lte-text', ['reached', 'entered', 'in-view', 'is-visible']);
  addClasses('.lte.js-lte', ['reached', 'entered', 'in-view', 'is-visible']);
  addClasses('[class*="aos"]', ['aos-animate']);
  addClasses('.reveal,.animate,.animated,.in-view,.is-visible', ['in-view', 'is-visible']);

  document.querySelectorAll('.lazy, [data-ll-status]').forEach(el => {
    el.classList.add('entered', 'loaded', 'reached');
    if (el.dataset && el.dataset.src && !el.getAttribute('src')) el.setAttribute('src', el.dataset.src);
    if (el.dataset && el.dataset.srcset && !el.getAttribute('srcset')) el.setAttribute('srcset', el.dataset.srcset);
  });

  const st = document.createElement('style');
  st.type = 'text/css';
  st.textContent = `
    * , *::before, *::after { animation: none !important; transition: none !important; }
    .aos-init, .aos-animate, .in-view, .is-visible, .entered, .reached {
      opacity: 1 !important; transform: none !important; filter: none !important;
    }
  `;
  document.head.appendChild(st);
})();
"""

# --- Modal detection / capture / close ---

def js_find_any_modal_script():
    # Returns true if a likely modal is visible in the page
    return r"""
(() => {
  const selectors = [
    'section.modal.open-modal',
    'section.modal.open',
    '.modal.open-modal',
    '.modal.is-open',
    '.modal[open]',
    '[role="dialog"][aria-modal="true"]',
    '.ReactModal__Content--after-open',
    '.c-modal.is-active',
    '.lightbox.open',
    '.overlay[aria-modal="true"]'
  ];
  const isVisible = (el) => {
    if (!el) return false;
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || +style.opacity === 0) return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 50 && rect.height > 50;
  };
  for (const s of selectors) {
    const el = document.querySelector(s);
    if (el && isVisible(el)) return true;
  }
  return false;
})();
"""

def js_modal_bbox_script():
    # Returns {x,y,width,height} for the largest visible modal-ish element
    return r"""
(() => {
  const candidates = Array.from(document.querySelectorAll([
    'section.modal.open-modal',
    'section.modal.open',
    '.modal.open-modal',
    '.modal.is-open',
    '.modal[open]',
    '[role="dialog"][aria-modal="true"]',
    '.ReactModal__Content--after-open',
    '.c-modal.is-active',
    '.lightbox.open',
    '.overlay[aria-modal="true"]'
  ].join(','))).filter(el => {
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return cs.display !== 'none' && cs.visibility !== 'hidden' && +cs.opacity !== 0 && r.width > 50 && r.height > 50;
  });

  if (!candidates.length) return null;

  let best = candidates[0], bestA = 0;
  for (const el of candidates) {
    const r = el.getBoundingClientRect();
    const a = r.width * r.height;
    if (a > bestA) { best = el; bestA = a; }
  }
  const r = best.getBoundingClientRect();
  return { x: Math.max(0, r.x), y: Math.max(0, r.y), width: r.width, height: r.height };
})();
"""

def js_close_any_modal_script():
    # Attempts graceful close, then force-hide if needed
    return r"""
(() => {
  const clickSel = [
    '.js-modal-closer', '.modal__close', '.modal-close', '.c-modal__close',
    '[data-dismiss="modal"]', 'button[aria-label="Close"]', 'button[aria-label="close"]'
  ];
  for (const s of clickSel) {
    const btn = document.querySelector(s);
    if (btn && btn.offsetParent !== null) { btn.click(); return 'clicked'; }
  }
  // Escape key
  document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', keyCode:27, which:27, bubbles:true}));
  // Also strip common "open" classes as a fallback
  document.querySelectorAll('.modal, [role="dialog"]').forEach(el => {
    el.classList.remove('open-modal','open','is-open','is-active');
    el.removeAttribute('open');
  });
  // Hide obvious overlays
  document.querySelectorAll('.modal, .overlay, .lightbox, .ReactModal__Content--after-open')
    .forEach(el => { el.style.display = 'none'; });
  return 'forced';
})();
"""

# ---------- progressive scroll & prepare ----------

def progressive_scroll(page, step: int = 800, pause_ms: int = 150):
    y = 0
    while True:
        page.evaluate(f"() => window.scrollTo(0, {y});")
        page.wait_for_timeout(pause_ms)
        new_h = page.evaluate("() => document.body.scrollHeight")
        if y >= new_h:
            break
        y += step
    page.wait_for_timeout(200)

def nav_and_prepare(page, url, wait: str, insecure: bool, defloat: bool, hide_selectors: str,
                    isi_reached: bool, timeout_ms: int, settle: bool):
    page.set_default_timeout(timeout_ms)
    try:
        page.goto(url, wait_until=wait)
    except PWError:
        page.goto(url, wait_until="domcontentloaded")

    if settle:
        progressive_scroll(page)
    if isi_reached:
        page.evaluate(js_mark_isi_reached())
    if settle:
        page.evaluate(js_mark_all_viewed_and_freeze())
    if hide_selectors:
        page.evaluate(js_hide_selectors(hide_selectors))
        page.evaluate(js_clear_banner_offsets())
    if defloat:
        page.evaluate(js_defloat_script())
        page.evaluate(js_clear_banner_offsets())

# ---------- filtering & slug ----------

NON_HTML_EXTS = {
    ".pdf",".zip",".tar",".gz",".tgz",".bz2",".7z",".rar",
    ".doc",".docx",".ppt",".pptx",".xls",".xlsx",".csv",".tsv",
    ".mp4",".mp3",".webm",".mov",".avi",".mkv",
    ".jpg",".jpeg",".png",".gif",".svg",".ico",".webp",
    ".json",".xml",".rss",".atom",".txt",".md",".yaml",".yml"
}

def should_skip_url(u: str, include_nonhtml: bool) -> bool:
    if include_nonhtml:
        return False
    parsed = urlparse(u)
    if parsed.scheme not in ("http", "https"):
        return True
    path = parsed.path.lower()
    for ext in NON_HTML_EXTS:
        if path.endswith(ext):
            return True
    return False

def _slugify_segment(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\.(html?|aspx|php)$", "", s, flags=re.I)
    s = re.sub(r"[^a-z0-9\-_]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "page"

def unique_slug_for_url(u: str, used: Set[str]) -> str:
    """Return a unique slug for u, preferring <last>, then <parent>-<last>, else <last>-N."""
    p = urlparse(u)
    parts = [seg for seg in (p.path or "/").split("/") if seg]
    if not parts:
        base = "home"
        parent = ""
    else:
        base = _slugify_segment(parts[-1])
        parent = _slugify_segment(parts[-2]) if len(parts) >= 2 else ""

    if base and base not in used:
        used.add(base)
        return base

    if parent:
        cand = f"{parent}-{base}"
        if cand not in used:
            used.add(cand)
            return cand

    n = 2
    while True:
        cand = f"{base}-{n}"
        if cand not in used:
            used.add(cand)
            return cand
        n += 1

def slug_from_url(u: str) -> str:
    p = urlparse(u)
    path = p.path
    if not path or path == "/":
        slug = "home"
    else:
        parts = [seg for seg in path.split("/") if seg]
        slug = parts[-1] if parts else "home"
        slug = re.sub(r"\.(html?|aspx|php)$", "", slug, flags=re.I)
    slug = slug.strip().lower() or "page"
    slug = re.sub(r"[^a-z0-9\-_]+", "-", slug)
    return slug

# ---------- modal helpers ----------

def try_capture_modal_only(page, out_path: Path) -> Optional[Path]:
    """If a modal is present, screenshot just the modal area and return the path."""
    try:
        has_modal = page.evaluate(js_find_any_modal_script())
    except Exception:
        has_modal = False

    if not has_modal:
        return None

    bbox = page.evaluate(js_modal_bbox_script())
    if not bbox:
        return None

    page.evaluate("(y) => window.scrollTo(0, y)", max(0, int(bbox["y"] - 20)))
    page.wait_for_timeout(100)

    try:
        page.screenshot(
            path=str(out_path),
            full_page=False,
            clip={
                "x": float(bbox["x"]),
                "y": float(bbox["y"]),
                "width": float(bbox["width"]),
                "height": float(bbox["height"]),
            },
        )
        return out_path
    except Exception:
        return None

def close_any_modal(page):
    try:
        _ = page.evaluate(js_close_any_modal_script())
    except Exception:
        pass
    page.wait_for_timeout(200)

# ---------- core capture ----------

def capture_single_url(playwright, url: str, out_dir: Path, insecure: bool, nav_timeout_ms: int,
                       defloat: bool, hide_selectors: str, isi_reached: bool,
                       base_name: str, settle: bool, no_modal_shot: bool) -> List[Path]:
    """
    Returns a list of image paths in capture order, e.g.
    [popup_dt?, dt, popup_mb?, mb]
    """
    url = ensure_scheme(url)
    chromium = playwright.chromium
    browser = chromium.launch(headless=True, args=(["--ignore-certificate-errors"] if insecure else None))

    # Ensure subfolders
    desktop_dir = out_dir / "desktop"
    mobile_dir = out_dir / "mobile"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    mobile_dir.mkdir(parents=True, exist_ok=True)

    images: List[Path] = []

    # Desktop
    context = browser.new_context(
        viewport={"width": 1024, "height": 1080},
        device_scale_factor=2.0,
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari",
        ignore_https_errors=insecure,
    )
    page = context.new_page()
    nav_and_prepare(page, url, wait="load", insecure=insecure, defloat=defloat,
                    hide_selectors=hide_selectors, isi_reached=isi_reached, timeout_ms=nav_timeout_ms,
                    settle=settle)

    # Modal-only (desktop)
    if not no_modal_shot:
        popup_dt_png = desktop_dir / f"{base_name}_popup_dt.png"
        if try_capture_modal_only(page, popup_dt_png):
            images.append(popup_dt_png)
            close_any_modal(page)

    desktop_png = desktop_dir / f"{base_name}_dt.png"
    take_fullpage_screenshot(page, str(desktop_png))
    images.append(desktop_png)
    context.close()

    # Mobile (iPhone 12)
    iphone12 = {
        "viewport": {"width": 390, "height": 844},
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
        ),
        "is_mobile": True,
        "has_touch": True,
        "device_scale_factor": 3,
    }
    mctx = browser.new_context(
        viewport=iphone12["viewport"],
        user_agent=iphone12["user_agent"],
        is_mobile=iphone12["is_mobile"],
        has_touch=iphone12["has_touch"],
        device_scale_factor=iphone12["device_scale_factor"],
        ignore_https_errors=insecure,
    )
    mpage = mctx.new_page()
    nav_and_prepare(mpage, url, wait="load", insecure=insecure, defloat=defloat,
                    hide_selectors=hide_selectors, isi_reached=isi_reached, timeout_ms=nav_timeout_ms,
                    settle=settle)

    # Modal-only (mobile)
    if not no_modal_shot:
        popup_mb_png = mobile_dir / f"{base_name}_popup_mb.png"
        if try_capture_modal_only(mpage, popup_mb_png):
            images.append(popup_mb_png)
            close_any_modal(mpage)

    mobile_png = mobile_dir / f"{base_name}_mb.png"
    take_fullpage_screenshot(mpage, str(mobile_png))
    images.append(mobile_png)
    mctx.close()
    browser.close()
    return images

# ---------- inputs ----------

def parse_sitemap_file(path: Path) -> List[str]:
    txt = path.read_text(encoding="utf-8", errors="ignore").strip()
    if not txt:
        return []
    try:
        root = ET.fromstring(txt)
        ns = root.tag.split('}')[0].strip('{') if root.tag.startswith('{') else ''
        urls = []
        find_url = (lambda r: r.findall(f".//{{{ns}}}url")) if ns else (lambda r: r.findall(".//url"))
        for url_el in find_url(root):
            loc_el = url_el.find(f"{{{ns}}}loc") if ns else url_el.find("loc")
            if loc_el is not None and loc_el.text:
                urls.append(loc_el.text.strip())
        if urls:
            return urls
    except Exception:
        pass
    # Fallback: treat as plaintext list
    return [line.strip() for line in txt.splitlines() if line.strip() and not line.strip().startswith("#")]

def parse_url_list_file(path: Path) -> List[str]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    tokens = re.split(r"[\s,;|]+", raw)
    out = []
    for t in tokens:
        t = t.strip()
        if not t or t.startswith("#"):
            continue
        out.append(t)
    return out

# ---------- PDF ----------

def build_pdf_from_images(image_paths: List[Path], pdf_path: Path):
    imgs = [Image.open(p).convert("RGB") for p in image_paths if p.exists()]
    if not imgs:
        raise RuntimeError("No images to write to PDF.")
    first, *rest = imgs
    first.save(pdf_path, save_all=True, append_images=rest)

# ---------- orchestration ----------

def run_list(urls: List[str], out_dir: Path, insecure: bool, nav_timeout_ms: int,
             defloat: bool, hide_selectors: str, isi_reached: bool, include_nonhtml: bool,
             settle: bool, pdf_name: str, no_modal_shot: bool):
    filtered = [u for u in urls if not should_skip_url(u, include_nonhtml)]
    skipped = [u for u in urls if u not in filtered]
    total = len(filtered)
    ordered_images: List[Path] = []
    print(f"Found {len(urls)} URLs, processing {total} after filtering ({len(skipped)} skipped).")

    used: Set[str] = set()  # for unique slugs

    # Timing state for ETA
    t_batch_start = time.time()
    completed = 0
    avg_per_item: Optional[float] = None  # seconds

    with sync_playwright() as p:
        for idx, u in enumerate(filtered, start=1):
            # ETA before starting the item
            if completed > 0 and avg_per_item is not None:
                remaining = total - completed
                eta = remaining * avg_per_item
            else:
                eta = None

            slug = unique_slug_for_url(u, used)
            pct = int(idx / max(total, 1) * 100)

            print(f"[{idx}/{total}] {pct:3d}%  ETA {_fmt_eta(eta)}")
            print(f"   {u}")
            print(f"   → {slug}_dt.png / {slug}_mb.png (+popup variants if present)")

            t0 = time.time()
            imgs = capture_single_url(
                p, u, out_dir, insecure, nav_timeout_ms, defloat, hide_selectors, isi_reached,
                slug, settle, no_modal_shot
            )
            dt = time.time() - t0

            ordered_images.extend(imgs)
            completed += 1

            # Update average duration
            elapsed_batch = time.time() - t_batch_start
            avg_per_item = elapsed_batch / max(completed, 1)

            print(f"   ✓ captured in {_fmt_eta(dt)} (avg {_fmt_eta(avg_per_item)})\n")

    pdf_path = out_dir / pdf_name
    build_pdf_from_images(ordered_images, pdf_path)

    total_elapsed = time.time() - t_batch_start
    print(f"All done in {_fmt_eta(total_elapsed)}")
    return pdf_path, ordered_images, skipped

def capture_screenshots(url: Optional[str], out_dir: Path, insecure: bool = False, nav_timeout_ms: int = 60000,
                        defloat: bool = False, hide_selectors: str = "", isi_reached: bool = False,
                        sitemap_file: Optional[Path] = None, url_list_file: Optional[Path] = None,
                        include_nonhtml: bool = False, settle: bool = True, no_modal_shot: bool = False):
    # Prepare output and clear old PNGs
    out_dir.mkdir(parents=True, exist_ok=True)
    clear_previous_pngs(out_dir)

    # Timestamped PDF name
    ts = run_timestamp()
    final_pdf_name = f"screenshots_{ts}.pdf"

    if url_list_file:
        urls = parse_url_list_file(url_list_file)
        if not urls:
            raise SystemExit(f"No URLs found in list: {url_list_file}")
        pdf_path, images, skipped = run_list(
            urls, out_dir, insecure, nav_timeout_ms, defloat, hide_selectors, isi_reached,
            include_nonhtml, settle, final_pdf_name, no_modal_shot
        )
        return {"mode": "list", "count": len(images), "skipped": skipped, "pdf_path": str(pdf_path),
                "images": [str(p) for p in images]}

    if sitemap_file:
        urls = parse_sitemap_file(sitemap_file)
        if not urls:
            raise SystemExit(f"No URLs found in sitemap: {sitemap_file}")
        pdf_path, images, skipped = run_list(
            urls, out_dir, insecure, nav_timeout_ms, defloat, hide_selectors, isi_reached,
            include_nonhtml, settle, final_pdf_name, no_modal_shot
        )
        return {"mode": "sitemap", "count": len(images), "skipped": skipped, "pdf_path": str(pdf_path),
                "images": [str(p) for p in images]}

    if not url:
        raise SystemExit("You must provide a URL or use --sitemap-file / --url-list.")

    with sync_playwright() as p:
        slug = slug_from_url(url)
        imgs = capture_single_url(
            p, url, out_dir, insecure, nav_timeout_ms, defloat, hide_selectors, isi_reached,
            slug, settle, no_modal_shot
        )
    pdf_path = out_dir / final_pdf_name
    build_pdf_from_images(imgs, pdf_path)
    return {"mode": "single", "pdf_path": str(pdf_path), "images": [str(p) for p in imgs]}

# ---------- CLI ----------

def parse_args():
    ap = argparse.ArgumentParser(description="Take desktop & mobile full-page screenshots and output a PDF.")
    ap.add_argument("url", nargs="?", help="Website URL (with or without http/https). Omit when using --sitemap-file/--url-list")
    ap.add_argument("-o", "--out-dir", default="output", help="Output directory (default: ./output)")
    ap.add_argument("--sitemap-file", type=str, default=None, help="Local path to sitemap XML or newline list of URLs.")
    ap.add_argument("--url-list", type=str, default=None, help="Local path to a plaintext list of URLs (CRLF/LF/tabs/whitespace supported).")
    ap.add_argument("--include-nonhtml", action="store_true", help="Include PDFs/images from sitemap/list (off by default).")
    ap.add_argument("--insecure", action="store_true", help="Ignore HTTPS certificate errors.")
    ap.add_argument("--timeout-ms", type=int, default=60000, help="Navigation timeout in ms (default 60000).")
    ap.add_argument("--defloat", action="store_true", help="Convert fixed/sticky elements to absolute/static.")
    ap.add_argument("--hide-selectors", default="", help="Comma-separated CSS selectors to hide before screenshot.")
    ap.add_argument("--isi-reached", action="store_true", help="Force ISI sections to the 'reached' state.")
    ap.add_argument("--no-settle", action="store_true", help="Do not auto-finish animations by scrolling/marking.")
    ap.add_argument("--no-modal-shot", action="store_true", help="Do not try to capture modal-only screenshots before the full page.")
    return ap.parse_args()

def main():
    args = parse_args()
    out = Path(args.out_dir)
    sitemap_file = Path(args.sitemap_file) if args.sitemap_file else None
    url_list_file = Path(args.url_list) if args.url_list else None
    results = capture_screenshots(
        args.url, out,
        insecure=args.insecure,
        nav_timeout_ms=args.timeout_ms,
        defloat=args.defloat,
        hide_selectors=args.hide_selectors,
        isi_reached=args.isi_reached,
        sitemap_file=sitemap_file,
        url_list_file=url_list_file,
        include_nonhtml=args.include_nonhtml,
        settle=(not args.no_settle),
        no_modal_shot=args.no_modal_shot
    )
    print("Done!")
    if results["mode"] in ("sitemap", "list"):
        print(f"Images captured: {results['count']}")
        if results.get("skipped"):
            print(f"Skipped {len(results['skipped'])} non-HTML urls")
    print(f"PDF       : {results['pdf_path']}")
    if "images" in results:
        for p in results["images"]:
            print(p)

if __name__ == "__main__":
    main()
