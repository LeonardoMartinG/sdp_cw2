class Config:
    # mode selection
    # OPTIONS: "INFO", "DEBUG"
    MODE = "INFO"
    MODE_OPTIONS = {"INFO", "DEBUG"}

    # date range
    START_DATE = "2018-01-01"
    END_DATE = "2023-12-31"
    
    # local clone
    # REPO_PATH = "repos/commons-lang"
    REPO_PATH = "/home/yaoguyuan/Desktop/dubbo"
    
    # output file
    OUTPUT_CSV = 'driller_output.csv'

    # thresholds
    MAX_MODIFIED_FILES = 50 # maximum modified files to consider a normal commit
    MAX_ADDED_LOC = 5000  # maximum added lines of code to consider a normal commit