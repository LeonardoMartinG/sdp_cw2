# main.py
import pandas as pd
from config import Config
from miner import mine_repository
from analyzer import Analyzer
from visualizer import Visualizer

def main():
    # 1. Mine data from the repository
    df, stats = mine_repository(Config.REPO_PATH)    
    if df.empty:
        raise RuntimeError("No Java test/production files detected.")
    
    # Data preprocessing
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