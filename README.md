# arangit

arangit is an ArangoDB importer that (1) can parse a valid .git directory, (2) build a graph data model and (3) import this graph into ArangoDB

## Usage

```bash
$ python arangit.py --path <git_repository_root>
```

## Screenshots

### ArangoDB Collections

![Alt text](images/01.png?raw=true "ArangoDB Collections")

### Subset of Graph

![Alt text](images/02.png?raw=true "Graph Visualization")

### Commit Objects

![Alt text](images/03.png?raw=true "Commit Objects")

### Tree Objects

![Alt text](images/04.png?raw=true "Tree Objects")

### Blob Objects

![Alt text](images/05.png?raw=true "Blob Objects")