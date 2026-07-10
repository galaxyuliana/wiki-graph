# AGENTS.md snippet — live graph with any coding agent

AGENTS.md is read natively by Codex CLI, Cursor, Gemini CLI, GitHub Copilot,
Windsurf, Aider, Devin, Claude Code, and more. Paste the block below into the
`AGENTS.md` at the root of your wiki/docs repo (adjust the path to wherever
you cloned wiki-graph), and every agent that edits your docs will keep the
graph fresh — no plugin system required.

```markdown
## Knowledge graph

This repo's markdown files are visualized as a knowledge graph.

- After creating, editing, deleting, or renaming any markdown file, rebuild it:
  `python3 ~/tools/wiki-graph/build.py . --quiet`
- The interactive view is `.wiki-graph/wiki-graph.html`; the machine-readable
  form is `.wiki-graph/graph.json` (nodes carry `type`, `status`, `tags`,
  `in`, `out`; a node with `in + out == 0` is an orphan; `broken` lists
  dangling links). Read graph.json to answer questions about hubs, orphans,
  broken links, or how docs relate.
- Never edit files inside `.wiki-graph/` by hand — they are generated.
```
