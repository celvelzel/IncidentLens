#!/usr/bin/env bash
# Create/update a dedicated clean HPC checkout; never run this during a frozen batch.
set -euo pipefail
REPO_URL="${REPO_URL:-https://github.com/celvelzel/IncidentLens.git}"
BRANCH="${BRANCH:-codex/hpc-wpd}"
DEST="${1:?Usage: bash sync.sh /absolute/path/to/new-hpc-checkout}"
if [[ ! -e "$DEST" ]]; then
  git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$DEST"
else
  [[ -d "$DEST/.git" || -f "$DEST/.git" ]] || { echo 'Not a Git checkout' >&2; exit 1; }
  [[ "$(git -C "$DEST" remote get-url origin)" == "$REPO_URL" ]] || { echo 'Unexpected remote' >&2; exit 1; }
  [[ "$(git -C "$DEST" branch --show-current)" == "$BRANCH" ]] || { echo 'Unexpected branch' >&2; exit 1; }
  [[ -z "$(git -C "$DEST" status --porcelain)" ]] || { echo 'Checkout is dirty' >&2; exit 1; }
  [[ ! -d "$DEST/results/hpc-wpd" ]] || { echo 'Existing HPC sessions: use a NEW checkout for latest code' >&2; exit 1; }
  git -C "$DEST" fetch origin "$BRANCH"
  git -C "$DEST" merge --ff-only "origin/$BRANCH"
fi
git -C "$DEST" rev-parse HEAD
printf 'Checkout ready. Install dependencies and follow docs/hpc-wpd-guide.zh-CN.md\n'
