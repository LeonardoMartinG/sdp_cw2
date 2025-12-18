import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
from pydriller import Repository


#congif

START_DATE = "2018-01-01"
END_DATE   = "2023-12-31"

#local clone
# REPO_PATH = "/path/to/your/local/clone/of/commons-lang"
REPO_PATH = "/home/yaoguyuan/Desktop/commons-lang"


#helpers

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
        and "src/main" in path
        and not name.endswith(("Test", "Tests", "IT", "IntegrationTest"))
    )


#data collection

rows = []

repo = Repository(
    REPO_PATH,
    since=pd.Timestamp(START_DATE),
    to=pd.Timestamp(END_DATE),
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
        print("")

#dataframe setup

df = pd.DataFrame(rows)

if df.empty:
    raise RuntimeError("No Java test/production files detected.")

df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(None)

df["month"] = df["date"].dt.to_period("M")



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
