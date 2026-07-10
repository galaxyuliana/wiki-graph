# Contributing to wiki-graph

Thanks for wanting to help! This project is deliberately small; the best
contributions keep it that way.

## Ground rules

1. **Zero dependencies.** The builder is Python 3.8+ stdlib only; the viewer
   is one self-contained HTML file with no external resources (no CDNs, no
   fonts, no fetch calls except the same-origin `graph.json` poll in live
   mode). PRs that add a dependency need an extraordinary reason.
2. **No site-specific hardcoding.** Nothing in `build.py` or `template.html`
   may reference a particular wiki, company, folder name, or taxonomy.
   Repo-specific behavior goes through `.wiki-graph.json` or frontmatter.
3. **Every feature works from a plain terminal.** Agent integrations
   (skill, hooks, AGENTS.md) are thin adapters over the CLI.

## Dev loop

```bash
# run the tests (stdlib unittest, ~0.3s)
python3 -m unittest discover tests -v

# eyeball your changes on the demo wiki
python3 build.py examples/demo-wiki /tmp/wg --open

# test live mode
python3 build.py examples/demo-wiki /tmp/wg --serve
# then edit a demo file and watch the page morph
```

If you have Claude Code, `claude plugin validate . --strict` checks the
plugin + marketplace manifests.

## Pull requests

- Add or update a test in `tests/test_build.py` for builder changes.
- For viewer changes, include a before/after screenshot or GIF.
- Update `CHANGELOG.md` under "Unreleased".
- Keep commits focused; one idea per PR (we practice what the demo preaches).

## Reporting bugs

Open an issue with: your OS + Python version, the command you ran, what you
expected, what happened. For rendering bugs, attach the `graph.json` if you
can share it (or a minimal repro wiki — three files is usually enough).
