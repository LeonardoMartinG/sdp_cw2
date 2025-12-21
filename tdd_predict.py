import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pathlib import Path
from pydriller import Repository

# config

# use a local clone for speed and stability
REPO_PATH = r"repos/commons-lang"

# optional date filters
START_DATE = None
END_DATE = None

# commit-size threshold
SMALL_COMMIT_MAX_FILES = 8

# keywords that indicate non-atomic commits
SUSPECT_MSG_PATTERNS = [
    "merge", "pull request", "squash",
    "refactor", "release", "cleanup",
    "bump", "dependency"
]

# helpers

TEST_SUFFIXES = ("Test", "Tests", "IT", "IntegrationTest")

def norm_path(p: str) -> str:
    return p.replace("\\", "/")

def is_java_file(path: str) -> bool:
    return path is not None and path.endswith(".java")

def is_test_file(path: str) -> bool:
    p = norm_path(path)
    name = Path(p).stem
    return (
        is_java_file(p)
        and "src/test" in p
        and name.endswith(TEST_SUFFIXES)
    )

def is_prod_file(path: str) -> bool:
    p = norm_path(path)
    name = Path(p).stem
    return (
        is_java_file(p)
        and ("src/main" in p or "src/java" in p)
        and not name.endswith(TEST_SUFFIXES)
    )

def base_from_test_stem(test_stem: str):
    for suf in TEST_SUFFIXES:
        if test_stem.endswith(suf) and len(test_stem) > len(suf):
            return test_stem[:-len(suf)]
    return None

def is_suspect_message(msg: str) -> bool:
    m = msg.lower()
    return any(k in m for k in SUSPECT_MSG_PATTERNS)

def java_package(path: str) -> str:
    p = norm_path(path)
    if "src/main/java/" in p:
        return p.split("src/main/java/")[1].rsplit("/", 1)[0]
    if "src/test/java/" in p:
        return p.split("src/test/java/")[1].rsplit("/", 1)[0]
    return ""

# file introduction events

rows = []
commit_rows = []

repo = Repository(
    REPO_PATH,
    only_no_merge=True
)

for commit in repo.traverse_commits():

    if START_DATE and commit.committer_date < pd.Timestamp(START_DATE, tz="UTC"):
        continue
    if END_DATE and commit.committer_date > pd.Timestamp(END_DATE, tz="UTC"):
        continue

    modified_files = commit.modified_files
    if not modified_files:
        continue

    commit_rows.append({
        "commit": commit.hash,
        "date": commit.committer_date,
        "commit_size": len(modified_files),
        "msg": commit.msg
    })

    for mod in modified_files:

        if mod.change_type.name != "ADD":
            continue

        path = mod.new_path or mod.old_path
        if not is_java_file(path):
            continue

        p = norm_path(path)

        if is_test_file(p):
            file_type = "test"
        elif is_prod_file(p):
            file_type = "prod"
        else:
            continue

        rows.append({
            "commit": commit.hash,
            "date": commit.committer_date,
            "file_type": file_type,
            "path": p,
            "stem": Path(p).stem,
            "package": java_package(p)
        })

df = pd.DataFrame(rows)
commits_df = pd.DataFrame(commit_rows)

if df.empty or commits_df.empty:
    raise RuntimeError("no java production/test add events found")

# chronological commit indices

df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(None)
commits_df["date"] = pd.to_datetime(commits_df["date"], utc=True).dt.tz_convert(None)

commits_df = commits_df.sort_values("date").drop_duplicates("commit")
commits_df["commit_index"] = range(len(commits_df))

df = df.merge(
    commits_df[["commit", "commit_index", "commit_size", "msg"]],
    on="commit",
    how="left"
)

df["month"] = df["date"].dt.to_period("M")

# match test and production introductions

prod_df = df[df["file_type"] == "prod"].copy()
test_df = df[df["file_type"] == "test"].copy()

test_df["base"] = test_df["stem"].apply(base_from_test_stem)
test_df = test_df.dropna(subset=["base"])

first_test = (
    test_df.sort_values("commit_index")
           .groupby("base")
           .first()
           .reset_index()
           .rename(columns={"commit_index": "test_index"})
)

first_prod = (
    prod_df.sort_values("commit_index")
           .groupby("stem")
           .first()
           .reset_index()
           .rename(columns={"commit_index": "prod_index"})
)

pairs = first_prod.merge(
    first_test,
    left_on="stem",
    right_on="base",
    how="left",
    suffixes=("_prod", "_test")
)

pairs["distance"] = pairs["test_index"] - pairs["prod_index"]

def classify_pair(row):
    if pd.isna(row["distance"]):
        return "no_test"
    if row["distance"] < 0:
        return "test_first"
    if row["distance"] == 0:
        return "same_commit"
    return "test_after"

pairs["category"] = pairs.apply(classify_pair, axis=1)

# atomic same-commit detection

pairs["small_commit"] = pairs["commit_size_prod"] <= SMALL_COMMIT_MAX_FILES
pairs["clean_msg"] = ~pairs["msg_prod"].apply(is_suspect_message)
pairs["same_package"] = pairs["package_prod"] == pairs["package_test"]

pairs["atomic_like"] = (
    (pairs["category"] == "same_commit")
    & pairs["small_commit"]
    & pairs["clean_msg"]
    & pairs["same_package"]
)

# tdd metrics and score

valid_pairs = pairs[pairs["category"] != "no_test"]

test_presence_rate = (pairs["category"] != "no_test").mean()
test_first_rate = (valid_pairs["category"] == "test_first").mean()
same_commit_atomic_rate = pairs["atomic_like"].mean()

tdd_score = (
    0.60 * test_first_rate +
    0.25 * same_commit_atomic_rate +
    0.15 * test_presence_rate
)

tdd_score = float(max(0.0, min(1.0, tdd_score)))

print("\nTDD summary")
print(f"production classes introduced: {len(first_prod)}")
print(f"test presence rate:            {test_presence_rate:.3f}")
print(f"test-first rate:               {test_first_rate:.3f}")
print(f"atomic same-commit rate:       {same_commit_atomic_rate:.3f}")
print(f"estimated tdd adoption chance: {tdd_score:.3f}\n")

# save outputs

df.to_csv("driller_file_add_events.csv", index=False)
pairs.to_csv("driller_prod_test_pairs_scored.csv", index=False)

# plots

labels = ["test-first", "same-commit (atomic)", "test-after"]
counts = [
    (pairs["category"] == "test_first").sum(),
    pairs["atomic_like"].sum(),
    (pairs["category"] == "test_after").sum()
]

plt.figure(figsize=(8, 5))
plt.bar(labels, counts)
plt.title("test–production introduction ordering")
plt.ylabel("number of prod–test pairs")
plt.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.show()
