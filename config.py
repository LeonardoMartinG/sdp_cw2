class Config:
    # mode selection
    MODE = "INFO"
    MODE_OPTIONS = {"INFO", "DEBUG"}

    # date range (optional)
    START_DATE = ""
    END_DATE = ""

    # local clone
    REPO_PATH = "repos/commons-numbers"

    # output file
    OUTPUT_CSV = "driller_output.csv"

    # thresholds
    MAX_MODIFIED_FILES = 120
    MAX_ADDED_LOC = 12000

    # atomic heuristics
    SMALL_COMMIT_MAX_FILES = 12
    CYCLE_WINDOW_COMMITS = 3

    # matching strictness
    REQUIRE_SAME_PACKAGE = False

    # ------------------------------------------------------------
    # Path filters (CRUCIAL for multi-module repos like Apache)
    #
    # If INCLUDE_PATH_PREFIXES is non-empty, ONLY those paths are analysed.
    # Example for Gilded Rose (Java Maven module only):
    #   INCLUDE_PATH_PREFIXES = ["Java/src/"]
    #
    # Example for commons-lang:
    #   INCLUDE_PATH_PREFIXES = ["src/main/java/", "src/test/java/"]
    # ------------------------------------------------------------
    INCLUDE_PATH_PREFIXES = []   # use: ["Java/src/"] for gilded-rose
    EXCLUDE_PATH_PREFIXES = []   # e.g. ["doc/", "site/"]
