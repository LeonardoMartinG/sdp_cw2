import pandas as pd
from config import Config
from miner import mine_repository
from analyzer import Analyzer
from visualizer import Visualizer


def main():
    df, stats = mine_repository(Config.REPO_PATH, Config.MODE)
    if df.empty:
        raise RuntimeError("No Java test/production events detected.")

    # Normalize dates
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(None)

    # Rebuild commit_index globally and consistently
    unique_commits = (
        df[["commit", "date"]]
        .drop_duplicates("commit")
        .sort_values("date")
        .reset_index(drop=True)
    )
    unique_commits["commit_index"] = unique_commits.index

    df = df.drop(columns=["commit_index"], errors="ignore")
    df = df.merge(unique_commits[["commit", "commit_index"]], on="commit", how="left")

    df["month"] = df["date"].dt.to_period("M")
    df.to_csv(Config.OUTPUT_CSV, index=False)

    # Distance-based ordering
    distances = Analyzer.calculate_distances(df)


    # Repository-level TDD evaluation

    tdd_report = Analyzer.evaluate_repo_tdd(df, stats)

    print("\n=== Repository TDD Analysis Report ===")
    print("1) Commit Summary")
    print(f"   1.1 All commits processed : {stats.get('all_commits', 0)}")
    print(f"   1.2 Bugfix commits        : {stats.get('fix_commits', 0)}")
    print(f"   1.3 TDB-detected commits : {stats.get('tdb_commits', 0)}")

    print("2) Ratios")
    print(f"   2.1 TDB / All commits    : {tdd_report['tdb_commit_ratio']:.4f}")
    print(f"   2.2 TDB / Fix commits    : {tdd_report['tdb_in_fix_ratio']:.4f}")

    ordering = tdd_report["ordering_proportions"]
    print("3) Prod–Test Ordering Proportions")
    print(f"   3.1 Test First (d < 0)   : {ordering['test_first']:.2%}")
    print(f"   3.2 Same commit          : {ordering['same_commit']:.2%}")
    print(f"   3.3 Test After (d > 0)  : {ordering['test_after']:.2%}")

    print("4) Test / Production Signals")
    print(f"   4.1 Test LOC ratio       : {tdd_report['test_loc_ratio']:.4f}")
    print(f"   4.2 Test event ratio     : {tdd_report['test_event_ratio']:.4f}")

    print("5) Aggregated Score")
    print(f"   5.1 TDD score (0..1)     : {tdd_report['tdd_score']:.4f}")
    print(f"   5.2 Stored value         : {Analyzer.latest_repo_tdd_value}")
    print("=======================================\n")


    # Per-project TDD breakdown

    if "project" in df.columns and df["project"].nunique() > 1:
        per_project = Analyzer.per_project_scores(df, stats)

        print("Per-project TDD score ranking:")
        for project, score in per_project.items():
            print(f"  {project:<25} {score:.4f}")
        print()


    # Visualizations
    Visualizer.plot_tdb_pie_charts(stats)
    Visualizer.plot_tdd_distance_bar(distances)
    Visualizer.plot_cumulative_loc(df)
    Visualizer.plot_trends(df)
    Visualizer.plot_commit_size_boxplot(df)


if __name__ == "__main__":
    main()
