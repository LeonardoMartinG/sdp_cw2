# This script collects those related information by mining the git repository

from pydriller import Repository

def mine_repo(repo_path, size=-1, detailed=False):
    print(f"Mining repository at: {repo_path}")

    # initialize a counter to limit the number of commits processed
    commit_count = 0

    for commit in Repository(repo_path, order='reverse').traverse_commits():
        if size != -1 and commit_count >= size:
            break
        commit_count += 1

        # prepare a dict to hold commit info
        commit_info = {}
        commit_info['msg'] = commit.msg
        commit_info['author'] = commit.author.name
        commit_info['date'] = commit.author_date
        # print commit info
        print(f"<Author: {commit_info['author']}>")
        print(f"<Date: {commit_info['date']}>")
        print(f"<Message: {commit_info['msg']}>")

        # prepare a dict to hold modified files info
        modified_files_info = {}
        modified_files_info['num'] = commit.files
        # print modified files info
        print(f"<Number of modified files: {modified_files_info['num']}>")

        for modified_file in commit.modified_files:
            # to ensure that we only analyze JAVA source files
            if not modified_file.filename.endswith('.java'):
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
            file_info['modified_methods'] = list(changed_methods.intersection(prev_methods))

            print(f"    <Filename: {file_info['filename']}>")
            print(f"    <Change Type: {file_info['change_type']}>")
            print(f"    <Added Methods: {file_info['added_methods']}>")
            print(f"    <Removed Methods: {file_info['removed_methods']}>")
            print(f"    <Modified Methods: {file_info['modified_methods']}>")

            if detailed:
                # to provide more detailed info, print the original DIFF
                print("    -------------------- Diff Start --------------------")
                print(modified_file.diff)
                print("    -------------------- Diff End ----------------------\n\n")

if __name__ == "__main__":
    repo_path = "/home/yaoguyuan/Desktop/commons-csv"  # specify the path to your local git repository
    mine_repo(repo_path) 