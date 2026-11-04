#!/bin/bash
# Example Slurm job. Adapt the #SBATCH lines to your cluster, or override them on the sbatch line.
# Runs one or more cases one after another on the same node, so their timings compare:
#   cd cases/small4 && sbatch ../../job_template.sh small4
#   cd cases && sbatch -n 4 --gpus=4 ../job_template.sh small4/small4 tiled8/tiled8:4
# Each argument is [<dir>/]<case>[:<ranks>]: <dir> holds <case>.par/.re2/.usr, the log is <dir>/<case>.out.
# <ranks> (default 1) is the number of GPUs for that run; request the largest on the sbatch line.
# Optional files:
#   cluster.env in the submit directory: sourced once, for modules and settings such as NEKRS_HOME.
#   run.env in a case's directory: sourced for that run only, for example export NEKRS_GPU_MPI=1.
#SBATCH --job-name=cilia_nekrs
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus=1
#SBATCH --cpus-per-task=8
#SBATCH --time=01:00:00
#SBATCH -o %x_%j.out

cd "$SLURM_SUBMIT_DIR" || exit 1
[ -f cluster.env ] && source ./cluster.env

export NEKRS_HOME=${NEKRS_HOME:-$HOME/.local/nekrs}
export PATH=$NEKRS_HOME/bin:$PATH

# Share compiled code between runs so a new case directory does not recompile (~9 min cold).
# GPU kernels: OCCA names each by a hash of its source and build flags, so one cache serves all runs.
# Nek5000 interface: depends only on the polynomial order, so share one build per N.
# Keyed by the nekRS install time, so reinstalling nekRS starts a fresh cache.
NRS_SHARED_CACHE=$HOME/.cache/nekrs/$(stat -c %Y "$NEKRS_HOME/bin/nekrs")
export OCCA_CACHE_DIR=$NRS_SHARED_CACHE/occa/

echo "node $(hostname)"
nvidia-smi topo -m 2>&1 | head -8                                      # GPU links (NVLink or PCIe)
ucx_info -d 2>/dev/null | grep -E 'Transport: ' | sort -u | tr '\n' ' '; echo   # UCX transports

[ $# -eq 0 ] && set -- small4
FAILED=0
for ARG in "$@"; do
  RUN=${ARG%%:*}; NR=1; [ "$ARG" != "$RUN" ] && NR=${ARG#*:}
  (
    cd "$(dirname "$RUN")" || exit 1
    CASE=$(basename "$RUN")
    N=$(sed -n 's/^polynomialOrder *= *\([0-9]*\).*/\1/p' "$CASE.par")
    mkdir -p "$OCCA_CACHE_DIR" "$NRS_SHARED_CACHE/nek5000_N$N" .cache
    [ -e .cache/nek5000 ] || ln -s "$NRS_SHARED_CACHE/nek5000_N$N" .cache/nek5000
    [ -f run.env ] && source ./run.env
    echo "=== $RUN on $NR ranks $(date)${NEKRS_GPU_MPI:+, NEKRS_GPU_MPI=$NEKRS_GPU_MPI}"
    nrsmpi "$CASE" "$NR" > "$CASE.out" 2>&1; RC=$?
    echo "=== $RUN done $(date), exit $RC"
    exit $RC
  ) || FAILED=1
done
exit $FAILED
