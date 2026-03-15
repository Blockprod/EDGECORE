## LFS migration and history-rewrite plan

This document describes a safe, reviewable procedure to migrate large files to Git LFS
and (optionally) rewrite repository history to remove large objects from all branches.

IMPORTANT: rewriting history is destructive. Coordinate with your team and take backups.

High-level strategy
- Create a preview branch with `git lfs migrate import` (already done: `lfs-migration-preview`).
- Open PR and validate CI on preview branch.
- When approved, run the migration on the branches you want to replace (usually `main`) by rewriting history locally and force-pushing the rewritten refs to origin.

Prerequisites
- Install `git-lfs` and `git-filter-repo` (preferred) or `bfg`.
- Ensure you have push permissions to the remote and that all contributors are informed.

Backup (mandatory)
1. Create a mirror backup of the remote repository (store offline):

```bash
git clone --mirror https://github.com/Blockprod/EDGECORE.git edgecore-repo-backup.git
tar -czf edgecore-repo-backup-$(date +%Y%m%d).tgz edgecore-repo-backup.git
```

2. Optionally create a GitHub release or archive snapshot via UI.

Preview branch validation
- Review the PR for `lfs-migration-preview` (https://github.com/Blockprod/EDGECORE/pull/new/lfs-migration-preview).
- Verify that CI passes and that the LFS pointers are present for the expected files.

Migration and force-push procedure (recommended sequence)

1) Lock the repository (announce maintenance window and ask contributors to pause pushes).

2) Locally, fetch all refs and prepare a fresh clone:

```bash
git clone --mirror https://github.com/Blockprod/EDGECORE.git
cd EDGECORE.git
```

3) Run `git lfs migrate import` to convert historical files to LFS. Example (adjust includes):

```bash
# convert results, debug_load_errors, bt_results_* across all refs
git lfs install --local
git lfs migrate import --include="results/**,debug_load_errors.txt,bt_results_*" --include-ref=refs/heads/* --yes
```

4) Verify the migration locally. Inspect commits containing large filenames and confirm they are LFS pointers:

```bash
git log --stat -n 20
git verify-pack -v .git/objects/pack/pack-*.idx | sort -k3 -n -r | head
```

5) Force-push all rewritten refs to origin (this updates history on remote):

```bash
# Force-update branches and tags
git push --force --all origin
git push --force --tags origin
```

6) Run a remote housekeeping: on the remote, GitHub will handle storage; locally, advertise cleanup

```bash
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

Post-migration steps for contributors
- Everyone with a clone must reclone, or follow these steps:

```bash
# Option A: reclone (recommended)
git clone https://github.com/Blockprod/EDGECORE.git

# Option B: if you must preserve local branches, run (dangerous):
git fetch origin
git reset --hard origin/main
git clean -fdx
```

Notes and alternatives
- If you prefer not to rewrite history, keep `lfs-migration-preview` as canonical new branch and merge non-destructively into `main`. This keeps history but may keep large objects in remote history.
- `git-filter-repo` can be used to perform more targeted removals; `bfg` is another option but `git-filter-repo` is faster and recommended.

Checklist before executing destructive push
- [ ] Team notified and maintenance window scheduled
- [ ] Mirror backup created and stored
- [ ] `lfs-migration-preview` reviewed and approved
- [ ] Script ready and tested on preview branch
- [ ] Push credentials available and tested

If you want, I can now:
- prepare the exact `git lfs migrate import` command to run for `main` and other branches and a one-line script to perform the force-push; or
- proceed to run the migration and force-push (only after explicit confirmation).
