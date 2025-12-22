# miner.py
import pandas as pd
from pydriller import Repository
from utils import *
from analyzer import Analyzer
from config import Config

def mine_repository(repo_path):

    rows = []
    stats = {
        "all_commits": 0,
        "fix_commits": 0,
        "tdb_commits": 0
    }
    
    branches = get_all_branches(repo_path)
    processed_hashes = set()
    print(f"Starting mining repository {repo_path} with {len(branches)} branches...")

    for branch in branches:
        # Here we only consider non-merge commits
        repo = Repository(repo_path, only_in_branch=branch, only_no_merge=True)
        
        for commit in repo.traverse_commits():
            # only consider unique commits
            if commit.hash in processed_hashes:
                continue
            processed_hashes.add(commit.hash)

            stats["all_commits"] += 1
            if is_bugfix_message(commit.msg):
                stats["fix_commits"] += 1
            
            if stats["all_commits"] % 500 == 0:
                print(f"Processed {stats['all_commits']} commits")

            modified_files = commit.modified_files
            commit_size = len(modified_files)
            if commit_size == 0 or commit_size > Config.MAX_MODIFIED_FILES:
                continue

            # precalculate added lines of code
            total_added_loc = sum(mod.added_lines for mod in modified_files)
            if total_added_loc > Config.MAX_ADDED_LOC:
                continue

            # detect TDB behavior
            if Analyzer.detect_tdb_behavior(modified_files, commit.msg):
                stats["tdb_commits"] += 1

            # record file additions for distance calculation
            for mod in modified_files:

                path = mod.new_path or mod.old_path
                if not path or not path.endswith(".java"):
                    continue

                if mod.change_type.name != "ADD":
                    continue     

                file_type = None
                if is_test_file(path):
                    file_type = "test"
                elif is_prod_file(path):
                    file_type = "prod"
                else:
                    continue
                    
                rows.append({
                    "commit_index": stats["all_commits"], # TODO: fix index across branches
                    "commit": commit.hash,
                    "date": commit.committer_date,
                    "file_type": file_type,
                    "path": path.replace("\\", "/"),
                    "commit_size": commit_size,
                    "package": extract_package(path),
                    "added_lines": mod.added_lines
                })
    
    return pd.DataFrame(rows), stats