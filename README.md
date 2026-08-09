# The Morning Pull

A personal news page that rebuilds itself every morning. Each section is one
prompt you write; a scheduled job runs each prompt through Claude with live web
search, assembles the answers into a single web page, and publishes it to GitHub
Pages. Open your bookmark, read your custom paper.

## What you edit

Just **`prompts.yaml`**. Add a section by copying a block; remove one by deleting
its block; reorder by moving blocks. That's the whole day-to-day workflow.

## One-time setup (about 10 minutes)

1. **Create a GitHub repo** and add these files to it.

2. **Add your API key.** In the repo: *Settings → Secrets and variables → Actions
   → New repository secret.* Name it `ANTHROPIC_API_KEY`, paste your key from
   console.anthropic.com. (The key stays a secret — it is never in the published page.)

3. **Turn on Pages.** *Settings → Pages → Build and deployment → Source:*
   choose **GitHub Actions**.

4. **Run it once by hand** to confirm it works: *Actions tab → Morning dispatch →
   Run workflow.* After it finishes, your page is live at
   `https://<your-username>.github.io/<repo-name>/`.

After that it runs on its own each morning.

## Changing when it runs

Edit the `cron:` line in `.github/workflows/briefing.yml`. The time is in **UTC**.
`0 11 * * *` is 7 AM Eastern Daylight Time. Subtract your UTC offset to pick your
hour (e.g. for 7 AM Central use `0 12 * * *`).

## Changing the model or search depth

Both live at the top of `prompts.yaml` (`model:` and `max_searches_per_prompt:`).
Current model names are at docs.claude.com/en/docs/about-claude/models.

## Running locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...
python generate.py      # writes index.html; open it in a browser
```

## Cost

You're running a handful of short, web-searching prompts once a day. That's a few
cents daily in API usage. Hosting and scheduling on GitHub are free.

## Notes

- Each item shows its **source links** — AI news summaries can overstate a rumor,
  so click through when it matters.
- If one prompt fails on a given day, that section shows a short note and the rest
  of the page still builds.
- Want an archive of past days instead of overwriting? Have the workflow write to
  `archive/YYYY-MM-DD.html` as well as `index.html` — a small change to `generate.py`.
