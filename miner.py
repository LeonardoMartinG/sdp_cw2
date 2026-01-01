import pandas as pd
from pydriller import Repository

from config import Config
from analyzer import Analyzer
from utils import (
    extract_package,
    extract_project,
    get_all_branches,
    is_bugfix_message,
    is_prod_file,
    is_squashed_message,
    is_test_file,
    norm_path,
)


def _path_allowed(path: str) -> bool:
    p = norm_path(path)

    if Config.EXCLUDE_PATH_PREFIXES:
        for pre in Config.EXCLUDE_PATH_PREFIXES:
            if p.startswith(pre):
                return False

    if Config.INCLUDE_PATH_PREFIXES:
        return any(p.startswith(pre) for pre in Config.INCLUDE_PATH_PREFIXES)

    return True


def mine_repository(repo_path: str, mode: str):
    if mode not in Config.MODE_OPTIONS:
        raise ValueError(f"Invalid mode: {mode}. Choose from {Config.MODE_OPTIONS}.")

    rows = []
    stats = {"all_commits": 0, "fix_commits": 0, "tdb_commits": 0}

    branches = get_all_branches(repo_path)
    processed_hashes = set()
    print(f"[Miner] Starting mining repository: {repo_path} (branches: {len(branches)})")

    for branch in branches:
        repo = Repository(repo_path, only_in_branch=branch, only_no_merge=True)

        for commit in repo.traverse_commits():
            if is_squashed_message(commit.msg):
                if mode == "DEBUG":
                    print(f"[Miner][DEBUG] Skipping squash commit: {commit.hash}")
                continue

            if commit.hash in processed_hashes:
                continue
            processed_hashes.add(commit.hash)

            stats["all_commits"] += 1
            if is_bugfix_message(commit.msg):
                stats["fix_commits"] += 1

            if stats["all_commits"] % 500 == 0:
                print(f"[Miner] Processed {stats['all_commits']} commits")

            modified_files = commit.modified_files
            commit_size = len(modified_files)

            if commit_size == 0 or commit_size > Config.MAX_MODIFIED_FILES:
                continue

            total_added_loc = sum(getattr(mod, "added_lines", 0) or 0 for mod in modified_files)
            if total_added_loc > Config.MAX_ADDED_LOC:
                continue

            if Analyzer.detect_tdb_behavior(modified_files, commit.msg):
                stats["tdb_commits"] += 1

            allowed_types = {"ADD", "MODIFY", "RENAME"}

            for mod in modified_files:
                change_type = getattr(mod, "change_type", None)
                change_name = getattr(change_type, "name", None) if change_type else None
                if change_name not in allowed_types:
                    continue

                path = mod.new_path or mod.old_path
                if not path or not str(path).endswith(".java"):
                    continue

                path = norm_path(path)
                if not _path_allowed(path):
                    continue

                file_type = None
                if is_test_file(path):
                    file_type = "test"
                elif is_prod_file(path):
                    file_type = "prod"
                else:
                    continue

                rows.append(
                    {
                        "commit": commit.hash,
                        "date": commit.committer_date,
                        "file_type": file_type,
                        "path": path,
                        "package": extract_package(path),
                        "project": extract_project(path),
                        "added_lines": getattr(mod, "added_lines", 0) or 0,
                        "commit_size": commit_size,
                        "commit_msg": commit.msg or "",
                        "change_type": change_name,
                    }
                )

    return pd.DataFrame(rows), stats
