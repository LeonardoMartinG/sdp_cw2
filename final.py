import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pathlib import Path
from pydriller import Repository

#config
# Use a LOCAL clone for speed & stability (recommended for Windows)
REPO_PATH = r"repos/commons-lang"

# Optional date filters (None = full history)
START_DATE = None  # "yyyy-mm-dd"
END_DATE = None

# Commit-size threshold: large commits weaken “same-commit implies TDD”
SMALL_COMMIT_MAX_FILES = 8

# “Atomic-like” extra filters (per-file change size thresholds)
MAX_PROD_CHANGE_LINES = 300
MAX_TEST_CHANGE_LINES = 400

# keywords that indicate non-atomic / potentially batched commits
SUSPECT_MSG_PATTERNS = [
    "merge", "pull request", "squash",
    "refactor", "release", "cleanup",
    "bump", "dependency"
]

#helpers
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
    m = (msg or "").lower()
    return any(k in m for k in SUSPECT_MSG_PATTERNS)

def extract_package(path: str) -> str:
    p = norm_path(path)
    if "src/main/java/" in p:
        return p.split("src/main/java/")[1].rsplit("/", 1)[0]
    if "src/test/java/" in p:
        return p.split("src/test/java/")[1].rsplit("/", 1)[0]
    if "src/java/" in p:
        return p.split("src/java/")[1].rsplit("/", 1)[0]
    if "src/test/" in p:
        return p.split("src/test/")[1].rsplit("/", 1)[0]
    return ""

def safe_added_deleted(mod) -> tuple[int, int]:
    try:
        return int(mod.added_lines or 0), int(mod.deleted_lines or 0)
    except Exception:
        return 0, 0

def looks_like_test_source(source_code: str) -> bool:
    if not source_code:
        return False
    s = source_code.lower()
    return (
        "@test" in s
        or "assert" in s
        or "org.junit" in s
        or "org.testng" in s
        or "hamcrest" in s
    )

def looks_like_prod_class(source_code: str, class_name: str) -> bool:
    if not source_code or not class_name:
        return False
    return f"class {class_name}" in source_code or f"interface {class_name}" in source_code

#file introduction events
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

        added, deleted = safe_added_deleted(mod)

        rows.append({
            "commit": commit.hash,
            "date": commit.committer_date,
            "file_type": file_type,
            "path": p,
            "stem": Path(p).stem,
            "package": extract_package(p),
            "added_lines": added,
            "deleted_lines": deleted,
        })

df = pd.DataFrame(rows)
commits_df = pd.DataFrame(commit_rows)

if df.empty or commits_df.empty:
    raise RuntimeError("no java production/test add events found")

#chronological commit indices
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

#match test and production introductions
prod_df = df[df["file_type"] == "prod"].copy()
test_df = df[df["file_type"] == "test"].copy()

test_df["base"] = test_df["stem"].apply(base_from_test_stem)
test_df = test_df.dropna(subset=["base"])

first_test = (
    test_df.sort_values("commit_index")
           .groupby(["base", "package"])
           .first()
           .reset_index()
           .rename(columns={"commit_index": "test_index"})
)

first_prod = (
    prod_df.sort_values("commit_index")
           .groupby(["stem", "package"])
           .first()
           .reset_index()
           .rename(columns={"commit_index": "prod_index"})
)

