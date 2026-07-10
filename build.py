#!/usr/bin/env python3
"""Convenience entry point — forwards to the real builder inside the skill.

The core lives in skills/wiki-graph/scripts/ so that the skill folder stays a
self-contained, portable Agent Skill (https://agentskills.io). This shim just
lets you run `python3 wiki-graph/build.py` from a clone or submodule.
"""
import os
import runpy
import sys

sys.argv[0] = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "skills", "wiki-graph", "scripts", "build.py")
runpy.run_path(sys.argv[0], run_name="__main__")
