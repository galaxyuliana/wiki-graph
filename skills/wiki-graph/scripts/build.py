#!/usr/bin/env python3
"""Build an interactive knowledge graph of a markdown wiki.

Usage:  python3 build.py [ROOT] [OUT_DIR] [options]

  ROOT     directory to scan (default: git repo root of the cwd, else cwd)
  OUT_DIR  where outputs go  (default: ROOT/.wiki-graph)

Options:
  --serve [PORT]  build, watch for changes, and serve at http://127.0.0.1:PORT
                  (default 7177) — the open page updates itself live
  --watch         rebuild whenever a markdown file changes (no server)
  --check         also list broken markdown links; exit 1 if any (CI-friendly)
  --open          open the built page in the default browser
  --quiet         print nothing on success

Outputs:
  wiki-graph.html  self-contained page; open it in any browser, no server needed
  graph.json       the same graph, agent-readable

Optional config, ROOT/.wiki-graph.json:
  { "title":  "My Wiki",            // page title (default: ROOT dir name)
    "roots":  ["docs", "wiki"],     // scan only these subdirs (default: all)
    "ignore": ["drafts", "vendor"]  // extra directory names to skip
  }

Zero dependencies: Python 3.8+ stdlib only.
"""
import datetime
import json
import os
import re
import subprocess
import sys
import threading
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
IGNORE_DIRS = {"node_modules", "__pycache__", "venv", ".venv", "site-packages"}
INDEX_NAMES = {"index.md", "readme.md", "_index.md", "home.md", "moc.md"}
AGENT_FILES = {"AGENTS.md", "CLAUDE.md", "GEMINI.md"}  # machine config, not wiki content

FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.S)
LINK_RE = re.compile(r"\]\(([^)#\s]+\.md)")
WIKI_RE = re.compile(r"\[\[([^\]|#\n]+?)(?:[#|][^\]]*)?\]\]")  # Obsidian [[wikilinks]]
FENCE_RE = re.compile(r"^(```|~~~).*?^\1", re.S | re.M)
CODE_RE = re.compile(r"`[^`\n]+`")
TAG_SPLIT = re.compile(r"[,\s]+")
_ESC = re.compile(r"\\u([0-9a-fA-F]{4})")


def _unescape(s):
    # some backfilled frontmatter carries literal \uXXXX sequences — decode them
    return _ESC.sub(lambda m: chr(int(m.group(1), 16)), s)


def fm_field(text, key):
    m = re.search(rf"^{key}:\s*(.+)$", text, re.M)
    return _unescape(m.group(1).strip().strip("\"'")) if m else None


def fm_tags(text):
    """Parse `tags:` — inline (`a, b` / `[a, b]`) or a YAML `- item` list."""
    m = re.search(r"^tags:[ \t]*(.*)$", text, re.M)
    if not m:
        return []
    inline = m.group(1).strip().strip("[]")
    if inline:
        return [t.strip().strip("\"'#") for t in TAG_SPLIT.split(inline) if t.strip()]
    tags, rest = [], text[m.end():].splitlines()
    for line in rest:
        lm = re.match(r"\s+-\s+(.+)", line)
        if not lm:
            break
        tags.append(lm.group(1).strip().strip("\"'#"))
    return tags


