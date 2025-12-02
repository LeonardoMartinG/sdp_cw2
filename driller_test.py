import matplotlib.pyplot as plt
import pandas as pd
from pydriller import Repository

# 1. Collect commit data from the repo

repo_url = "https://github.com/apache/superset.git"#testing on the apache project repo

data = []
for commit in Repository(repo_url).traverse_commits():
    data.append({
        "date": commit.committer_date,             # already tz-aware datetime
        "n_files": len(commit.modified_files),     # number of files changed in this commit
    })

df = pd.DataFrame(data)

# Ensure datetime is timezone-aware in UTC, then make it naive (no tz)
df["date"] = pd.to_datetime(df["date"], utc=True)
df["date"] = df["date"].dt.tz_convert(None)

# Create a month column for grouping
df["month"] = df["date"].dt.to_period("M")

# 2. Commits over time (per month)

monthly_counts = (
    df.groupby("month")
      .size()
      .sort_index()
)

plt.figure(figsize=(10, 4))
monthly_counts.index = monthly_counts.index.to_timestamp()
plt.plot(monthly_counts.index, monthly_counts.values)
plt.title("Commits Over Time (per Month)")
plt.xlabel("Month")
plt.ylabel("Number of Commits")
plt.grid(True)
plt.tight_layout()
plt.show()

# 3. Distribution of commit sizes (files changed per commit)

plt.figure(figsize=(8, 4))
plt.hist(df["n_files"], bins=20, edgecolor="black")
plt.title("Distribution of Commit Sizes")
plt.xlabel("Number of Files Modified in Commit")
plt.ylabel("Number of Commits")
plt.tight_layout()
plt.show()
