# ClickHouse Build

PostgreSQL to ClickHouse migration tool.

## Preparation

  - Ensure you are working on a branch
  - Get AWS keys
  - Add an [AGENTS.md](https://agents.md/) file to your repo to help `chbuild` improve it's efficacy

## Running

To start, run the application:

```
chbuild
```

or

```
chbuild --repo /path/to/repo
```

## TODO

**General**
  - [ ] Check that these are not MySQL queries etc - try get postgres context
  - [ ] Check planning agent aren't rewriting queries when scanning

**Data migrator**
  - [ ] Should suggest sorting keys based on queries
