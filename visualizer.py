import matplotlib.pyplot as plt

class Visualizer:
    @staticmethod
    def plot_tdb_pie_charts(stats):
        num_all = stats["all_commits"]
        num_tdb = stats["tdb_commits"]
        num_fix = stats["fix_commits"]

        sizes_all = [num_tdb, max(0, num_all - num_tdb)]
        sizes_fix = [num_tdb, max(0, num_fix - num_tdb)]

        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        axes[0].pie(sizes_all, labels=["TDB Commits", "Other Commits"], autopct="%1.1f%%", startangle=140, explode=(0.1, 0), shadow=True)
        axes[0].set_title(f"TDB Ratio in All Commits\n(Total: {num_all})")

        axes[1].pie(sizes_fix, labels=["TDB Commits", "Other Fix Commits"], autopct="%1.1f%%", startangle=140, explode=(0.1, 0), shadow=True)
        axes[1].set_title(f"TDB Ratio in BugFix Commits\n(Total Fixes: {num_fix})")

        plt.tight_layout()
        plt.show()

    @staticmethod
    def plot_tdd_distance_bar(distances):
        valid = [d for d in distances if d is not None]
        test_first = sum(d < 0 for d in valid)
        same_commit = sum(d == 0 for d in valid)
        test_after = sum(d > 0 for d in valid)

        labels = ["Test First (d<0)", "Same Commit (d=0)", "Test After (d>0)"]
        counts = [test_first, same_commit, test_after]

        plt.figure(figsize=(8, 5))
        plt.bar(labels, counts)
        plt.ylabel("Frequency")
        plt.title("Test–Production Ordering (Distance)")
        plt.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        plt.show()

    @staticmethod
    def plot_cumulative_loc(df):
        df = df.sort_values("date")

        prod = df[df["file_type"] == "prod"].copy()
        test = df[df["file_type"] == "test"].copy()

        prod["cum_loc"] = prod["added_lines"].cumsum()
        test["cum_loc"] = test["added_lines"].cumsum()

        plt.figure(figsize=(10, 6))
        plt.plot(prod["date"], prod["cum_loc"], label="Production LOC", linewidth=2)
        plt.plot(test["date"], test["cum_loc"], label="Test LOC", linewidth=2, linestyle="--")

        plt.title("Evolution of Code Scale: Production vs Test")
        plt.xlabel("Time")
        plt.ylabel("Cumulative Added LOC")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    @staticmethod
    def plot_trends(df):
        commits_per_month = df.drop_duplicates("commit").groupby("month").size()
        plt.figure(figsize=(10, 4))
        commits_per_month.index = commits_per_month.index.to_timestamp()
        plt.plot(commits_per_month.index, commits_per_month.values)
        plt.title("Commit Activity Over Time")
        plt.grid(True)
        plt.tight_layout()
        plt.show()

        adds_per_month = df.groupby(["month", "file_type"]).size().unstack(fill_value=0)
        plt.figure(figsize=(10, 4))
        adds_per_month.index = adds_per_month.index.to_timestamp()
        plt.plot(adds_per_month.index, adds_per_month.get("prod", 0), label="Production events")
        plt.plot(adds_per_month.index, adds_per_month.get("test", 0), label="Test events")
        plt.title("Test vs Production Events Over Time")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    @staticmethod
    def plot_commit_size_boxplot(df):
        commit_summary = df.groupby("commit").agg({"file_type": lambda x: set(x), "commit_size": "first"})

        def classify(types):
            if types == {"test"}:
                return "Test-only"
            if types == {"prod"}:
                return "Prod-only"
            if "test" in types and "prod" in types:
                return "Mixed"
            return "Other"

        commit_summary["type"] = commit_summary["file_type"].apply(classify)
        commit_summary.boxplot(column="commit_size", by="type", figsize=(8, 4), grid=False)
        plt.title("Commit Size by Commit Type")
        plt.suptitle("")
        plt.ylabel("Files Changed")
        plt.tight_layout()
        plt.show()
