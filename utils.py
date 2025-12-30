from pathlib import Path
from git import Repo
import re

def is_test_file(path: str) -> bool:
    path = path.replace("\\", "/")
    name = Path(path).stem
    return (
        path.endswith(".java")
        and "src/test" in path
        and name.endswith(("Test", "Tests", "IT", "IntegrationTest"))
    )

def is_prod_file(path: str) -> bool:
    path = path.replace("\\", "/")
    name = Path(path).stem
    return (
        path.endswith(".java")
        and ("src/main" in path or "src/java" in path)
        and not name.endswith(("Test", "Tests", "IT", "IntegrationTest"))
    )

def extract_package(path: str) -> str:
    path = path.replace("\\", "/")
    if "src/java/" in path:
        return path.split("src/java/")[1].rsplit("/", 1)[0]
    if "src/main/java/" in path:
        return path.split("src/main/java/")[1].rsplit("/", 1)[0]
    if "src/test/java/" in path:
        return path.split("src/test/java/")[1].rsplit("/", 1)[0]
    if "src/test/" in path:
        return path.split("src/test/")[1].rsplit("/", 1)[0]
    return ""

def is_bugfix_message(msg: str) -> bool:
    bugfix_keywords = [
        "fix", "fixed", "fixes", "fixing",
    ]
    msg_lower = msg.lower()
    return any(keyword in msg_lower for keyword in bugfix_keywords)

def is_squashed_message(msg: str) -> bool:
    # if the commit message contains '(#123)' pattern, consider it a squash and merge commit
    # we can use regular expression to detect this pattern
    pattern = r"\(#\d+\)"
    return re.search(pattern, msg) is not None

def get_all_branches(repo_path: str) -> list[str]:
    repo = Repo(repo_path)
    remote_refs = repo.remotes.origin.refs
    branches = [ref.name for ref in remote_refs if 'HEAD' not in ref.name]
    return branches