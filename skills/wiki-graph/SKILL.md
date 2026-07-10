---
name: wiki-graph
description: Render a markdown wiki, docs repo, or notes vault as an interactive knowledge graph — an Obsidian-style force view (self-contained HTML) plus an agent-readable graph.json. Use whenever the user invokes /wiki-graph, asks to see, refresh, watch, or schedule the knowledge graph, wants the wiki or docs visualized, or asks about hubs, orphans, broken links, or clusters in a docs repo. Works on any folder of markdown files; no dependencies beyond Python 3.
---

# wiki-graph

Build the graph of the repo the user is working in and show it. Every node is a
markdown file (frontmatter `type`/`status`/`tags` drive color, filters, and
search); every edge is a real markdown link — both `[text](path.md)` and
Obsidian `[[wikilinks]]`.

All commands below use `<skill-dir>` for this skill's base directory (stated
when the skill loads).

## Default flow (manual build)

1. `ROOT` = `git rev-parse --show-toplevel` (not a git repo → use the cwd).
2. Run `python3 "<skill-dir>/scripts/build.py" "$ROOT"` — outputs land in
   `$ROOT/.wiki-graph/` (override with a second positional arg if the user
   wants them elsewhere).
3. Open `wiki-graph.html` from there (`open` on macOS, `xdg-open` on Linux,
   `start` on Windows) and relay the doc/link/orphan counts the script printed.
4. If `.wiki-graph/` is new in a git repo, suggest adding it to `.gitignore`
   (one line) — or committing it, if they want the graph shared.

## Live mode (auto-updating)

- **In Claude Code with the plugin installed**, a PostToolUse hook already
  rebuilds `.wiki-graph/` after every markdown edit — building once (step
  above) is all it takes to turn that on for a repo.
- When the user says **live / watch / serve**, run
  `python3 "<skill-dir>/scripts/build.py" "$ROOT" --serve` **in the
  background**, then tell them the URL it printed
  (default `http://127.0.0.1:7177/wiki-graph.html`). The open page polls
  `graph.json` and morphs in place — new docs flash into the web as they are
  written. Stop it when they ask (kill the background job).

## Scheduled mode

When the user wants the graph rebuilt on a schedule (e.g. nightly):

- Preferred, if your environment has a scheduler (Claude Code cron, CI cron):
  schedule `python3 "<skill-dir>/scripts/build.py" "<ROOT>" --quiet`.
- Plain OS fallback — offer this crontab line (adjust paths):
  `0 7 * * * python3 <skill-dir>/scripts/build.py <ROOT> --quiet`
- For a public, always-fresh graph of a GitHub repo, point them at
  `integrations/github-pages.yml` in this plugin's repository — it publishes
  the graph to GitHub Pages on every push and on a daily cron.

## Answering questions about the graph

Read `$ROOT/.wiki-graph/graph.json` (rebuild first if stale): nodes carry
`type`, `status`, `tags`, `in`, `out` — `in + out == 0` → orphan; high `in` →
hub. `edges` are `[from, to]` doc paths. `broken` lists `[source, target]`
links that point at missing files — offer to fix those when asked.
`--check` exits 1 when broken links exist (useful in CI).

## Notes

- Optional per-repo config `ROOT/.wiki-graph.json`:
  `{"title": "My Wiki", "roots": ["docs"], "ignore": ["vendor"]}`.
- Stdlib-only, ~1s on a 400-doc wiki; dot-dirs and `node_modules` are skipped.
- Timeline replay appears automatically when git history (or frontmatter
  dates) span more than one day.
