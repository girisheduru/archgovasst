---
name: update-readmes
description: Keep the Architecture Governance Assistant frontend and backend READMEs accurate whenever project code, dependencies, or runtime configuration changes.
---

# Update project READMEs

1. Review the code changes for the task and read `frontend/README.md` and `backend/README.md` from the repository root.
2. Update the frontend README when user-facing behavior, setup, build commands, or frontend configuration changes. Update the backend README when API behavior, setup, runtime configuration, or deployment changes. For changes to the API contract, proxy, or cross-origin requests, check the instructions on both sides.
3. Verify edited commands, paths, environment variable names, and API examples against the implementation. Keep `COMMANDS.md` in sync when project commands are added or changed. Preserve existing README text that still applies.

If both READMEs are still accurate, finish the check without a documentation edit.
