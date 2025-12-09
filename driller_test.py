import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path
from pydriller import Repository


#congif

START_DATE = "2018-01-01"
END_DATE   = "2023-12-31"

#local clone
REPO_PATH = "C:/git/cloudstack"


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

    for mod in modified_files:
        path = mod.new_path or mod.old_path
        if not path or not path.endswith(".java"):
            continue

        if is_test_file(path):
            file_type = "test"
        elif is_prod_file(path):
            file_type = "prod"
        else:
            continue

        rows.append({
            "commit": commit.hash,
            "date": commit.committer_date,
            "file_type": file_type,
            "path": path.replace("\\", "/"),
            "commit_size": commit_size
        })


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
