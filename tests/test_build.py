#!/usr/bin/env python3
"""Tests for the wiki-graph builder. Stdlib only: python3 -m unittest discover tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(REPO, "skills", "wiki-graph", "scripts", "build.py")
DEMO = os.path.join(REPO, "examples", "demo-wiki")


def run_build(root, out, extra=()):
    return subprocess.run(
        [sys.executable, BUILD, root, out, "--quiet", *extra],
        capture_output=True, text=True, timeout=120)


class TestDemoWiki(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = cls.tmp.name
        r = run_build(DEMO, cls.out)
        assert r.returncode == 0, r.stderr
        with open(os.path.join(cls.out, "graph.json"), encoding="utf-8") as f:
            cls.g = json.load(f)
        cls.by = {n["path"]: n for n in cls.g["nodes"]}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_markdown_file_is_a_node(self):
        md = sum(len([f for f in fs if f.endswith(".md")])
                 for _, _, fs in os.walk(DEMO))
        self.assertEqual(len(self.g["nodes"]), md)

    def test_relative_link_resolves(self):
        self.assertIn(["index.md", "concepts/digital-garden.md"], self.g["edges"])

    def test_wikilink_resolves_by_basename(self):
        self.assertIn(["concepts/digital-garden.md", "concepts/zettelkasten.md"],
                      self.g["edges"])

    def test_wikilink_with_alias_and_anchor_still_resolves(self):
        # linking-well.md links [[wikilinks]] -> reference/wikilinks.md
        self.assertIn(["guides/linking-well.md", "reference/wikilinks.md"],
                      self.g["edges"])

    def test_orphan_detected(self):
        o = self.by["notes/orphan-island.md"]
        self.assertEqual((o["in"], o["out"]), (0, 0))

    def test_frontmatter_parsed(self):
        self.assertEqual(self.by["index.md"]["type"], "index")
        self.assertEqual(self.by["decisions/0001-plain-markdown.md"]["status"],
                         "frozen")
        self.assertEqual(self.by["concepts/digital-garden.md"]["tags"],
                         ["gardening", "philosophy"])

    def test_code_spans_are_not_links(self):
        # reference/wikilinks.md documents [[name]] syntax in backticks
        self.assertEqual(self.g["broken"], [])

    def test_degrees_are_consistent(self):
        self.assertEqual(sum(n["in"] for n in self.g["nodes"]),
                         len(self.g["edges"]))
        self.assertEqual(sum(n["out"] for n in self.g["nodes"]),
                         len(self.g["edges"]))

    def test_html_is_self_contained(self):
        with open(os.path.join(self.out, "wiki-graph.html"),
                  encoding="utf-8") as f:
            html = f.read()
        self.assertNotIn("__DATA__", html)
        self.assertIn('"nodes"', html)
        self.assertNotIn("<script src=", html)      # no external resources
        self.assertNotIn('href="http', html)


class TestConfigAndCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.out = os.path.join(self.root, "graph-out")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)

    def test_config_roots_ignore_and_title(self):
        self.write(".wiki-graph.json", json.dumps(
            {"title": "Configured", "roots": ["docs"], "ignore": ["skipme"]}))
        self.write("docs/a.md", "[b](b.md)")
        self.write("docs/b.md", "hello")
        self.write("docs/skipme/c.md", "ignored")
        self.write("elsewhere/d.md", "outside roots")
        r = run_build(self.root, self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        g = json.load(open(os.path.join(self.out, "graph.json")))
        self.assertEqual(g["title"], "Configured")
        self.assertEqual(sorted(n["path"] for n in g["nodes"]),
                         ["docs/a.md", "docs/b.md"])
        self.assertEqual(g["edges"], [["docs/a.md", "docs/b.md"]])

    def test_check_flag_fails_on_broken_links(self):
        self.write("a.md", "[gone](missing.md) and [[nowhere]]")
        r = run_build(self.root, self.out, extra=["--check"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing.md", r.stderr)
        g = json.load(open(os.path.join(self.out, "graph.json")))
        self.assertEqual(len(g["broken"]), 2)

    def test_agent_instruction_files_are_excluded(self):
        self.write("a.md", "hello")
        self.write("AGENTS.md", "## Knowledge graph\nrebuild after edits")
        self.write("CLAUDE.md", "project instructions")
        run_build(self.root, self.out)
        g = json.load(open(os.path.join(self.out, "graph.json")))
        self.assertEqual([n["path"] for n in g["nodes"]], ["a.md"])

    def test_default_out_dir_self_gitignores(self):
        self.write("a.md", "hello")
        out = os.path.join(self.root, ".wiki-graph")
        run_build(self.root, out)
        with open(os.path.join(out, ".gitignore"), encoding="utf-8") as f:
            self.assertIn("*", f.read())

    def test_custom_out_dir_gets_no_gitignore(self):
        self.write("a.md", "hello")
        run_build(self.root, self.out)   # "graph-out", not ".wiki-graph"
        self.assertFalse(os.path.exists(os.path.join(self.out, ".gitignore")))

    def test_ambiguous_wikilink_is_not_an_edge(self):
        self.write("x/dup.md", "one")
        self.write("y/dup.md", "two")
        self.write("a.md", "[[dup]]")
        run_build(self.root, self.out)
        g = json.load(open(os.path.join(self.out, "graph.json")))
        self.assertEqual(g["edges"], [])
        self.assertEqual(g["broken"], [["a.md", "[[dup]]"]])


if __name__ == "__main__":
    unittest.main()
