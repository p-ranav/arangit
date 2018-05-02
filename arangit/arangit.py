import argparse
import os
import json
import subprocess
from arango import ArangoClient, exceptions

# Global variables, each a list of Python dictionaries
BRANCHES = []
COMMIT_OBJECTS = []
TREE_OBJECTS = []
BLOB_OBJECTS = []

# ArangoDB Configuration
ARANGO_CONFIG = {
    'protocol': 'http',
    'host': 'localhost',
    'port': 8529,
    'username': 'pranav',
    'password': 'pranav@Arango',
    'enable_logging': True
    }
ARANGO_CLIENT = ArangoClient(**ARANGO_CONFIG)
ARANGO_DATABASE_NAME = 'arangit'
ARANGO_DATABASE = ARANGO_CLIENT.db(ARANGO_DATABASE_NAME)

def object_exists(object_type, object_hash):
    result = False
    object_type_map = {
        "commit": COMMIT_OBJECTS,
        "tree": TREE_OBJECTS,
        "blob": BLOB_OBJECTS
        }
    for git_object in object_type_map[object_type]:
        if git_object["hash"] == object_hash:
            result = True       
    return result

def scan_git_branches(refs_heads_root):
    branches = []
    for current_directory, sub_directories, files in os.walk(refs_heads_root):
        for file in files:
            branch_path = os.path.join(current_directory, file)
            # Well this is a little hacky but it works to get all branch names
            branch_name = branch_path.replace(refs_heads_root,
                                              "")[1:].replace("\\", "/")
            result = subprocess.run(["cat", branch_path],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            branch_commit = result.stdout.decode("utf-8").strip()
            branches.append({ "type": "branch", "name": branch_name, "commit": branch_commit })
    return branches

def scan_git_object(repository_root, object_hash):
    git_object = {}

    # Run "git cat-file -t <object_hash>" to determine object type
    result = subprocess.run(["git", "cat-file", "-t", object_hash],
                            cwd=repository_root,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    git_cat_file_type = ""
    try:
        git_cat_file_type = result.stdout.decode("utf-8").strip()
    except UnicodeDecodeError:
        git_cat_file_type = result.stdout

    # Run 'git cat-file -p <object_hash>" to print object details
    result = subprocess.run(["git", "cat-file", "-p", object_hash],
                            cwd=repository_root,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    git_cat_file_print = ""
    try:
        git_cat_file_print = result.stdout.decode("utf-8").strip()
    except UnicodeDecodeError:
        git_cat_file_print = result.stdout

    # Handle commit objects
    if git_cat_file_type == "commit":
        git_object = {
            "type": git_cat_file_type,
            "hash": object_hash,
            "message": "",
            "parents": []
            }
        # If the git object is a commit object, git cat-file -p will show:
        # (1) tree <tree_object_hash>
        # (2) author <author_name> <author_email>
        # (3) committer <committer_name> <committer_email>
        for line in git_cat_file_print.split("\n"):
            if line.startswith("tree"):
                git_object["tree"] = line.split(" ")[1].strip()
            elif line.startswith("author"):
                git_object["author"] = {
                    "name": line.split("author ")[1].split(" <")[0],
                    "email": line.split("<")[1].split(">")[0]
                    }
            elif line.startswith("committer"):
                git_object["committer"] = {
                    "name": line.split("committer ")[1].split(" <")[0],
                    "email": line.split("<")[1].split(">")[0]
                    }
            elif line.startswith("parent"):
                git_object["parents"].append(line.split("parent ")[1].strip())
            else:
                git_object["message"] += line
        if git_object not in COMMIT_OBJECTS:
            COMMIT_OBJECTS.append(git_object)

        # Scan the tree object that the commit is pointing to
        if not object_exists("tree", git_object["tree"]):
            scan_git_object(repository_root, git_object["tree"])

        # Scan the parents commits of this commit
        for parent in git_object["parents"]:
            if not object_exists("commit", parent):
                scan_git_object(repository_root, parent)

    # Handle tree objects
    elif git_cat_file_type == "tree":
        git_object = {
            "type": git_cat_file_type,
            "hash": object_hash,
            "children": []
            }
        # If the git object is a tree object, git cat-file -p will show:
        # List of blob or tree objects
        for line in git_cat_file_print.split("\n"):
            line_entries = line.split(" ")
            file_or_directory_permissions = line_entries[0].strip()
            file_or_directory_type = line_entries[1].strip()
            file_or_directory_hash = line_entries[2].split('\t')[0].strip()
            file_or_directory_name = line_entries[2].split('\t')[1].strip()
            git_object["children"].append({
                "type": file_or_directory_type,
                "permissions": file_or_directory_permissions,
                "hash": file_or_directory_hash,
                "name": file_or_directory_name
                })
        if git_object not in TREE_OBJECTS:
            TREE_OBJECTS.append(git_object)

        # Scan the tree's children
        for child in git_object["children"]:
            if not object_exists(child["type"], child["hash"]):
                scan_git_object(repository_root, child["hash"])

    elif git_cat_file_type == "blob":
        encoded_content = ""
        try:
            encoded_content = git_cat_file_print.encode("utf-8")
        except:
            encoded_content = "unavailable"
        git_object = {
            "type": git_cat_file_type,
            "hash": object_hash,
            "content": git_cat_file_print
            }
        if git_object not in BLOB_OBJECTS:
            BLOB_OBJECTS.append(git_object)

def scan_git_repository(repository_root):
    # Start by checking if there is a .git directory
    git_directory = os.path.join(repository_root, ".git")
    if os.path.isdir(git_directory):
        # Good so far. Check if there are any branches
        heads_directory = os.path.join(git_directory, "refs/heads")
        if os.path.isdir(heads_directory):
            # We have branches! Scan 'em
            global BRANCHES
            BRANCHES = scan_git_branches(heads_directory)

            # For each branch in branches, scan commits and build up your graph
            for branch in BRANCHES:
                scan_git_object(repository_root, branch["commit"])
                
        else:
            # There are no branches in this git repository
            error_message = "{} is not a valid git repository".format(path)
            raise ValueError(error_message)            
    else:
        # There is not .git directory; not a valid git repository
        error_message = "{} is not a valid git repository".format(path)
        raise ValueError(error_message)

def create_arangit_graph(graph_name):
    try:
        ARANGO_DATABASE.delete_graph(graph_name, drop_collections=True)
    except:
        pass
    ARANGO_GRAPH = ARANGO_DATABASE.create_graph(graph_name)

    vertex_collections = {
        "branches": BRANCHES,
        "commits": COMMIT_OBJECTS,
        "trees": TREE_OBJECTS,
        "blobs": BLOB_OBJECTS
        }

    # Insert all vertices into appropriate collections
    for key, value in vertex_collections.items():
        collection_handle = ARANGO_GRAPH.create_vertex_collection(graph_name +\
                                                                  '_' +\
                                                                  key)
        for document in value:
            if key == "branches":
                document["_key"] = document["name"]
            else:
                document["_key"] = document["hash"][:6]
            collection_handle.insert(document)

    # Edge between branches and commits
    ARANGO_GRAPH.create_edge_definition(name=graph_name + '_branch_commit_edge',
        from_collections=[graph_name + "_branches"],
        to_collections=[graph_name + "_commits"])
    branch_commit_edge = ARANGO_GRAPH.edge_collection(graph_name +
                                                      '_branch_commit_edge')
    for branch in BRANCHES:
        branch_commit_edge.insert({
            '_from': graph_name + "_branches/" + branch["name"],
            '_to': graph_name + "_commits/" + branch["commit"][:6]
            })

    # Edge between commit and parents
    ARANGO_GRAPH.create_edge_definition(name=graph_name + '_commit_commit_edge',
                                        from_collections=[graph_name + "_commits"],
                                        to_collections=[graph_name + "_commits"])
    commit_commit_edge = ARANGO_GRAPH.edge_collection(graph_name +
                                                    '_commit_commit_edge')
    for commit in COMMIT_OBJECTS:
        for parent in commit["parents"]:
            commit_commit_edge.insert({
                '_from': graph_name + "_commits/" + commit["hash"][:6],
                '_to': graph_name + "_commits/" + parent[:6]
                })

    # Edge between commits and trees
    ARANGO_GRAPH.create_edge_definition(name=graph_name + '_commit_tree_edge',
                                        from_collections=[graph_name + "_commits"],
                                        to_collections=[graph_name + "_trees"])
    commit_tree_edge = ARANGO_GRAPH.edge_collection(graph_name +
                                                    '_commit_tree_edge')
    for commit in COMMIT_OBJECTS:
        commit_tree_edge.insert({
            '_from': graph_name + "_commits/" + commit["hash"][:6],
            '_to': graph_name + "_trees/" + commit["tree"][:6]
            })

    # Edege between tree and tree children
    ARANGO_GRAPH.create_edge_definition(name=graph_name + "_tree_tree_edge",
                                        from_collections=[graph_name + "_trees"],
                                        to_collections=[graph_name + "_trees"])
    tree_tree_edge = ARANGO_GRAPH.edge_collection(graph_name + "_tree_tree_edge")

    # Edege between tree and blob children
    ARANGO_GRAPH.create_edge_definition(name=graph_name + "_tree_blobs_edge",
                                        from_collections=[graph_name + "_trees"],
                                        to_collections=[graph_name + "_blobs"])
    tree_blobs_edge = ARANGO_GRAPH.edge_collection(graph_name + "_tree_blobs_edge")

    for tree in TREE_OBJECTS:
        for child in tree["children"]:
            if child["type"] == "tree":
                tree_tree_edge.insert({
                    '_from': graph_name + "_trees/" + tree["hash"][:6],
                    '_to': graph_name + "_trees/" + child["hash"][:6]
                    })
            elif child["type"] == "blob":
                tree_blobs_edge.insert({
                    '_from': graph_name + "_trees/" + tree["hash"][:6],
                    '_to': graph_name + "_blobs/" + child["hash"][:6]
                    })
    
if __name__ == "__main__":
    # We have just one argument for now; path to the git repository
    parser = argparse.ArgumentParser(description='Scan a git repository')
    parser.add_argument('--path',
                        help="Absolute path to root of a git repository")
    args = parser.parse_args()
    path_argument = os.path.join(os.getcwd(), args.path)
    scan_git_repository(path_argument)
    print("Number of Branches:", len(BRANCHES))
    print("Number of Commit Objects:", len(COMMIT_OBJECTS))
    print("Number of Tree Objects:", len(TREE_OBJECTS))
    print("Number of Blob Objects:", len(BLOB_OBJECTS))
    #print("BRANCHES:\n", json.dumps(BRANCHES, indent=4))
    #print("COMMIT OBJECTS:\n", json.dumps(COMMIT_OBJECTS, indent=4))
    #print("TREE OBJECTS:\n", json.dumps(TREE_OBJECTS, indent=4))
    #print("BLOB OBJECTS:\n", json.dumps(BLOB_OBJECTS, indent=4))

    git_repository_name = os.path.basename(path_argument)
    print(git_repository_name)
    create_arangit_graph(git_repository_name)
