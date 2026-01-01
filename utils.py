# utils.py
from __future__ import annotations

from pathlib import Path
from git import Repo
import re
from typing import List

# ------------------------------------------------------------------
# Normalization helpers
# ------------------------------------------------------------------

def norm_path(p: str) -> str:
    """Normalize paths to forward-slash POSIX style (Windows-safe)."""
    return (p or "").replace("\\", "/")

def is_java_file(path: str) -> bool:
    return bool(path) and norm_path(path).endswith(".java")

# ------------------------------------------------------------------
# Constants / heuristics
# ------------------------------------------------------------------

TEST_NAME_HINTS = (
    "Test", "Tests", "IT", "IntegrationTest",
    "Spec", "Specification", "Should", "TestCase"
)

TEST_DIR_HINTS = (
    "/src/test/", "/src/test/java/", "/src/testFixtures/",
    "/test/", "/tests/", "/spec/", "/__tests__/"
)

PROD_DIR_HINTS = (
    "/src/main/", "/src/main/java/", "/src/java/", "/main/"
)

# ------------------------------------------------------------------
# File classification helpers
# ------------------------------------------------------------------

def is_test_file(path: str) -> bool:
    """Return True if `path` looks like a Java test file."""
    p = norm_path(path)
    if not p.endswith(".java"):
        return False

    stem = Path(p).stem
    in_test_dir = any(h in p for h in TEST_DIR_HINTS)

    # Common test naming styles
    name_looks_testy = (
        stem.startswith("Test")
        or any(stem.endswith(suf) for suf in TEST_NAME_HINTS)
    )

    return in_test_dir or name_looks_testy


def is_prod_file(path: str) -> bool:
    """Return True if `path` looks like a Java production source file."""
    p = norm_path(path)
    if not p.endswith(".java"):
        return False

    stem = Path(p).stem
    name_looks_testy = (
        stem.startswith("Test")
        or any(stem.endswith(suf) for suf in TEST_NAME_HINTS)
    )

    # If it looks testy AND our test detector agrees, don't treat as prod
    if name_looks_testy and is_test_file(p):
        return False

    # Typical production layout OR fallback (not test)
    return any(h in p for h in PROD_DIR_HINTS) or not is_test_file(p)

# ------------------------------------------------------------------
# Package + project extraction
# ------------------------------------------------------------------

def extract_package(path: str) -> str:
    """Extract a directory/package fragment after common Java source roots."""
    p = norm_path(path)

    markers = [
        "src/main/java/",
        "src/test/java/",
        "src/java/",
        "src/test/",
        "test/",
        "tests/",
    ]

    for m in markers:
        if m in p:
            tail = p.split(m, 1)[1]
            if "/" in tail:
                return tail.rsplit("/", 1)[0]
            return ""

    return ""


def extract_project(path: str) -> str:
    """
    Extract a logical project/module name from a path.

    Examples:
      Java/src/main/java/...          -> Java
      fizz-buzz/src/test/java/...     -> fizz-buzz
      commons-math-legacy/...         -> commons-math-legacy
      src/main/java/...              -> root
    """
    p = norm_path(path).lstrip("/")
    parts = [x for x in p.split("/") if x]

    if not parts:
        return "root"

    # If the repo root uses src/... directly, call it root
    if parts[0] == "src":
        return "root"

    # If there is a src folder later, take the folder before it
    if "src" in parts:
        idx = parts.index("src")
        if idx > 0:
            return parts[idx - 1]

    # Otherwise just take top folder
    return parts[0]

# ------------------------------------------------------------------
# Commit message heuristics
# ------------------------------------------------------------------

def is_bugfix_message(msg: str) -> bool:
    """Heuristic to label bugfix commits."""
    m = (msg or "").lower()
    return any(k in m for k in (
        "fix", "fixed", "fixes", "fixing",
        "bug", "bugfix", "hotfix", "patch"
    ))


def is_squashed_message(msg: str) -> bool:
    """Detect GitHub squash-merge style messages like '(#123)'."""
    return re.search(r"\(#\d+\)", msg or "") is not None

# ------------------------------------------------------------------
# Git helpers
# ------------------------------------------------------------------

def get_all_branches(repo_path: str) -> List[str]:
    """Return branch names (origin refs if present, else local heads)."""
    repo = Repo(repo_path)

    # Local-only repo (no remotes)
    if not repo.remotes:
        return [h.name for h in repo.heads]

    remote_refs = repo.remotes.origin.refs
    return [ref.name for ref in remote_refs if "HEAD" not in ref.name]
