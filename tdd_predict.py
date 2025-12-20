import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pathlib import Path
from pydriller import Repository

#config
# Use a LOCAL clone for speed & stability (recommended for Windows)
REPO_PATH = r"repos/commons-lang"   

# Optional (leave None to use full history)
START_DATE = None  # "yyyy-mm-dd"
END_DATE   = None  

# Commit-size threshold: large commits weaken “same-commit implies TDD”
SMALL_COMMIT_MAX_FILES = 8

#helpers

TEST_SUFFIXES = ("Test", "Tests", "IT", "IntegrationTest")

def norm_path(p: str) -> str:
    return p.replace("\\", "/")

def is_java_file(path: str) -> bool:
    return path is not None and path.endswith(".java")

def is_test_file(path: str) -> bool:
    p = norm_path(path)
    name = Path(p).stem
    return (is_java_file(p) and ("src/test" in p) and name.endswith(TEST_SUFFIXES))

def is_prod_file(path: str) -> bool:
    p = norm_path(path)
    name = Path(p).stem
    # commons-lang contains both Maven layout and older layouts in history
    return (is_java_file(p) and (("src/main" in p) or ("src/java" in p)) and (not name.endswith(TEST_SUFFIXES)))

def base_from_test_stem(test_stem: str) -> str | None:
    """FooTest -> Foo ; FooIT -> Foo ; FooIntegrationTest -> Foo"""
    for suf in TEST_SUFFIXES:
        if test_stem.endswith(suf) and len(test_stem) > len(suf):
            return test_stem[: -len(suf)]
    return None

#1-File intro events

rows = []
commit_rows = []  # commit-level metadata

repo = Repository(
    REPO_PATH,
    only_no_merge=True
)

# NOTE: traverse_commits order is not guaranteed chronological;
# we will rebuild a chronological order later.
for commit in repo.traverse_commits():
    if START_DATE and commit.committer_date < pd.Timestamp(START_DATE, tz="UTC"):
        continue
    if END_DATE and commit.committer_date > pd.Timestamp(END_DATE, tz="UTC"):
        continue

    modified_files = commit.modified_files
    if not modified_files:
        continue

    commit_size = len(modified_files)

    commit_rows.append({
        "commit": commit.hash,
        "date": commit.committer_date,
        "commit_size": commit_size,
        "msg": commit.msg
    })

    for mod in modified_files:
        # Only added files are used for “new class introduced” analysis
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
            "stem": Path(p).stem
        })

df = pd.DataFrame(rows)
commits_df = pd.DataFrame(commit_rows)

if df.empty or commits_df.empty:
    raise RuntimeError("No Java production/test ADD events found. Check repo path and filters.")

# Normalize datetime (tz-aware -> UTC -> naive)
df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(None)
commits_df["date"] = pd.to_datetime(commits_df["date"], utc=True).dt.tz_convert(None)

#2-Chronological commit indices
# Sort commits oldest -> newest and assign indices
commits_df = commits_df.sort_values("date", ascending=True).drop_duplicates("commit")
commits_df["commit_index"] = range(len(commits_df))

# Attach chronological index + commit_size to file events
df = df.merge(commits_df[["commit", "commit_index", "commit_size"]], on="commit", how="left")
df["month"] = df["date"].dt.to_period("M")

# Match test↔prod introductions
# We match by base class name: Foo.java ↔ FooTest.java, FooIT.java, etc.

prod_df = df[df["file_type"] == "prod"].copy()
test_df = df[df["file_type"] == "test"].copy()

# Map tests to their base production name
test_df["base"] = test_df["stem"].apply(base_from_test_stem)
test_df = test_df.dropna(subset=["base"])

# For each base, record earliest test commit index
first_test_idx = test_df.groupby("base")["commit_index"].min().to_dict()

# For each prod stem, record earliest prod commit index + commit_size at creation
first_prod = (
    prod_df.sort_values("commit_index")
           .groupby("stem")
           .first()[["commit_index", "commit_size"]]
           .rename(columns={"commit_index": "prod_index", "commit_size": "prod_commit_size"})
           .reset_index()
)

# Determine ordering category for each prod class that has a matching test
def classify_pair(prod_stem: str, prod_index: int):
    t_idx = first_test_idx.get(prod_stem)
    if t_idx is None:
        return None, None
    dist = t_idx - prod_index
    if dist < 0:
        return "test_first", dist
    elif dist == 0:
        # IMPORTANT: this is NOT "test-first"
        return "same_commit", dist
    else:
        return "test_after", dist

cats = []
dists = []
for _, r in first_prod.iterrows():
    c, d = classify_pair(r["stem"], int(r["prod_index"]))
    cats.append(c)
    dists.append(d)

first_prod["category"] = cats
first_prod["distance"] = dists
paired = first_prod.dropna(subset=["category"]).copy()

# Also compute “has any test at all” for prod classes
first_prod["has_test"] = first_prod["stem"].isin(first_test_idx.keys())

#Compute TDD score & stats

if len(first_prod) == 0:
    raise RuntimeError("No production class introductions detected under current filters.")

n_prod = len(first_prod)
test_presence_rate = first_prod["has_test"].mean()  # fraction of prod classes with a matching test ever

