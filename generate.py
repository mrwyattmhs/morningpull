#!/usr/bin/env python3
"""
Build the morning dispatch page.

Reads prompts.yaml, runs each section's prompt through Claude with live web
search, and writes a single index.html. Designed to be run once each morning
by a scheduler (see .github/workflows/briefing.yml), but you can also run it
by hand:  python generate.py

Requires the ANTHROPIC_API_KEY environment variable.
"""

import os
import sys
import html
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml
import markdown as md
from anthropic import Anthropic


# ----------------------------------------------------------------------
# Load config
# ----------------------------------------------------------------------
def load_config(path="prompts.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not cfg or "sections" not in cfg:
        sys.exit("prompts.yaml has no 'sections:' list — nothing to build.")
    return cfg


# ----------------------------------------------------------------------
# Ask Claude one prompt, with web search enabled.
# Returns (html_body, sources) where sources is a list of {title, url}.
# ----------------------------------------------------------------------
def run_prompt(client, model, prompt, max_searches):
    system = (
        "You are assembling a section of someone's personal morning news page. "
        "Search the web for current information. Be concise and factual. Use short "
        "paragraphs or a tight bulleted list. Do not pad. When something is a rumor "
        "or a single-source report, say so plainly rather than stating it as settled."
    )

    resp = client.messages.create(
        model=model,
        max_tokens=1200,
        system=system,
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": max_searches,
        }],
        messages=[{"role": "user", "content": prompt}],
    )

    # Collect the assistant's prose from all text blocks, and gather any
    # cited web sources so we can link them under the section.
    text_parts = []
    sources = {}
    for block in resp.content:
        if block.type == "text":
            text_parts.append(block.text)
            for cit in (getattr(block, "citations", None) or []):
                url = getattr(cit, "url", None)
                if url:
                    sources[url] = getattr(cit, "title", None) or url

    body_md = "".join(text_parts).strip() or "_No results returned for this section today._"
    body_html = md.markdown(body_md, extensions=["extra", "sane_lists"])
    source_list = [{"title": t, "url": u} for u, t in sources.items()]
    return body_html, source_list


# ----------------------------------------------------------------------
# Render one section to HTML
# ----------------------------------------------------------------------
def render_section(index, title, body_html, sources):
    num = f"{index:02d}"
    if sources:
        links = "\n".join(
            f'<li><a href="{html.escape(s["url"])}">{html.escape(s["title"])}</a></li>'
            for s in sources
        )
        sources_html = f'<div class="sources"><span class="sources-label">Sources</span><ul>{links}</ul></div>'
    else:
        sources_html = ""

    return f"""
    <section class="entry">
      <div class="entry-head">
        <span class="entry-num">{num}</span>
        <h2 class="entry-title">{html.escape(title)}</h2>
      </div>
      <div class="entry-body">{body_html}</div>
      {sources_html}
    </section>
    """


