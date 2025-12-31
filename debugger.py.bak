# This script could be used to analyze modified Java files and their methods in a Git repository.
# And it can be used as a debugging tool for the main script, because it provides detailed information of modified files and methods.
# To know how to use this script, simply take a look at the sample run at the end.

import argparse
from pydriller import Repository

# debugging a specified commit in a specified repository
# repo_path: str = the path to the repository
# commit_hash: str = the hash of the commit to debug
# mfile_path_hint: str|None = a hint to filter modified files by path (optional)
# mfile_suffix_hint: str|None = a hint to filter modified files by suffix (optional)
# detailed: bool = whether to show detailed diffs of modified files
def debug_commit(repo_path, commit_hash, mfile_path_hint=None, mfile_suffix_hint=None, detailed=False):
    print(f"Commit from repository: {repo_path}")
    print(f"Commit hash: {commit_hash}\n")

    for commit in Repository(path_to_repo=repo_path, single=commit_hash).traverse_commits():
        # prepare a dict to hold commit info
        commit_info = {}
        commit_info['msg'] = commit.msg
        commit_info['author'] = commit.author.name
        commit_info['date'] = commit.author_date
        # print commit info
        print(f"<Author: {commit_info['author']}>")
        print(f"<Date: {commit_info['date']}>")
        print(f"<Message: {commit_info['msg']}>\n")

        for modified_file in commit.modified_files:
            # filter modified files by path hint and suffix hint
            file_path = modified_file.new_path or modified_file.old_path # use the old path only if the file is deleted
            file_path = file_path.replace("\\", "/")  # normalize path to use forward slashes
            if mfile_suffix_hint is not None and not file_path.endswith(mfile_suffix_hint):
                continue
            if mfile_path_hint is not None and mfile_path_hint not in file_path:
                continue

            # prepare a dict to hold each modified file info
            file_info = {}
            file_info['filename'] = modified_file.filename
            file_info['change_type'] = modified_file.change_type.name

            # rather than extracting all changed methods, we need to split those added/removed/modified methods
            curr_methods = {m.long_name for m in modified_file.methods}
            prev_methods = {m.long_name for m in modified_file.methods_before}
            changed_methods = {m.long_name for m in modified_file.changed_methods}

            file_info['added_methods'] = list(curr_methods - prev_methods)
            file_info['removed_methods'] = list(prev_methods - curr_methods)
            file_info['modified_methods'] = list(changed_methods.intersection(prev_methods).intersection(curr_methods))
            
            print("======================================================\n")
            print(f"<Filename: {file_info['filename']}>")
            print(f"<Change Type: {file_info['change_type']}>")
            # print(f"<Changed Methods>: {changed_methods}>")
            print(f"<Added Methods: {file_info['added_methods']}>")
            print(f"<Removed Methods: {file_info['removed_methods']}>")
            print(f"<Modified Methods: {file_info['modified_methods']}>")

            if detailed:
                # to provide more detailed info, print the original DIFF
                print("<---------------------DIFF START--------------------->")
                print(modified_file.diff)
                print("<----------------------DIFF END---------------------->")

            print("\n") # add a newline for each modified file for better readability

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A CLI tool for debugging a specified commit in a specified repository."
    )

    # REQUIRED ARGUMENTS
    parser.add_argument(
        "repo_path", 
        help="Path to the git repository"
    )
    parser.add_argument(
        "commit_hash", 
        help="The specific commit hash you want to debug"
    )
    # OPTIONAL ARGUMENTS with default values
    parser.add_argument(
        "--suffix", "-s", 
        default=".java", 
        help="File suffix hint (default: .java)"
    )
    parser.add_argument(
        "--path", "-p", 
        default="src/test", 
        help="File path hint (default: src/test)"
    )
    parser.add_argument(
        "--detailed", "-d", 
        default=False, 
        type=bool,
        help="Show detailed diffs of modified files (default: False)"
    )

    args = parser.parse_args()
    debug_commit(
        repo_path=args.repo_path,
        commit_hash=args.commit_hash,
        mfile_suffix_hint=args.suffix,
        mfile_path_hint=args.path,
        detailed=args.detailed
    )

# Just a sample run of the script, which can be replicated in the terminal:

# yaoguyuan@yaoguyuan-virtual-machine:~/Desktop/sdp_cw2$ python3 debugger.py --help
# usage: debugger.py [-h] [--suffix SUFFIX] [--path PATH] [--detailed DETAILED] repo_path commit_hash

# A CLI tool for debugging a specified commit in a specified repository.

# positional arguments:
#   repo_path             Path to the git repository
#   commit_hash           The specific commit hash you want to debug

# options:
#   -h, --help            show this help message and exit
#   --suffix SUFFIX, -s SUFFIX
#                         File suffix hint (default: .java)
#   --path PATH, -p PATH  File path hint (default: src/test)
#   --detailed DETAILED, -d DETAILED
#                         Show detailed diffs of modified files (default: False)
# yaoguyuan@yaoguyuan-virtual-machine:~/Desktop/sdp_cw2$ python3 debugger.py /home/yaoguyuan/Desktop/commons-csv 50a89da39fb3f2cf126c9ba7d41a099a3e576d6c --detailed=True
# Commit from repository: /home/yaoguyuan/Desktop/commons-csv
# Commit hash: 50a89da39fb3f2cf126c9ba7d41a099a3e576d6c

# <Author: Emmanuel Bourg>
# <Date: 2012-03-26 23:25:48+00:00>
# <Message: Test empty files

# git-svn-id: https://svn.apache.org/repos/asf/commons/proper/csv/trunk@1305668 13f79535-47bb-0310-9956-ffa450edef68>

# ======================================================

# <Filename: CSVParserTest.java>
# <Change Type: MODIFY>
# <Added Methods: ['CSVParserTest::testEmptyFile()']>
# <Removed Methods: []>
# <Modified Methods: []>
# <---------------------DIFF START--------------------->
# @@ -217,6 +217,12 @@ public class CSVParserTest {
#          }
#      }
 
# +    @Test
# +    public void testEmptyFile() throws Exception {
# +        CSVParser parser = new CSVParser("", CSVFormat.DEFAULT);
# +        assertNull(parser.getRecord());
# +    }
# +
#      @Test
#      @Ignore
#      public void testBackslashEscapingOld() throws IOException {

# <----------------------DIFF END---------------------->


