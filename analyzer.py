# analyzer.py
from pathlib import Path
from utils import *

class Analyzer:

    @staticmethod
    def detect_tdb_behavior(modified_files, commit_msg):
        """
        Detect TDB (Test Driven Bugfixing) behavior.
        Return True only if:
        1. At least one Prod and its Test are modified together in the commit.
        2. The commit can be deduced as a bugfix from its message.
        """
        if not is_bugfix_message(commit_msg):
            return False
        
        mod_prod_files = []
        mod_test_files = []
        
        for mod in modified_files:
            # only consider .java files
            path = mod.new_path or mod.old_path
            if not path or not path.endswith(".java"):
                continue

            # only consider MODIFY changes
            if mod.change_type.name != "MODIFY":
                continue
                
            # classification
            if is_test_file(path):
                mod_test_files.append(path)
            elif is_prod_file(path):
                mod_prod_files.append(path)
            else:
                continue

        # check for synchronized Prod-Test pairs
        num_sync_pairs = 0
        for prod_path in mod_prod_files:
            prod_name = Path(prod_path).stem
            expected_test_names = {
                f"{prod_name}Test", f"{prod_name}Tests",
                f"{prod_name}IT", f"{prod_name}IntegrationTest"
            }
            for test_path in mod_test_files:
                if Path(test_path).stem in expected_test_names:
                    return True
        
        return False

    @staticmethod
    def calculate_distances(df):
        """
        Calculate distances between Prod and Test file additions.
        To avoid multiple additions of the same file affecting the result, we only consider the first addition (smallest commit_index) of each file.
        """
        # split prod and test
        prod_df = df[df["file_type"] == "prod"].copy()
        test_df = df[df["file_type"] == "test"].copy()

        # extract stem
        prod_df["stem"] = prod_df["path"].apply(lambda p: Path(p).stem)
        test_df["stem"] = test_df["path"].apply(lambda p: Path(p).stem)

        # only consider first additions
        prod_first_lookup = prod_df.groupby(["stem", "package"])["commit_index"].min().reset_index()
        test_first_lookup = test_df.groupby(["stem", "package"])["commit_index"].min().to_dict()

        distances = []
        for _, row in prod_first_lookup.iterrows():
            prod_stem = row["stem"]
            prod_pkg = row["package"]
            prod_idx = row["commit_index"]

            expected_test_stems = [
                f"{prod_stem}Test", f"{prod_stem}Tests",
                f"{prod_stem}IT", f"{prod_stem}IntegrationTest"
            ]
            
            test_idx = None
            for test_stem in expected_test_stems:
                key = (test_stem, prod_pkg)
                if key in test_first_lookup:
                    test_idx = test_first_lookup[key]
                    break
            
            if test_idx is not None:
                distances.append(test_idx - prod_idx)
            else:
                distances.append(None)
                
        return distances