# ----------------------------------------------------------------------
# Styles for all three themes (plain string — no f-string brace-escaping).
# Every color reads from CSS variables; each theme[data-theme] block sets
# the palette and a few structural overrides so the three read as distinct
# layouts, not just recolors of one.
# ----------------------------------------------------------------------
_PAGE_CSS = """
  :root { --maxw: 720px; --rail: 92px; }
  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  body {
    margin: 0;
    padding-left: var(--rail);
    font-family: "Inter", system-ui, sans-serif;
    line-height: 1.6;
    transition: background .28s ease, color .28s ease;
  }

  /* ---------- Theme palettes ---------- */
  body[data-theme="editorial"] {
    --paper:#f3f4f1; --ink:#1a2230; --muted:#5c6672; --accent:#b23a2e; --hair:#d8dad4;
    background: var(--paper); color: var(--ink);
  }
  body[data-theme="green"] {
    --paper:#14572f; --ink:#ffffff; --muted:#c7e3d3; --accent:#ffd166; --hair:rgba(255,255,255,.30);
    background: var(--paper); color: var(--ink);
  }
  body[data-theme="dark"] {
    --paper:#0e1116; --ink:#e8e6e1; --muted:#8b95a3; --accent:#e0a458; --hair:#232a33;
    background: var(--paper); color: var(--ink);
  }

  /* ---------- Left theme rail ---------- */
  .theme-rail {
    position: fixed; top: 0; left: 0; z-index: 20;
    width: var(--rail); height: 100vh;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 12px;
    border-right: 1px solid var(--hair);
  }
  .theme-rail .rail-label {
    position: absolute; top: 22px;
    font-family: "JetBrains Mono", monospace; font-size: 10px;
    letter-spacing: .16em; text-transform: uppercase; color: var(--muted);
  }
  .theme-rail button {
    appearance: none; cursor: pointer;
    width: 64px; height: 64px; border-radius: 14px;
    display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 7px;
    border: 1px solid var(--hair); background: transparent; color: var(--muted);
    font-family: "JetBrains Mono", monospace; font-size: 9px;
    letter-spacing: .1em; text-transform: uppercase;
    transition: transform .15s ease, border-color .15s ease, color .15s ease;
  }
  .theme-rail button:hover { transform: translateY(-1px); }
  .theme-rail button[aria-pressed="true"] { border-color: var(--accent); color: var(--ink); }
  .theme-rail .swatch {
    width: 22px; height: 22px; border-radius: 6px;
    box-shadow: inset 0 0 0 1px rgba(0,0,0,.18);
  }
  .sw-editorial { background: #f3f4f1; }
  .sw-green     { background: #14572f; }
  .sw-dark      { background: #0e1116; }

  /* ---------- Shared shell ---------- */
  .wrap { max-width: var(--maxw); margin: 0 auto; padding: 0 24px 96px; }

  header.mast { padding: 56px 0 20px; border-bottom: 2px solid var(--ink); }
  .mast .kicker {
    font-family: "JetBrains Mono", monospace;
    font-size: 12px; letter-spacing: .14em; text-transform: uppercase;
    color: var(--accent); margin: 0 0 14px;
  }
  .mast h1 {
    font-family: "Spectral", Georgia, serif;
    font-weight: 600; font-size: clamp(38px, 8vw, 60px);
    line-height: 1.02; letter-spacing: -.01em; margin: 0;
  }
  .mast .subtitle {
    font-family: "Spectral", Georgia, serif; font-style: italic;
    color: var(--muted); font-size: 18px; margin: 12px 0 0;
  }

  .entry { padding: 40px 0; border-bottom: 1px solid var(--hair); }
  .entry-head { display: flex; align-items: baseline; gap: 14px; margin-bottom: 14px; }
  .entry-num {
    font-family: "JetBrains Mono", monospace; font-size: 13px;
    color: var(--accent); padding-top: 4px;
  }
  .entry-title {
    font-family: "Spectral", Georgia, serif; font-weight: 600;
    font-size: 26px; letter-spacing: -.01em; margin: 0;
  }
  .entry-body { font-size: 17px; }
  .entry-body p { margin: 0 0 14px; }
  .entry-body ul { margin: 0 0 14px; padding-left: 20px; }
  .entry-body li { margin: 0 0 8px; }
  .entry-body a {
    color: var(--ink); text-decoration: underline;
    text-decoration-color: var(--accent); text-underline-offset: 2px;
  }

  .sources { margin-top: 18px; padding-top: 14px; border-top: 1px dotted var(--hair); }
  .sources-label {
    font-family: "JetBrains Mono", monospace; font-size: 11px;
    letter-spacing: .12em; text-transform: uppercase; color: var(--muted);
  }
  .sources ul { list-style: none; margin: 8px 0 0; padding: 0; }
  .sources li { margin: 0 0 4px; }
  .sources a { color: var(--muted); font-size: 14px; text-decoration: none; }
  .sources a:hover { color: var(--accent); }

  footer { margin-top: 40px; font-family: "JetBrains Mono", monospace; font-size: 12px; color: var(--muted); }

  /* ---------- GREEN: sans masthead, big stacked numerals, poster feel ---------- */
  body[data-theme="green"] .mast { border-bottom-color: rgba(255,255,255,.55); }
  body[data-theme="green"] .mast h1 { font-family: "Inter", sans-serif; font-weight: 600; letter-spacing: -.02em; }
  body[data-theme="green"] .mast .subtitle { font-family: "Inter", sans-serif; font-style: normal; }
  body[data-theme="green"] .entry-head { display: block; margin-bottom: 10px; }
  body[data-theme="green"] .entry-num {
    display: block; padding: 0 0 4px;
    font-family: "Inter", sans-serif; font-weight: 700; font-size: 40px; line-height: 1;
  }
  body[data-theme="green"] .entry-title { font-family: "Inter", sans-serif; font-weight: 600; font-size: 28px; }
  body[data-theme="green"] .entry-body a { color: var(--ink); text-decoration-color: var(--accent); }

  /* ---------- DARK: technical, left accent bar on hover ---------- */
  body[data-theme="dark"] .entry {
    padding-left: 18px; border-left: 2px solid transparent;
    transition: border-color .18s ease;
  }
  body[data-theme="dark"] .entry:hover { border-left-color: var(--accent); }
  body[data-theme="dark"] .entry-title { font-family: "Inter", sans-serif; font-weight: 600; }
  body[data-theme="dark"] .mast h1 { letter-spacing: -.015em; }

  /* ---------- Motion + a11y floor ---------- */
  @media (prefers-reduced-motion: no-preference) {
    .entry { animation: rise 0.5s ease both; }
    @keyframes rise { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
  }
  a:focus-visible, button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

  /* ---------- Responsive: rail becomes a top bar on phones ---------- */
  @media (max-width: 720px) {
    body { padding-left: 0; }
    .theme-rail {
      position: sticky; top: 0; left: 0; width: 100%; height: auto;
      flex-direction: row; justify-content: center; gap: 8px;
      padding: 10px; border-right: none; border-bottom: 1px solid var(--hair);
      background: var(--paper);
    }
    .theme-rail .rail-label { display: none; }
    .theme-rail button { width: auto; height: 42px; flex-direction: row; gap: 8px; padding: 0 14px; }
    .theme-rail .swatch { width: 16px; height: 16px; }
  }
"""


