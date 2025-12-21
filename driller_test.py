import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pydriller import Repository
from utils import *

#congif
START_DATE = "2018-01-01"
END_DATE   = "2023-12-31"

#local clone
#REPO_PATH = "repos/commons-lang"
REPO_PATH = "/home/yaoguyuan/Desktop/commons-lang"

#data collection
rows = []
num_all_commits = 0
num_fix_commits = 0
num_tdb_commits = 0

branches = get_all_branches(REPO_PATH)
# print(f"All branches in the repository: {branches}")
processed_commits = set()

for branch in branches:
    # print(f"Processing branch: {branch}")
    repo = Repository(REPO_PATH, only_in_branch=branch, only_no_merge=True)
    for i, commit in enumerate(repo.traverse_commits()):
        # only consider unique commits
        if commit.hash in processed_commits:
            continue
        processed_commits.add(commit.hash)

        num_all_commits += 1
        if is_bugfix_message(commit.msg):
            num_fix_commits += 1

        if i % 500 == 0:
            print(f"Processed {i} commits")

        modified_files = commit.modified_files
        if not modified_files:
            continue

        commit_size = len(modified_files)

        added_test_files = []
        added_prod_files = []
        modified_test_files = []
        modified_prod_files = []
        num_sync_pairs = 0
        cur_sync_pairs = []

        for mod in modified_files:

            # only consider Java files
            path = mod.new_path or mod.old_path
            if not path or not path.endswith(".java"):
                continue

            # only consider added or modified files
            if mod.change_type.name != "ADD" and mod.change_type.name != "MODIFY":
                continue

            if is_test_file(path):
                file_type = "test"
                if mod.change_type.name == "ADD":
                    added_test_files.append(path)
                else:
                    modified_test_files.append(path)
            elif is_prod_file(path):
                file_type = "prod"
                if mod.change_type.name == "ADD":
                    added_prod_files.append(path)
                else:
                    modified_prod_files.append(path)
            else:
                continue

            if mod.change_type.name == "ADD":
                rows.append({
                    "commit_index": i,
                    "commit": commit.hash,
                    "date": commit.committer_date,
                    "file_type": file_type,
                    "path": path.replace("\\", "/"),
                    "commit_size": commit_size,
                    "package": extract_package(path)
                })

        # If a production file and the corresponding test file are added in the same commit,
        # though we are unable to confirm TDD adherence as we don't know the order of additions,
        # we could do some heuristic analysis here:

        # e.g.1, to detect TDB(Test Driven Bugfixing) behavior
        # that is, to fix a bug in production code, the developer first adds a test to replicate the bug
        # which could be a sign of TDD adherence
        for prod_path in modified_prod_files:
            prod_name = Path(prod_path).stem
            expected_test_names = {
                f"{prod_name}Test",
                f"{prod_name}Tests",
                f"{prod_name}IT",
                f"{prod_name}IntegrationTest"
            }
            for test_path in modified_test_files:
                test_name = Path(test_path).stem
                if test_name in expected_test_names:
                    num_sync_pairs += 1
                    cur_sync_pairs.append({
                        "prod_path": prod_path,
                        "test_path": test_path
                    })

        if num_sync_pairs > 0:
            if is_bugfix_message(commit.msg):
                num_tdb_commits += 1
                # print(f"Commit {commit.hash} is likely to involve TDB behavior.")
                # print(f"Commit message: {commit.msg}")

# tdb vs non-tdb visualization
non_tdb_all_count = num_all_commits - num_tdb_commits
sizes_all = [num_tdb_commits, non_tdb_all_count]
labels_all = ['TDB Commits', 'Other Commits']
colors_all = ['#ff9999', '#66b3ff'] 

# tdb vs non-tdb fix visualization
non_tdb_fix_count = num_fix_commits - num_tdb_commits
sizes_fix = [num_tdb_commits, non_tdb_fix_count]
labels_fix = ['TDB Commits', 'Other Fix Commits']
colors_fix = ['#ff9999', '#99ff99'] 

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Pie chart for all commits
axes[0].pie(sizes_all, 
            labels=labels_all, 
            autopct='%1.1f%%',
            startangle=140,    
            colors=colors_all, 
            explode=(0.1, 0),  
            shadow=True)
axes[0].set_title(f'TDB Ratio in All Commits\n(Total: {num_all_commits})')

# Pie chart for bug-fix commits
axes[1].pie(sizes_fix, 
            labels=labels_fix, 
            autopct='%1.1f%%', 
            startangle=140, 
            colors=colors_fix, 
            explode=(0.1, 0), 
            shadow=True)
axes[1].set_title(f'TDB Ratio in BugFix Commits\n(Total Fixes: {num_fix_commits})')

# Adjust layout and show plot
plt.tight_layout()
plt.show()

#dataframe setup

df = pd.DataFrame(rows)

if df.empty:
    raise RuntimeError("No Java test/production files detected.")

df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(None)

df["month"] = df["date"].dt.to_period("M")

df.to_csv('driller_output.csv', index=False)

# In order to detect TDD adherence, we calculate the distance between each test file and its production file.
# For instance, if the distance == -1, it means the test file was added one commit before the production file, which is a good sign of TDD adherence.