def load_config(root):
    try:
        with open(os.path.join(root, ".wiki-graph.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def detect_root():
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return os.getcwd()


def first_seen_dates(root):
    """Map repo-relative path -> date the file first appeared in git (one pass)."""
    try:
        out = subprocess.run(
            ["git", "-C", root, "log", "--reverse", "--diff-filter=A",
             "--name-only", "--format=%x01%as"],
            capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return {}
    seen, cur = {}, ""
    for line in out.splitlines():
        if line.startswith("\x01"):
            cur = line[1:]
        elif line.strip() and line not in seen:
            seen[line] = cur
    return seen


def collect(root, cfg):
    ignore = IGNORE_DIRS | set(cfg.get("ignore") or [])
    files = []
    for broot in (cfg.get("roots") or [""]):
        base = os.path.join(root, broot) if broot else root
        for dp, dns, fns in os.walk(base):
            dns[:] = [d for d in dns if d not in ignore and not d.startswith(".")]
            for fn in fns:
                if fn.lower().endswith((".md", ".markdown")) and fn not in AGENT_FILES:
                    p = os.path.join(dp, fn)
                    files.append((p, os.path.relpath(p, root)))
    return sorted(set(files))


def build_graph(root, cfg):
    files = collect(root, cfg)
    relset = {rel for _, rel in files}
    born = first_seen_dates(root)
    # basename index for wikilink resolution (Obsidian shortest-path convention)
    byname = {}
    for rel in relset:
        byname.setdefault(
            os.path.splitext(os.path.basename(rel))[0].lower(), []).append(rel)
    nodes, edges, broken = {}, [], []
    for p, rel in files:
        try:
            txt = open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        fm = FM_RE.match(txt)
        ftxt = fm.group(1) if fm else ""
        typ = fm_field(ftxt, "type") or (
            "index" if os.path.basename(rel).lower() in INDEX_NAMES else "untyped")
        rel_posix = rel.replace(os.sep, "/")
        parts = rel_posix.split("/")
        nodes[rel] = {
            "path": rel_posix,
            "title": (fm_field(ftxt, "title")
                      or os.path.splitext(os.path.basename(rel))[0])[:60],
            "type": typ.lower(),
            "status": (fm_field(ftxt, "status") or "living").lower(),
            "area": parts[0] if len(parts) > 1 else "(root)",
            "sub": parts[1] if len(parts) > 2 else "",
            "tags": fm_tags(ftxt),
            "born": (born.get(rel_posix) or fm_field(ftxt, "date")
                     or fm_field(ftxt, "created") or fm_field(ftxt, "timestamp")
                     or ""),
        }
        # code fences and inline code spans are examples, not links
        body = CODE_RE.sub("", FENCE_RE.sub("", txt))
        for m in LINK_RE.finditer(body):
            tgt = m.group(1)
            if tgt.startswith(("http://", "https://")):
                continue
            cand = (os.path.normpath(tgt.lstrip("/")) if tgt.startswith("/")
                    else os.path.normpath(os.path.join(os.path.dirname(rel), tgt)))
            if cand in relset:
                if cand != rel:
                    edges.append((rel, cand))
            else:
                broken.append([rel.replace(os.sep, "/"), tgt])
        for m in WIKI_RE.finditer(body):
            t = m.group(1).strip()
            cand = os.path.normpath(t + ".md")          # [[folder/name]] form
            if cand not in relset:
                hits = byname.get(t.lower(), [])
                cand = hits[0] if len(hits) == 1 else None  # unambiguous basename only
            if cand and cand in relset:
                if cand != rel:
                    edges.append((rel, cand))
            else:
                broken.append([rel.replace(os.sep, "/"), f"[[{t}]]"])

    edges = sorted(set(edges))
    din, dout = {}, {}
    for s, t in edges:
        dout[s] = dout.get(s, 0) + 1
        din[t] = din.get(t, 0) + 1
    for rel, n in nodes.items():
        n["in"], n["out"] = din.get(rel, 0), dout.get(rel, 0)
    return {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "title": cfg.get("title") or os.path.basename(os.path.abspath(root)),
        "root": os.path.basename(os.path.abspath(root)),
        "nodes": list(nodes.values()),
        "edges": [[s.replace(os.sep, "/"), t.replace(os.sep, "/")]
                  for s, t in edges],
        "broken": sorted(broken),
    }


def write_outputs(graph, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    if os.path.basename(os.path.normpath(out_dir)) == ".wiki-graph":
        # self-ignoring output dir: generated files never dirty the repo
        gi = os.path.join(out_dir, ".gitignore")
        if not os.path.exists(gi):
            with open(gi, "w", encoding="utf-8") as f:
                f.write("# generated by wiki-graph — `git add -f .wiki-graph` to commit it\n*\n")
    with open(os.path.join(out_dir, "graph.json"), "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=1, ensure_ascii=False)
    data = json.dumps(graph, separators=(",", ":"),
                      ensure_ascii=False).replace("</", "<\\/")
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    out = os.path.join(out_dir, "wiki-graph.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(tpl.replace("__DATA__", data))
    return out


def build_once(root, out_dir, quiet=False, check=False):
    graph = build_graph(root, load_config(root))
    out = write_outputs(graph, out_dir)
    if not quiet:
        orphans = sum(1 for n in graph["nodes"] if n["in"] + n["out"] == 0)
        print(f"{len(graph['nodes'])} docs, {len(graph['edges'])} links, "
              f"{orphans} unlinked -> {out} + graph.json")
    if check and graph["broken"]:
        print(f"\n{len(graph['broken'])} broken link(s):", file=sys.stderr)
        for src, tgt in graph["broken"]:
            print(f"  {src} -> {tgt}", file=sys.stderr)
        sys.exit(1)
    return out


def tree_signature(root, cfg):
    """Cheap change detector: (path, mtime, size) of every scanned .md + config."""
    sig = []
    for p, _ in collect(root, cfg):
        try:
            st = os.stat(p)
            sig.append((p, st.st_mtime_ns, st.st_size))
        except OSError:
            pass
    for extra in (os.path.join(root, ".wiki-graph.json"),
                  os.path.join(HERE, "template.html")):
        try:
            st = os.stat(extra)
            sig.append((extra, st.st_mtime_ns, st.st_size))
        except OSError:
            pass
    return hash(tuple(sig))


def watch_loop(root, out_dir, quiet):
    last = tree_signature(root, load_config(root))
    while True:
        try:
            import time
            time.sleep(1.2)
            cfg = load_config(root)
            sig = tree_signature(root, cfg)
            if sig != last:
                last = sig
                out = write_outputs(build_graph(root, cfg), out_dir)
                if not quiet:
                    now = datetime.datetime.now().strftime("%H:%M:%S")
                    print(f"[{now}] rebuilt {out}")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            if not quiet:
                print(f"watch error (retrying): {e}", file=sys.stderr)


class QuietHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass


def serve(root, out_dir, port, quiet, open_page):
    httpd = None
    for p in range(port, port + 10):
        try:
            httpd = ThreadingHTTPServer(
                ("127.0.0.1", p), partial(QuietHandler, directory=out_dir))
            port = p
            break
        except OSError:
            continue
    if httpd is None:
        sys.exit(f"error: no free port in {port}..{port + 9}")
    url = f"http://127.0.0.1:{port}/wiki-graph.html"
    if not quiet:
        print(f"live at {url}  (Ctrl-C to stop)")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    if open_page:
        webbrowser.open(url)
    try:
        watch_loop(root, out_dir, quiet)
    except KeyboardInterrupt:
        pass


def main():
    args = sys.argv[1:]
    quiet = "--quiet" in args
    do_open = "--open" in args
    do_watch = "--watch" in args
    do_serve = "--serve" in args
    port = 7177
    if do_serve:
        i = args.index("--serve")
        if i + 1 < len(args) and args[i + 1].isdigit():
            port = int(args.pop(i + 1))
    pos = [a for a in args if not a.startswith("--")]
    root = os.path.abspath(pos[0]) if pos else detect_root()
    out_dir = (os.path.abspath(pos[1]) if len(pos) > 1
               else os.path.join(root, ".wiki-graph"))
    if not os.path.isdir(root):
        sys.exit(f"error: not a directory: {root}")

    out = build_once(root, out_dir, quiet, check="--check" in args)
    if do_serve:
        serve(root, out_dir, port, quiet, open_page=do_open or not quiet)
    elif do_watch:
        if not quiet:
            print("watching for changes  (Ctrl-C to stop)")
        try:
            watch_loop(root, out_dir, quiet)
        except KeyboardInterrupt:
            pass
    elif do_open:
        webbrowser.open("file://" + out)


if __name__ == "__main__":
    main()