if len(paired) == 0:
    # No matches found => very low evidence of TDD
    test_first_rate = 0.0
    same_commit_rate = 0.0
    test_after_rate = 0.0
else:
    test_first_rate = (paired["category"] == "test_first").mean()
    same_commit_rate = (paired["category"] == "same_commit").mean()
    test_after_rate = (paired["category"] == "test_after").mean()

# Commit-size weighting: same_commit in small commits is more credible
# (Large commits are more likely refactors / squash merges / batching)
same_commit_small = paired[
    (paired["category"] == "same_commit") & (paired["prod_commit_size"] <= SMALL_COMMIT_MAX_FILES)
]
same_commit_small_rate = len(same_commit_small) / len(paired) if len(paired) else 0.0

# A simple, defensible scoring model (0..1):
# - test_first is strongest evidence
# - same_commit_small is moderate evidence
# - test_presence is weak evidence
# - penalty for big commits reduces confidence in same-commit signals
#
# This is a heuristic model and can be adjusted based on empirical validation.
tdd_score = (
    0.55 * test_first_rate +
    0.25 * same_commit_small_rate +
    0.20 * test_presence_rate
)

# Clamp to [0,1]
tdd_score = float(max(0.0, min(1.0, tdd_score)))

print("\n========== TDD SUMMARY ==========")
print(f"Production classes introduced: {n_prod}")
print(f"Matched prod↔test pairs:       {len(paired)}")
print(f"Test presence rate:           {test_presence_rate:.3f}")
print(f"Test-first rate:              {test_first_rate:.3f}")
print(f"Same-commit rate:             {same_commit_rate:.3f}")
print(f"Same-commit (small commits):  {same_commit_small_rate:.3f} (<= {SMALL_COMMIT_MAX_FILES} files)")
print(f"Test-after rate:              {test_after_rate:.3f}")
print(f"\nEstimated TDD adoption chance (0..1): {tdd_score:.3f}")
print("Interpretation: ~0.0 = little evidence, ~1.0 = strong evidence.\n")

# Save raw data for your report appendix / reproducibility
df.to_csv("driller_file_add_events.csv", index=False)
first_prod.to_csv("driller_prod_class_pairs.csv", index=False)

#5 - Plots  

#  Plot A: Test–Production ordering (correct labels)
labels = ["Test-first", "Same-commit", "Test-after"]
counts = [
    int((paired["category"] == "test_first").sum()),
    int((paired["category"] == "same_commit").sum()),
    int((paired["category"] == "test_after").sum()),
]
plt.figure(figsize=(8, 5))
plt.bar(labels, counts)
plt.ylabel("Number of matched prod↔test pairs")
plt.title("Test–Production Introduction Ordering (Class-level)")
plt.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.show()

#  Plot B: Distance distribution (optional, more detail)
if len(paired):
    plt.figure(figsize=(10, 5))
    plt.hist(paired["distance"], bins=40, edgecolor="black")
    plt.axvline(0, linestyle="--")
    plt.title("Distribution of Commit Distance (test_index - prod_index)")
    plt.xlabel("Distance in commits (negative = test-first, 0 = same-commit, positive = test-after)")
    plt.ylabel("Number of pairs")
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.show()

#  Plot C: Commit activity over time 
commits_per_month = commits_df.copy()
commits_per_month["month"] = commits_per_month["date"].dt.to_period("M")
monthly_counts = commits_per_month.groupby("month").size().sort_index()

plt.figure(figsize=(10, 4))
monthly_counts.index = monthly_counts.index.to_timestamp()
plt.plot(monthly_counts.index, monthly_counts.values)
plt.title("Commit Activity Over Time")
plt.xlabel("Time")
plt.ylabel("Number of commits")
plt.grid(True)
plt.tight_layout()
plt.show()

# Plot D: Test vs Prod file additions over time
adds_per_month = df.groupby(["month", "file_type"]).size().unstack(fill_value=0)

plt.figure(figsize=(10, 4))
adds_per_month.index = adds_per_month.index.to_timestamp()
plt.plot(adds_per_month.index, adds_per_month.get("prod", 0), label="Production files added")
plt.plot(adds_per_month.index, adds_per_month.get("test", 0), label="Test files added")
plt.title("Test vs Production File Additions Over Time")
plt.xlabel("Time")
plt.ylabel("Files added")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# Plot E: Commit size vs commit type (prod-only, test-only, mixed)
commit_types = df.groupby("commit")["file_type"].apply(lambda x: set(x)).to_frame("types")
commit_types = commit_types.merge(commits_df[["commit", "commit_size"]], left_index=True, right_on="commit", how="left")

def classify_commit(types: set[str]) -> str:
    if types == {"test"}:
        return "Test-only"
    if types == {"prod"}:
        return "Prod-only"
    if "test" in types and "prod" in types:
        return "Mixed"
    return "Other"

commit_types["commit_type"] = commit_types["types"].apply(classify_commit)

commit_types.boxplot(column="commit_size", by="commit_type", figsize=(8, 4), grid=False)
plt.title("Commit Size by Commit Type")
plt.suptitle("")
plt.xlabel("Commit type (based on Java file adds)")
plt.ylabel("Files changed in commit")
plt.tight_layout()
plt.show()