pairs = first_prod.merge(
    first_test,
    left_on=["stem", "package"],
    right_on=["base", "package"],
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

#atomic same-commit detection
pairs["small_commit"] = pairs["commit_size_prod"] <= SMALL_COMMIT_MAX_FILES
pairs["clean_msg"] = ~pairs["msg_prod"].apply(is_suspect_message)
pairs["same_package"] = pairs["package"] == pairs["package"]  # always True after merge-by-package, kept for clarity

prod_change = pairs["added_lines_prod"].fillna(0) + pairs["deleted_lines_prod"].fillna(0)
test_change = pairs["added_lines_test"].fillna(0) + pairs["deleted_lines_test"].fillna(0)
pairs["small_file_changes"] = (prod_change <= MAX_PROD_CHANGE_LINES) & (test_change <= MAX_TEST_CHANGE_LINES)

pairs["atomic_like"] = (
    (pairs["category"] == "same_commit")
    & pairs["small_commit"]
    & pairs["clean_msg"]
    & pairs["small_file_changes"]
)

#tdd metrics and score
valid_pairs = pairs[pairs["category"] != "no_test"]

test_presence_rate = (pairs["category"] != "no_test").mean() if len(pairs) else 0.0
test_first_rate = (valid_pairs["category"] == "test_first").mean() if len(valid_pairs) else 0.0
same_commit_atomic_rate = pairs["atomic_like"].mean() if len(pairs) else 0.0

# scoring model (0..1)
# - test-first is strongest evidence
# - atomic-like same-commit is weaker evidence
# - test presence is weakest evidence
tdd_score = (
    0.70 * test_first_rate +
    0.15 * same_commit_atomic_rate +
    0.15 * test_presence_rate
)
tdd_score = float(max(0.0, min(1.0, tdd_score)))

print("\nTDD summary")
print(f"production classes introduced: {len(first_prod)}")
print(f"test presence rate:            {test_presence_rate:.3f}")
print(f"test-first rate:               {test_first_rate:.3f}")
print(f"atomic same-commit rate:       {same_commit_atomic_rate:.3f}")
print(f"estimated tdd adoption chance: {tdd_score:.3f}\n")

#save outputs
df.to_csv("driller_file_add_events.csv", index=False)
pairs.to_csv("driller_prod_test_pairs_scored.csv", index=False)

#plots
labels = ["test-first", "same-commit (atomic-like)", "test-after"]
counts = [
    int((pairs["category"] == "test_first").sum()),
    int(pairs["atomic_like"].sum()),
    int((pairs["category"] == "test_after").sum()),
]

plt.figure(figsize=(8, 5))
plt.bar(labels, counts)
plt.title("test–production introduction ordering")
plt.ylabel("number of prod–test pairs")
plt.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.show()

#distance distribution
valid_d = pairs[pairs["category"] != "no_test"]["distance"].dropna()
if len(valid_d):
    plt.figure(figsize=(10, 5))
    plt.hist(valid_d, bins=40, edgecolor="black")
    plt.axvline(0, linestyle="--")
    plt.title("distribution of commit distance (test_index - prod_index)")
    plt.xlabel("distance in commits (negative=test-first, 0=same-commit, positive=test-after)")
    plt.ylabel("number of pairs")
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.show()

#commit activity over time
commits_per_month = commits_df.copy()
commits_per_month["month"] = commits_per_month["date"].dt.to_period("M")
monthly_counts = commits_per_month.groupby("month").size().sort_index()

plt.figure(figsize=(10, 4))
monthly_counts.index = monthly_counts.index.to_timestamp()
plt.plot(monthly_counts.index, monthly_counts.values)
plt.title("commit activity over time")
plt.xlabel("time")
plt.ylabel("number of commits")
plt.grid(True)
plt.tight_layout()
plt.show()

#test vs prod file adds over time
adds_per_month = df.groupby(["month", "file_type"]).size().unstack(fill_value=0)

plt.figure(figsize=(10, 4))
adds_per_month.index = adds_per_month.index.to_timestamp()
plt.plot(adds_per_month.index, adds_per_month.get("prod", 0), label="production files added")
plt.plot(adds_per_month.index, adds_per_month.get("test", 0), label="test files added")
plt.title("test vs production file additions over time")
plt.xlabel("time")
plt.ylabel("files added")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

#commit size vs commit type (based on java file adds)
commit_types = df.groupby("commit")["file_type"].apply(lambda x: set(x)).to_frame("types")
commit_types = commit_types.merge(commits_df[["commit", "commit_size"]], left_index=True, right_on="commit", how="left")

def classify_commit(types: set[str]) -> str:
    if types == {"test"}:
        return "test-only"
    if types == {"prod"}:
        return "prod-only"
    if "test" in types and "prod" in types:
        return "mixed"
    return "other"

commit_types["commit_type"] = commit_types["types"].apply(classify_commit)

commit_types.boxplot(column="commit_size", by="commit_type", figsize=(8, 4), grid=False)
plt.title("commit size by commit type")
plt.suptitle("")
plt.xlabel("commit type (based on java file adds)")
plt.ylabel("files changed in commit")
plt.tight_layout()
plt.show()
