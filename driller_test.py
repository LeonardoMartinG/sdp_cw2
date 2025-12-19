import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pathlib import Path
from pydriller import Repository


#congif

START_DATE = "2018-01-01"
END_DATE   = "2023-12-31"

#local clone
REPO_PATH = "repos/commons-lang"
# REPO_PATH = "/home/yaoguyuan/Desktop/commons-lang"


#helpers

def is_test_file(path: str) -> bool:
    path = path.replace("\\", "/")
    name = Path(path).stem
    return (
        path.endswith(".java")
        and "src/test" in path
        and name.endswith(("Test", "Tests", "IT", "IntegrationTest"))
    )

# def is_prod_file(path: str) -> bool:
#     path = path.replace("\\", "/")
#     name = Path(path).stem
#     return (
#         path.endswith(".java")
#         and "src/main" in path
#         and not name.endswith(("Test", "Tests", "IT", "IntegrationTest"))
#     )

def is_prod_file(path: str) -> bool:
    path = path.replace("\\", "/")
    name = Path(path).stem
    return (
        path.endswith(".java")
        and ("src/main" in path or "src/java" in path)
        and not name.endswith(("Test", "Tests", "IT", "IntegrationTest"))
    )



#data collection

rows = []

repo = Repository(
    REPO_PATH,
    #since=pd.Timestamp(START_DATE),
    #to=pd.Timestamp(END_DATE),
    only_no_merge=True
)

for i, commit in enumerate(repo.traverse_commits()):
    if i % 500 == 0:
        print(f"Processed {i} commits")

    modified_files = commit.modified_files
    if not modified_files:
        continue

    commit_size = len(modified_files)

    cur_test_files = []
    cur_prod_files = []
    num_tdd_pairs = 0
    cur_tdd_pairs = []

    for mod in modified_files:

        # only consider Java files
        path = mod.new_path or mod.old_path
        if not path or not path.endswith(".java"):
            continue

        # only consider added files
        if mod.change_type.name != "ADD":
            continue

        if is_test_file(path):
            file_type = "test"
            cur_test_files.append(path)
        elif is_prod_file(path):
            file_type = "prod"
            cur_prod_files.append(path)
        else:
            continue

        rows.append({
            "commit_index": i,
            "commit": commit.hash,
            "date": commit.committer_date,
            "file_type": file_type,
            "path": path.replace("\\", "/"),
            "commit_size": commit_size
        })

    # If a production file and the corresponding test file are added in the same commit,
    # We consider this commit to strictly follow the test-first principle.
    for prod_path in cur_prod_files:
        prod_name = Path(prod_path).stem
        expected_test_names = {
            f"{prod_name}Test",
            f"{prod_name}Tests",
            f"{prod_name}IT",
            f"{prod_name}IntegrationTest"
        }
        for test_path in cur_test_files:
            test_name = Path(test_path).stem
            if test_name in expected_test_names:
                num_tdd_pairs += 1
                cur_tdd_pairs.append({
                    "prod_path": prod_path,
                    "test_path": test_path
                })

    if num_tdd_pairs > 0:
        print(f"Commit {commit.hash} has followed TDD with {num_tdd_pairs} pairs:")
        for pair in cur_tdd_pairs:
            print(f"  Prod: {pair['prod_path']}")
            print(f"  Test: {pair['test_path']}")
        print(f"Commit message: {commit.msg}")
        print("")

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
test_lookup = test_df.groupby("stem")["commit_index"].min().to_dict()

distances = []
for _, row in prod_df.iterrows():
    prod_stem = row["stem"]
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
        if test_stem in test_lookup:
            test_commit_index = test_lookup[test_stem]
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