# split dataframes to production and test files
prod_df = df[df["file_type"] == "prod"].copy()
test_df = df[df["file_type"] == "test"].copy()
# extract the stem for easy matching
prod_df["stem"] = prod_df["path"].apply(lambda p: Path(p).stem)
test_df["stem"] = test_df["path"].apply(lambda p: Path(p).stem)
# build a lookup of test files for quick access
test_lookup = test_df.groupby(["stem", "package"])["commit_index"].min().to_dict()

distances = []
for _, row in prod_df.iterrows():
    prod_stem = row["stem"]
    prod_package = row["package"]
    prod_commit_index = row["commit_index"]
    # derive the expected test stem
    expected_test_stems = [
        f"{prod_stem}Test",
        f"{prod_stem}Tests",
        f"{prod_stem}IT",
        f"{prod_stem}IntegrationTest"
    ]
    # set default test_commit_index as None meaning not found
    test_commit_index = None
    for test_stem in expected_test_stems:
        lookup_key = (test_stem, prod_package)
        if lookup_key in test_lookup:
            test_commit_index = test_lookup[lookup_key]
            break
    if test_commit_index is not None:
        distance = test_commit_index - prod_commit_index
        distances.append(distance)
    else:
        distances.append(None)

# Distribution of Test-Prod-Distance
valid_distances = [d for d in distances if d is not None]
test_first = sum(d < 0 for d in valid_distances)
atomic = sum(d == 0 for d in valid_distances)
test_after = sum(d > 0 for d in valid_distances)
labels = ['Test First (d < 0)', 'Atomic (d = 0)', 'Test After (d > 0)']
counts = [test_first, atomic, test_after]
plt.figure(figsize=(8, 5))
plt.bar(labels, counts)
plt.ylabel('Frequency')
plt.title('Test–Production Commit Ordering')
plt.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.show()

# plt.figure(figsize=(12, 6))
# bins = np.arange(-100, 101, 1)  # from -50 to 50 with a bin width of 1
# # Histogram plotting
# counts, _, patches = plt.hist(valid_distances, bins=bins, color='skyblue', edgecolor='black', alpha=0.7)
# # Highlight the bin where distance == 0
# zero_index = np.searchsorted(bins, 0)
# if 0 <= zero_index < len(patches):
#     patches[zero_index].set_facecolor('crimson')
#     patches[zero_index].set_label('Atomic Commit (Same time)')
# # Add vertical lines and annotations
# plt.axvline(0, color='red', linestyle='--', linewidth=1)
# plt.text(25, plt.ylim()[1]*0.8, 'Test After', fontsize=12, color='green', ha='center')
# plt.text(-25, plt.ylim()[1]*0.8, 'Test First', fontsize=12, color='orange', ha='center')
# plt.title("Distribution of Test-Prod-Distance (Test Index - Prod Index)")
# plt.xlabel("Distance in Commits\n<-- Test First (-ve)  |  Atomic (0)  |  Test After (+ve) -->")
# plt.ylabel("Frequency (Number of Pairs)")
# plt.legend()
# plt.grid(axis='y', alpha=0.3)
# plt.tight_layout()
# plt.show()

# SOME EXPLANATION AND CHALLENGES
# 1. The dominant peak of 'atomic commits' might be due to the use of 'squash and merge' strategy. 
# In this case, even if developers do not follow TDD and simply add test files after production files in separate initial commits,
# the final squashed commit will show both files added simultaneously, leading to a distance of 0.
# 2. The analysis only considers added files. Modifications to existing files are not accounted.
# For instance, if a developer just added a method to an existing test file after adding a method in an existing production file,
# this scenario is not captured in the current distance metric.


# FEATURE 1: Commit activity over time


commits_per_month = (
    df.drop_duplicates("commit")
      .groupby("month")
      .size()
)

plt.figure(figsize=(10, 4))
commits_per_month.index = commits_per_month.index.to_timestamp()
plt.plot(commits_per_month.index, commits_per_month.values)
plt.title("Commit Activity Over Time")
plt.xlabel("Time")
plt.ylabel("Number of Commits")
plt.grid(True)
plt.tight_layout()
plt.show()



# FEATURE 2: Test vs Production file additions over time


adds_per_month = (
    df.groupby(["month", "file_type"])
      .size()
      .unstack(fill_value=0)
)

plt.figure(figsize=(10, 4))
adds_per_month.index = adds_per_month.index.to_timestamp()
plt.plot(adds_per_month.index, adds_per_month["prod"], label="Production files")
plt.plot(adds_per_month.index, adds_per_month["test"], label="Test files")
plt.title("Test vs Production File Additions")
plt.xlabel("Time")
plt.ylabel("Files Added")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()



# FEATURE 3: Commit size vs intent


commit_summary = (
    df.groupby("commit")
      .agg({
          "file_type": lambda x: set(x),
          "commit_size": "first"
      })
)

def classify_commit(types):
    if types == {"test"}:
        return "Test-only"
    if types == {"prod"}:
        return "Prod-only"
    if {"test", "prod"} <= types:
        return "Mixed"
    return "Other"

commit_summary["type"] = commit_summary["file_type"].apply(classify_commit)

commit_summary.boxplot(
    column="commit_size",
    by="type",
    figsize=(8, 4),
    grid=False
)

plt.title("Commit Size by Commit Type")
plt.suptitle("")
plt.xlabel("Commit Type")
plt.ylabel("Files Changed")
plt.tight_layout()
plt.show()
