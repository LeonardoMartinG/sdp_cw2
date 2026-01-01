# analyzer.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union, Tuple
import logging
import pandas as pd

from config import Config
from utils import (
    extract_package,
    is_bugfix_message,
    is_prod_file,
    is_test_file,
    is_squashed_message,
)

logger = logging.getLogger(__name__)

TEST_SUFFIXES = ("Test", "Tests", "IT", "IntegrationTest", "Spec", "Specification", "Should", "TestCase")

SUSPECT_MSG_PATTERNS = [
    "merge", "pull request", "squash",
    "release", "bump", "dependency", "changelog", "version",
    "format", "formatted", "whitespace", "reorganize", "reorganized",
    "translated", "translation", "move", "moved"
]


def is_suspect_message(msg: str) -> bool:
    m = (msg or "").lower()
    return any(k in m for k in SUSPECT_MSG_PATTERNS)


def base_from_test_stem(test_stem: str) -> Optional[str]:
    for suf in TEST_SUFFIXES:
        if test_stem.endswith(suf) and len(test_stem) > len(suf):
            return test_stem[: -len(suf)]
    if test_stem.startswith("Test") and len(test_stem) > 4:
        return test_stem[4:]
    return None


class Analyzer:
    latest_repo_tdd_value: Optional[float] = None

    @staticmethod
    def detect_tdb_behavior(
        modified_files: Iterable[Any],
        commit_msg: str,
        *,
        return_details: bool = False
    ) -> Union[bool, Dict[str, Any]]:
        if not isinstance(commit_msg, str):
            return {"tdb": False, "reason": "invalid_commit_msg"} if return_details else False

        if not is_bugfix_message(commit_msg):
            return {"tdb": False, "reason": "not_bugfix_message"} if return_details else False

        allowed_change_types = {"MODIFY", "ADD", "RENAME"}

        prod_info: List[Dict[str, str]] = []
        test_set = set()

        for mod in modified_files:
            path = getattr(mod, "new_path", None) or getattr(mod, "old_path", None)
            if not path or not str(path).endswith(".java"):
                continue

            change_type = getattr(mod, "change_type", None)
            change_name = getattr(change_type, "name", None) if change_type is not None else None
            if change_name not in allowed_change_types:
                continue

            norm_path = Path(str(path)).as_posix()
            pkg = extract_package(norm_path)
            stem = Path(norm_path).stem

            if is_test_file(norm_path):
                test_set.add((stem, pkg))
            elif is_prod_file(norm_path):
                prod_info.append({"stem": stem, "package": pkg, "path": norm_path})

        for prod in prod_info:
            prod_stem = prod["stem"]
            prod_pkg = prod["package"]
            expected = {
                f"{prod_stem}Test", f"{prod_stem}Tests",
                f"{prod_stem}IT", f"{prod_stem}IntegrationTest",
                f"Test{prod_stem}", f"{prod_stem}Spec", f"{prod_stem}Specification",
                f"{prod_stem}Should", f"{prod_stem}TestCase",
            }
            for t in expected:
                if (t, prod_pkg) in test_set:
                    return {"tdb": True, "prod": prod, "matched_test": {"stem": t, "package": prod_pkg}} if return_details else True

        return {"tdb": False, "reason": "no_matching_pair"} if return_details else False

    @staticmethod
    def calculate_distances(
        df: pd.DataFrame,
        *,
        return_dataframe: bool = False
    ) -> Union[List[Optional[int]], pd.DataFrame]:
        required = {"file_type", "path", "package", "commit_index", "project"}
        if not required.issubset(df.columns):
            raise ValueError(f"df must contain columns: {required}")

        prod_df = df[df["file_type"] == "prod"].copy()
        test_df = df[df["file_type"] == "test"].copy()

        empty_cols = [
            "project", "prod_path", "test_path",
            "prod_commit_index", "test_commit_index",
            "distance", "prod_stem", "package"
        ]

        if prod_df.empty:
            empty = pd.DataFrame(columns=empty_cols)
            return empty if return_dataframe else []

        prod_df["prod_stem"] = prod_df["path"].apply(lambda p: Path(str(p)).stem)
        test_df["test_stem"] = test_df["path"].apply(lambda p: Path(str(p)).stem)

        prod_first = (
            prod_df.sort_values("commit_index")
            .groupby(["project", "prod_stem", "package"], as_index=False)
            .first()
            .rename(columns={"path": "prod_path", "commit_index": "prod_commit_index"})
        )

        test_first = (
            test_df.sort_values("commit_index")
            .groupby(["project", "test_stem", "package"], as_index=False)
            .first()
            .rename(columns={"path": "test_path", "commit_index": "test_commit_index"})
        )

        grouped_tests: Dict[Tuple[str, str], List[Tuple[str, int, str]]] = {}
        for _, r in test_first.iterrows():
            key = (str(r["project"]), str(r["package"]))
            grouped_tests.setdefault(key, []).append(
                (str(r["test_stem"]), int(r["test_commit_index"]), str(r["test_path"]))
            )

        out_rows = []
        for _, p in prod_first.iterrows():
            project = str(p["project"])
            pkg = str(p["package"])
            prod_stem = str(p["prod_stem"])
            prod_idx = int(p["prod_commit_index"])
            prod_path = str(p["prod_path"])

            expected = {
                f"{prod_stem}Test", f"{prod_stem}Tests",
                f"{prod_stem}IT", f"{prod_stem}IntegrationTest",
                f"Test{prod_stem}", f"{prod_stem}Spec", f"{prod_stem}Specification",
                f"{prod_stem}Should", f"{prod_stem}TestCase",
            }

            candidates = grouped_tests.get((project, pkg), [])
            best: Optional[Tuple[int, str]] = None

            for test_stem, test_idx, test_path in candidates:
                if test_stem in expected:
                    if best is None or test_idx < best[0]:
                        best = (test_idx, test_path)
                    continue

                if len(prod_stem) >= 4 and prod_stem in test_stem:
                    if best is None or test_idx < best[0]:
                        best = (test_idx, test_path)

            if best is None:
                out_rows.append({
                    "project": project,
                    "prod_path": prod_path,
                    "test_path": None,
                    "prod_commit_index": prod_idx,
                    "test_commit_index": None,
                    "distance": None,
                    "prod_stem": prod_stem,
                    "package": pkg,
                })
            else:
                test_idx, test_path = best
                out_rows.append({
                    "project": project,
                    "prod_path": prod_path,
                    "test_path": test_path,
                    "prod_commit_index": prod_idx,
                    "test_commit_index": test_idx,
                    "distance": int(test_idx - prod_idx),
                    "prod_stem": prod_stem,
                    "package": pkg,
                })

        out = pd.DataFrame(out_rows, columns=empty_cols)
        if return_dataframe:
            return out
        return [None if pd.isna(x) else int(x) for x in out["distance"].tolist()]

    @staticmethod
    def _commit_meta(df: pd.DataFrame) -> pd.DataFrame:
        return df.drop_duplicates("commit_index")[["commit_index", "commit_size", "commit_msg"]].set_index("commit_index")

    @staticmethod
    def _atomic_like(commit_index: int, meta: pd.DataFrame, max_files: int) -> bool:
        if commit_index not in meta.index:
            return False
        row = meta.loc[commit_index]
        size = int(row.get("commit_size", 10**9))
        msg = row.get("commit_msg", "") or ""
        if size > max_files:
            return False
        if is_suspect_message(msg) or is_squashed_message(msg):
            return False
        return True

    @staticmethod
    def calculate_cycle_metrics(df: pd.DataFrame) -> Dict[str, float]:
        required = {"file_type", "path", "package", "project", "commit_index", "change_type", "commit_size", "commit_msg"}
        if not required.issubset(df.columns):
            raise ValueError(f"df must contain columns: {required}")

        work = df[df["change_type"].isin({"ADD", "MODIFY", "RENAME"})].copy()
        if work.empty:
            return {
                "cycle_test_first_rate": 0.0,
                "cycle_test_after_rate": 0.0,
                "cycle_same_commit_rate": 0.0,
                "cycle_atomic_like_rate": 0.0,
            }

        work["stem"] = work["path"].apply(lambda p: Path(str(p)).stem)
        work["base"] = work.apply(
            lambda r: base_from_test_stem(r["stem"]) if r["file_type"] == "test" else r["stem"],
            axis=1,
        )
        work = work.dropna(subset=["base"])

        meta = Analyzer._commit_meta(work)

        by_key: Dict[Tuple[str, str], List[Tuple[int, str, str]]] = {}
        for _, r in work.iterrows():
            key = (str(r["project"]), str(r["base"]))
            by_key.setdefault(key, []).append((int(r["commit_index"]), str(r["file_type"]), str(r["package"])))

        test_first = test_after = same_commit = atomic_like = total = 0

        for (project, base), events in by_key.items():
            events.sort(key=lambda x: x[0])

            grouped: Dict[int, List[Tuple[str, str]]] = {}
            for idx, ftype, pkg in events:
                grouped.setdefault(idx, []).append((ftype, pkg))

            for idx, entries in grouped.items():
                has_t = any(t == "test" for t, _ in entries)
                has_p = any(t == "prod" for t, _ in entries)
                if has_t and has_p:
                    same_commit += 1
                    total += 1
                    if Analyzer._atomic_like(idx, meta, Config.SMALL_COMMIT_MAX_FILES):
                        atomic_like += 1

            condensed: List[Tuple[int, str]] = []
            for idx in sorted(grouped.keys()):
                has_t = any(t == "test" for t, _ in grouped[idx])
                has_p = any(t == "prod" for t, _ in grouped[idx])
                if has_t and has_p:
                    continue
                if has_t:
                    condensed.append((idx, "test"))
                elif has_p:
                    condensed.append((idx, "prod"))

            for i in range(len(condensed) - 1):
                idx, cur = condensed[i]
                nxt_idx, nxt = condensed[i + 1]
                if (nxt_idx - idx) > Config.CYCLE_WINDOW_COMMITS:
                    continue
                total += 1
                if cur == "test" and nxt == "prod":
                    test_first += 1
                elif cur == "prod" and nxt == "test":
                    test_after += 1

        if total == 0:
            return {
                "cycle_test_first_rate": 0.0,
                "cycle_test_after_rate": 0.0,
                "cycle_same_commit_rate": 0.0,
                "cycle_atomic_like_rate": 0.0,
            }

        return {
            "cycle_test_first_rate": test_first / total,
            "cycle_test_after_rate": test_after / total,
            "cycle_same_commit_rate": same_commit / total,
            "cycle_atomic_like_rate": atomic_like / total,
        }

    @staticmethod
    def commit_type_metrics(df: pd.DataFrame) -> Dict[str, float]:
        g = df.groupby("commit_index")["file_type"].apply(lambda x: set(x))
        total = len(g)
        if total == 0:
            return {"test_only_rate": 0.0, "prod_only_rate": 0.0, "mixed_rate": 0.0}

        test_only = sum(s == {"test"} for s in g)
        prod_only = sum(s == {"prod"} for s in g)
        mixed = sum(("test" in s and "prod" in s) for s in g)
        return {
            "test_only_rate": test_only / total,
            "prod_only_rate": prod_only / total,
            "mixed_rate": mixed / total,
        }

    @staticmethod
    def evaluate_repo_tdd(df: pd.DataFrame, stats: Dict[str, int]) -> Dict[str, Any]:
        all_commits = max(int(stats.get("all_commits", 0)), 0)
        fix_commits = max(int(stats.get("fix_commits", 0)), 0)
        tdb_commits = max(int(stats.get("tdb_commits", 0)), 0)

        tdb_commit_ratio = (tdb_commits / all_commits) if all_commits else 0.0
        tdb_in_fix_ratio = (tdb_commits / fix_commits) if fix_commits else 0.0

        dist_df = Analyzer.calculate_distances(df, return_dataframe=True)
        valid = dist_df[dist_df["distance"].notna()]
        n_valid = len(valid)

        ordering_props = {"test_first": 0.0, "same_commit": 0.0, "test_after": 0.0}
        if n_valid:
            ordering_props["test_first"] = (valid["distance"] < 0).sum() / n_valid
            ordering_props["same_commit"] = (valid["distance"] == 0).sum() / n_valid
            ordering_props["test_after"] = (valid["distance"] > 0).sum() / n_valid

        cycle = Analyzer.calculate_cycle_metrics(df)
        ctm = Analyzer.commit_type_metrics(df)

        test_loc = float(df.loc[df["file_type"] == "test", "added_lines"].sum())
        prod_loc = float(df.loc[df["file_type"] == "prod", "added_lines"].sum())
        denom = test_loc + prod_loc
        test_loc_ratio = (test_loc / denom) if denom > 0 else 0.0

        test_events = int((df["file_type"] == "test").sum())
        prod_events = int((df["file_type"] == "prod").sum())
        denom2 = test_events + prod_events
        test_event_ratio = (test_events / denom2) if denom2 > 0 else 0.0

        weights = {
            "cycle_test_first_rate": 0.15,
            "cycle_atomic_like_rate": 0.20,
            "test_only_rate": 0.15,
            "test_loc_ratio": 0.25,
            "test_event_ratio": 0.10,
            "tdb_commit_ratio": 0.05,
            "tdb_in_fix_ratio": 0.05,
            "same_commit_prop": 0.10,
        }

        components = {
            "cycle_test_first_rate": float(cycle["cycle_test_first_rate"]),
            "cycle_atomic_like_rate": float(cycle["cycle_atomic_like_rate"]),
            "test_only_rate": float(ctm["test_only_rate"]),
            "test_loc_ratio": float(test_loc_ratio),
            "test_event_ratio": float(test_event_ratio),
            "tdb_commit_ratio": float(tdb_commit_ratio),
            "tdb_in_fix_ratio": float(tdb_in_fix_ratio),
            "same_commit_prop": float(ordering_props["same_commit"]),
        }

        score = 0.0
        total_w = 0.0
        for k, w in weights.items():
            score += components.get(k, 0.0) * float(w)
            total_w += float(w)

        score = (score / total_w) if total_w else 0.0
        score = max(0.0, min(1.0, float(score)))
        Analyzer.latest_repo_tdd_value = score

        return {
            "tdb_commit_ratio": tdb_commit_ratio,
            "tdb_in_fix_ratio": tdb_in_fix_ratio,
            "ordering_proportions": ordering_props,
            "cycle_metrics": cycle,
            "commit_type_metrics": ctm,
            "test_loc_ratio": test_loc_ratio,
            "test_event_ratio": test_event_ratio,
            "tdd_score": score,
            "notes": {
                "cycle_window_commits": Config.CYCLE_WINDOW_COMMITS,
                "atomic_like_small_commit_max_files": Config.SMALL_COMMIT_MAX_FILES,
                "project_grouping_enabled": True,
            },
        }

    @staticmethod
    def per_project_scores(df: pd.DataFrame, stats: Dict[str, int]) -> Dict[str, float]:
        scores = {}
        for project, sub in df.groupby("project"):
            if sub.empty:
                continue
            rep = Analyzer.evaluate_repo_tdd(sub, stats)
            scores[project] = float(rep["tdd_score"])
        return dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))
