# arangit

arangit is an ArangoDB importer that (1) can parse a valid .git directory, (2) build a graph data model and (3) import this graph into ArangoDB

## Quick Start

```bash
$ python arangit.py --path <git_repository_root>
```

## Example Usage

```bash
$ git clone https://github.com/pranav-srinivas-kumar/arangit
$ cd arangit/arangit
$ git clone https://github.com/pranav-srinivas-kumar/zcm
$ python arangit --path zcm
```

### ArangoDB Collections

![Alt text](images/01.png?raw=true "ArangoDB Collections")

### Arango Graph

![Alt text](images/02.png?raw=true "Graph Visualization")

### Branches

![Alt text](images/03.png?raw=true "Branches")

### Commit Objects

![Alt text](images/04.png?raw=true "Commit Objects")

### Tree Objects

![Alt text](images/05.png?raw=true "Tree Objects")

### Blob Objects

![Alt text](images/06.png?raw=true "Blob Objects")