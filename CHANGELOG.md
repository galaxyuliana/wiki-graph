# Changelog

## 1.0.0 — 2026-07-10

First public release. 🎉

- Force-directed knowledge graph of any markdown folder: one self-contained
  HTML file + agent-readable `graph.json`, from a stdlib-only Python builder
- Markdown links **and** Obsidian `[[wikilinks]]` (aliases, anchors,
  shortest-path basename resolution); code fences/spans are ignored
- **Live mode**: `--serve` (watch + local server + in-place morphing page)
  and a Claude Code PostToolUse hook that rebuilds after markdown edits,
  opt-in per repo
- **Scheduled mode**: cron-friendly `--quiet`, plus a GitHub Pages workflow
  (`integrations/github-pages.yml`) that publishes the graph on every push
- Dynamic color modes (type / folder / status) computed from the repo's own
  values; folder colors for repos without frontmatter
- Timeline replay from git history or frontmatter dates
- Frontmatter `tags` — searchable, shown in tooltips and the detail panel
- Broken-link detection in `graph.json` (`broken`) and `--check` for CI
- Orphan/hub analytics, search (`/` shortcut), dark/light theme,
  reduced-motion support
- Portable Agent Skill (agentskills.io) + Claude Code plugin/marketplace
  manifests + AGENTS.md snippet + git post-commit hook
- Demo wiki (`examples/demo-wiki`), unit tests, CI
