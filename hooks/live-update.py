#!/usr/bin/env python3
"""Claude Code PostToolUse hook: keep the knowledge graph fresh.

Fires after Write/Edit tool calls. If the edited file is markdown AND the
containing repo has already built a graph once (.wiki-graph/graph.json
exists somewhere up the tree), rebuild it silently. That existence check
makes live mode opt-in per repo: build the graph once and it stays fresh;
repos that never built one pay zero cost.

Always exits 0 and prints nothing — the agent conversation is never touched.
"""
import json
import os
import subprocess
import sys


def find_graph_root(path):
    d = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.isfile(os.path.join(d, ".wiki-graph", "graph.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if data.get("tool_name") not in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        return
    fp = (data.get("tool_input") or {}).get("file_path") or ""
    if not fp.lower().endswith((".md", ".markdown")):
        return
    root = find_graph_root(fp)
    if not root:
        return
    build = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "skills", "wiki-graph", "scripts", "build.py"))
    try:
        subprocess.run(
            [sys.executable or "python3", build, root,
             os.path.join(root, ".wiki-graph"), "--quiet"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
