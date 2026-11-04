#!/usr/bin/env bash
# Builds the udf against the mock and runs the 16 GPU-less checks. Every run has a timeout, because one class of bug
# (IQN dot products not reduced across ranks) hangs instead of failing. All checks run even after a failure.
#   tests/udf_mock/run_all.sh                 uses cilia.udf at the repo root
#   UDF=<file> MOCK_TIMEOUT=<s> run_all.sh    another udf, or another limit per run (default 60 s; all 16 take about 14 s)
set -u
cd "$(dirname "$(readlink -f "$0")")"
UDF=$(readlink -f "${UDF:-../../cilia.udf}")
LIMIT=${MOCK_TIMEOUT:-60}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
failed=0 total=0

check() {  # check <name> <command...>
    local name=$1 rc; shift
    total=$((total + 1))
    timeout -k 5 "$LIMIT" "$@" > "$WORK/log" 2>&1; rc=$?
    if [ "$rc" -eq 0 ]; then
        echo "PASS     $name"
    else
        failed=$((failed + 1))
        if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then echo "TIMEOUT  $name (over $LIMIT s)"; else echo "FAIL     $name (exit $rc)"; fi
        tail -n 15 "$WORK/log"
    fi
}

ranks() { echo mpirun --oversubscribe -np "$1"; }

python3 okl2cpp.py "$UDF" "$WORK/new_udf.cpp" || { echo "FAIL     okl2cpp.py"; exit 1; }
for d in halo kin dist; do
    timeout 300 mpicxx -std=c++17 -O2 -I. -include "$WORK/new_udf.cpp" "driver_$d.cpp" -o "$WORK/t_$d" \
        || { echo "FAIL     build driver_$d.cpp"; exit 1; }
done

COORDS="../../cases/tiled4/coordinates_tiled4.txt -2 2 -2 2 40 40 12"
for n in 1 2 3 4; do check "halo block, $n ranks" $(ranks $n) "$WORK/t_halo" $COORDS block 100; done
check "halo slab, 4 ranks" $(ranks 4) "$WORK/t_halo" $COORDS slab 100
check "halo scatter, 4 ranks" $(ranks 4) "$WORK/t_halo" $COORDS scatter 100
for n in 1 4; do check "kinematics fb, $n ranks" $(ranks $n) "$WORK/t_kin" $COORDS block 100 fb arclength; done
check "kinematics rod, 4 ranks" $(ranks 4) "$WORK/t_kin" $COORDS block 100 rod uniform z
for n in 1 2 3 4; do
    check "distributed IQN, $n ranks" $(ranks $n) "$WORK/t_dist" synthetic9 -1 3 -1 3 20 20 6 block 20 8 1e-9 8 "$WORK/F$n.bin"
done
# t_dist can print PASS and exit 0 with wrong forces, so the rank-count comparison is what catches a bad reduction.
for n in 2 3 4; do check "F 1 vs $n ranks" python3 cmp.py "$WORK/F1.bin" "$WORK/F$n.bin" 540; done

echo "$((total - failed)) of $total checks passed"
[ "$failed" -eq 0 ] && [ "$total" -eq 16 ]
