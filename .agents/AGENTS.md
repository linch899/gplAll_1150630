# Project Rules - gplAll_1150630

## Git Synchronization Rule
- **Requirement**: Every time the agent modifies the codebase, processes data, or completes a task, the agent MUST automatically commit and push the changes to the GitHub repository.
- **Commands**:
  1. `git add .`
  2. `git commit -m "<Clear description of the changes or tasks completed>"`
  3. `git push`
- **Exception**: If the changes are purely temporary scratch files in the artifact directory, do not push them (the `.gitignore` already handles workspace-level ignores).