# The three-button rail. aria-pressed defaults to the editorial theme so the
# active state is correct before JavaScript runs (no flash).
_THEME_RAIL = """
  <nav class="theme-rail" aria-label="Page theme">
    <span class="rail-label">Theme</span>
    <button type="button" data-theme="editorial" aria-pressed="true"><span class="swatch sw-editorial"></span>Paper</button>
    <button type="button" data-theme="green" aria-pressed="false"><span class="swatch sw-green"></span>Green</button>
    <button type="button" data-theme="dark" aria-pressed="false"><span class="swatch sw-dark"></span>Dark</button>
  </nav>
"""


# Theme switching. Remembers the last choice via localStorage when available,
# and degrades silently (in-memory only) anywhere storage is blocked.
_PAGE_JS = """
  (function () {
    var KEY = "mp-theme";
    var THEMES = ["editorial", "green", "dark"];
    var body = document.body;
    var buttons = Array.prototype.slice.call(document.querySelectorAll(".theme-rail button"));

    function apply(theme) {
      if (THEMES.indexOf(theme) === -1) theme = "editorial";
      body.setAttribute("data-theme", theme);
      buttons.forEach(function (b) {
        b.setAttribute("aria-pressed", String(b.getAttribute("data-theme") === theme));
      });
      try { localStorage.setItem(KEY, theme); } catch (e) {}
    }

    var saved = null;
    try { saved = localStorage.getItem(KEY); } catch (e) {}
    apply(saved || "editorial");

    buttons.forEach(function (b) {
      b.addEventListener("click", function () { apply(b.getAttribute("data-theme")); });
    });
  })();
"""


# ----------------------------------------------------------------------
# Page shell (design lives here)
# ----------------------------------------------------------------------
def render_page(cfg, dateline, sections_html):
    title = html.escape(cfg.get("title", "The Morning Pull"))
    subtitle = html.escape(cfg.get("subtitle", ""))
    subtitle_html = f'<p class="subtitle">{subtitle}</p>' if subtitle else ""
    css = _PAGE_CSS
    rail = _THEME_RAIL
    script = _PAGE_JS
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,400;0,600;1,400&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body data-theme="editorial">
{rail}
  <div class="wrap">
    <header class="mast">
      <p class="kicker">{dateline}</p>
      <h1>{title}</h1>
      {subtitle_html}
    </header>
    <main>
      {sections_html}
    </main>
    <footer>Assembled {dateline} · regenerated daily</footer>
  </div>
<script>{script}</script>
</body>
</html>
"""


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set the ANTHROPIC_API_KEY environment variable first.")

    cfg = load_config()
    model = os.environ.get("CLAUDE_MODEL") or cfg.get("model", "claude-sonnet-5")
    max_searches = int(cfg.get("max_searches_per_prompt", 5))
    tz = ZoneInfo(cfg.get("timezone", "America/New_York"))
    dateline = datetime.now(tz).strftime("%A, %B %-d, %Y").upper()

    client = Anthropic()

    rendered = []
    for i, sec in enumerate(cfg["sections"], start=1):
        title = sec.get("title", f"Section {i}")
        prompt = sec.get("prompt", "").strip()
        print(f"  [{i}/{len(cfg['sections'])}] {title} ...", flush=True)
        if not prompt:
            body, sources = "<p><em>This section has no prompt.</em></p>", []
        else:
            try:
                body, sources = run_prompt(client, model, prompt, max_searches)
            except Exception as e:
                # One bad section shouldn't sink the whole page.
                body = f"<p><em>Couldn't build this section today: {html.escape(str(e))}</em></p>"
                sources = []
        rendered.append(render_section(i, title, body, sources))

    page = render_page(cfg, dateline, "\n".join(rendered))
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page)
    print("Wrote index.html")


if __name__ == "__main__":
    main()
