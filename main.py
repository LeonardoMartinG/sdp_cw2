# main.py
import pandas as pd
from config import Config
from miner import mine_repository
from analyzer import Analyzer
from visualizer import Visualizer

def main():
    # 1. Mine data from the repository
    df, stats = mine_repository(Config.REPO_PATH, Config.MODE)    
    if df.empty:
        raise RuntimeError("No Java test/production files detected.")
    
    # Data preprocessing
    # ==============================================================================
    # FIX: Global Sorting and Re-indexing
    # ==============================================================================
    
    # global sort by date
    df = df.sort_values("date").reset_index(drop=True)
    
    # create unique commit list with new index
    unique_commits = df[["commit", "date"]].drop_duplicates("commit").sort_values("date").reset_index(drop=True)
    unique_commits["new_index"] = unique_commits.index
    
    # drop old commit_index
    df = df.drop(columns=["commit_index"])
    # merge to get new commit_index
    df = df.merge(unique_commits[["commit", "new_index"]], on="commit", how="left")
    # rename column
    df = df.rename(columns={"new_index": "commit_index"})
    # ==============================================================================

    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(None)
    df["month"] = df["date"].dt.to_period("M")   
    # Export CSV
    df.to_csv(Config.OUTPUT_CSV, index=False)
    
    # 2. Calculate Prod-Test distances
    distances = Analyzer.calculate_distances(df)
    
    # 3. Plot TDB pie charts and Prod-Test order bar chart and other trends
    Visualizer.plot_tdb_pie_charts(stats)
    Visualizer.plot_tdd_distance_bar(distances)
    Visualizer.plot_cumulative_loc(df)
    Visualizer.plot_trends(df)
    Visualizer.plot_commit_size_boxplot(df)

if __name__ == "__main__":
    main()