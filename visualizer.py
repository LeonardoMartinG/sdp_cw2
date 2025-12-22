import matplotlib.pyplot as plt

class Visualizer:
    @staticmethod
    def plot_tdb_pie_charts(stats):
        """
        Pie charts for TDB ratios in all commits and bugfix commits.
        """
        num_all = stats["all_commits"]
        num_tdb = stats["tdb_commits"]
        num_fix = stats["fix_commits"]
        
        sizes_all = [num_tdb, num_all - num_tdb]
        sizes_fix = [num_tdb, num_fix - num_tdb]
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        
        # 1. All Commits
        axes[0].pie(sizes_all, labels=['TDB Commits', 'Other Commits'], 
                    autopct='%1.1f%%', startangle=140, colors=['#ff9999', '#66b3ff'], explode=(0.1, 0), shadow=True)
        axes[0].set_title(f'TDB Ratio in All Commits\n(Total: {num_all})')

        # 2. BugFix Commits
        axes[1].pie(sizes_fix, labels=['TDB Commits', 'Other Fix Commits'], 
                    autopct='%1.1f%%', startangle=140, colors=['#ff9999', '#99ff99'], explode=(0.1, 0), shadow=True)
        axes[1].set_title(f'TDB Ratio in BugFix Commits\n(Total Fixes: {num_fix})')
        
        plt.tight_layout()
        plt.show()

    @staticmethod
    def plot_tdd_distance_bar(distances):
        """
        Bar chart for Prod-Test order distribution based on distances.
        """
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

    @staticmethod
    def plot_cumulative_loc(df):
        """
        Plot cumulative added lines of code (LOC) over time for Production and Test files.
        """
        df = df.sort_values("date")
        
        prod_df = df[df["file_type"] == "prod"].copy()
        test_df = df[df["file_type"] == "test"].copy()
        
        prod_df["cum_loc"] = prod_df["added_lines"].cumsum()
        test_df["cum_loc"] = test_df["added_lines"].cumsum()
        
        plt.figure(figsize=(10, 6))
        
        plt.plot(prod_df["date"], prod_df["cum_loc"], 
                 label="Production LOC", color="#1f77b4", linewidth=2)
                 
        plt.plot(test_df["date"], test_df["cum_loc"], 
                 label="Test LOC", color="#ff7f0e", linewidth=2, linestyle="--")
        
        plt.title("Evolution of Code Scale: Production vs Test")
        plt.xlabel("Time")
        plt.ylabel("Cumulative Added Lines of Code (LOC)")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    @staticmethod
    def plot_trends(df):
        """
        Plot trends over time:
        1. Commit Activity Over Time
        2. Production vs Test File Additions Over Time
        """
        # Feature 1: Commit Activity
        commits_per_month = df.drop_duplicates("commit").groupby("month").size()
        plt.figure(figsize=(10, 4))
        commits_per_month.index = commits_per_month.index.to_timestamp()
        plt.plot(commits_per_month.index, commits_per_month.values)
        plt.title("Commit Activity Over Time")
        plt.grid(True)
        plt.tight_layout()
        plt.show()

        # Feature 2: Prod vs Test Adds
        adds_per_month = df.groupby(["month", "file_type"]).size().unstack(fill_value=0)
        plt.figure(figsize=(10, 4))
        adds_per_month.index = adds_per_month.index.to_timestamp()
        plt.plot(adds_per_month.index, adds_per_month["prod"], label="Production files")
        plt.plot(adds_per_month.index, adds_per_month["test"], label="Test files")
        plt.title("Test vs Production File Additions")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    @staticmethod
    def plot_commit_size_boxplot(df):
        """
        Boxplot of commit sizes categorized by commit types.
        """
        commit_summary = df.groupby("commit").agg({
            "file_type": lambda x: set(x),
            "commit_size": "first"
        })
        
        def classify(types):
            if types == {"test"}: return "Test-only"
            if types == {"prod"}: return "Prod-only"
            if {"test", "prod"} <= types: return "Mixed"
            return "Other"

        commit_summary["type"] = commit_summary["file_type"].apply(classify)
        commit_summary.boxplot(column="commit_size", by="type", figsize=(8, 4), grid=False)
        plt.title("Commit Size by Commit Type")
        plt.suptitle("")
        plt.ylabel("Files Changed")
        plt.tight_layout()
        plt.show()