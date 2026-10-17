# Team Git Workflow and Branching Standards

## Branching Model
- `main` - Production-ready branch. Direct pushes are disabled; changes require approved pull requests.
- `feature/<name>` - Short-lived feature development branches branched off main.
- `fix/<issue-id>` - Bug fix branches with targeted regression tests.

## Conventional Commit Syntax
Commit messages must follow the Conventional Commits specification:
- `feat: add debounce file watcher to indexing service`
- `fix: resolve SQLite busy timeout during concurrent WAL access`
- `test: add end-to-end integration test for search router`
- `docs: update product specification with incremental indexing numbers`

Never rewrite history on shared branches (`git push --force` is prohibited on main).