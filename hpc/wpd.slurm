#!/usr/bin/env bash
#SBATCH --job-name=incidentlens-wpd
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=48:00:00
#SBATCH --output=results/wpd-%j.out
# Site partition/account/QOS and time limit must be set per cluster rules.
set -euo pipefail
: "${HPC_CHECKOUT:?Set absolute HPC checkout path}"
: "${RUN_ID:?Set the initialized run ID}"
: "${INCIDENT_LENS_API_KEY:?Export the provider API key}"
: "${INCIDENT_LENS_BASE_URL:?Export provider base URL}"
cd "$HPC_CHECKOUT"
# No git pull, dependency installation, probes or new attempts inside the job.
exec .venv/bin/python hpc/run_wpd.py "${HPC_MODE:-run}" --run-id "$RUN_ID"
