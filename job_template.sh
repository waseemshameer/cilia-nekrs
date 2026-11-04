#!/bin/bash
# Example Slurm job: one GPU, one MPI rank. Adapt the #SBATCH lines, modules and NEKRS_HOME
# to your cluster. Submit from the case directory:
#   cd cases/small4 && sbatch ../../job_template.sh small4
#SBATCH --job-name=cilia_nekrs
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus=1
#SBATCH --cpus-per-task=8
#SBATCH --time=01:00:00
#SBATCH -o %x_%j.out

# module load <your MPI> <your CUDA or ROCm>

export NEKRS_HOME=${NEKRS_HOME:-$HOME/.local/nekrs}
export PATH=$NEKRS_HOME/bin:$PATH

cd $SLURM_SUBMIT_DIR
CASE=${1:-small4}   # case name: the directory must hold <case>.par

# Optional: share compiled code between runs so a new case directory does not recompile (~9 min cold).
# GPU kernels: OCCA names each by a hash of its source and build flags, so one cache serves all runs.
# Nek5000 interface: depends only on the polynomial order, so share one build per N.
# Keyed by the nekRS install time, so reinstalling nekRS starts a fresh cache.
NRS_SHARED_CACHE=$HOME/.cache/nekrs/$(stat -c %Y $NEKRS_HOME/bin/nekrs)
N=$(sed -n 's/^polynomialOrder *= *\([0-9]*\).*/\1/p' $CASE.par)
export OCCA_CACHE_DIR=$NRS_SHARED_CACHE/occa/
mkdir -p $OCCA_CACHE_DIR $NRS_SHARED_CACHE/nek5000_N$N .cache
[ -e .cache/nek5000 ] || ln -s $NRS_SHARED_CACHE/nek5000_N$N .cache/nek5000

nrsmpi $CASE ${SLURM_NTASKS:-1}
