# Signal catalogue: nekRS v26.0.1 and cilia.udf log lines

Checked 2026-11-01 against logs of our own runs (all regexes below were run on them; counts in the last section) and the nekRS source (abbrev `N/`). Those logs are not in this repository.

Python: `F = r'[-+]?\d+\.\d+(?:[eE][-+]?\d+)?'` (a float as printed by `%e`/`%.3f`). Match on `line.rstrip('\n')`, use `re.search` / `re.match`. Everything goes to stdout in the single SLURM `-o %x_%j.out` file, in order (udf printf and nekRS printf interleave correctly). Only rank 0 prints in the 1-GPU runs.

## 1. Per-step lines (nekRS)

Printed by `nrs_t::printStepInfo`, `N/src/app/nrs/nrs.cpp:1042-1141`, called from `N/src/bin/driver.cpp:286, 300, 320`. Every step, because `PRINT INFO FREQUENCY` is 1 here (`N/src/lib/nekrs.cpp:524`).

| Signal | Regex | Real example | Source |
|---|---|---|---|
| step, t, dt, CFL | `^step=(\d+)\s+t=\s*(F)\s+dt=(F)\s+CFL=\s*(F)\s*$` | `step=64       t= 6.40000000e-02  dt=1.0e-03  CFL= 0.720` | nrs.cpp:1136 (`"step=%-8d t= %.8e  dt=%.1e  CFL= %.3f\n"`) |
| step wall time | `^step=(\d+)\s+elapsedStep=\s*(F)s\s+elapsedStepSum=\s*(F)s\s*$` | `step=64       elapsedStep= 4.79e-02s  elapsedStepSum= 6.04176e+00s` | nrs.cpp:1140; driver.cpp:243-320 |
| step separator | `^::$` | `::` | driver.cpp:321 |
| divergence error | `^step=(\d+)\s+FLUID divUErr\s*: (F)\s+(F)\s*$` (vol-avg, L2) | `step=64       FLUID divUErr       : 4.65e-10  1.49e-02` | nrs.cpp:1119 |
| run start marker | `^timestepping to time (\S+) \.\.\.$` | `timestepping to time 2 ...` | driver.cpp:243 |
| run end marker | `^finished with exit code (-?\d+)$` | `finished with exit code 0` | N/src/lib/nekrs.cpp:699 |
| runtime statistics block | `^>>> runtime statistics \(step= (\d+)\s+totalElapsed= (F)s\):` | `>>> runtime statistics (step= 1000  totalElapsed= 81.9334s):` | driver.cpp (runTimeStatFreq) |

Notes:
- **With IQN coupling (corrector loop), one step prints several blocks.** `driver.cpp:284-288` prints the full solver block + `t=/dt/CFL` for every non-converged corrector, then the final block. `elapsedStep` and `::` appear once per step only. Example: one small4 run has 2000 steps, 2000 `elapsedStep` lines, 4779 `t= ... CFL=` lines. A parser must key on `elapsedStep` (or the `iqn` line) for "a step finished", not on the CFL line.
- `t=` here is the new time `timeNew`; the udf `vals`/`wall`/`iqn` lines carry the same `t` of the step being computed.
- `dt` is fixed in the cilia case (`dt=2.0e-3` in the par, no `targetCFL`). `dt=` in the line is the only place a dt change would show; if `targetCFL` were enabled, `adjustDt` (nrs.cpp:1495) prints nothing normally (only `adjustDt: dt=%g CFL= %g CFLpred= %g CFLmax= %g CFLmin= %g` when `platform->verbose()`, nrs.cpp:1611). Not observed in any cilia log; regex if verbose: `^adjustDt: dt=(\S+) CFL= (\S+) CFLpred= (\S+) CFLmax= (\S+) CFLmin= (\S+)$`.
- CFL values: healthy small4 run at dt 2e-3 peaks about 0.7 to 1.4; the one divergence seen was 96.5 at step 128, aborted at 118.7.

## 2. Solver iteration counts and non-convergence

| Signal | Regex | Real example | Source |
|---|---|---|---|
| Linear solve (p, ux, uy, uz; or combined `U` with the block solver) | `^step=(\d+)\s+FLUID (p\|ux\|uy\|uz\|U)\s*: iter (\d+)\s+resNorm0 (F)\s+resNorm (F)\s*$` | `step=64       FLUID p             : iter 003  resNorm0 3.56e-01  resNorm 2.37e-04` | nrs.cpp:1065 (`"%03d"` iter, resNorm0 = initial residual after projection, resNorm = final) |
| Projection (initial guess) | `^step=(\d+)\s+proj FLUID (\S+)\s*: resNorm0 (F)\s+resNorm (F)\s+ratio = (F)\s+(\d+)/(\d+)\s*$` | `step=273      proj FLUID ux       : resNorm0 1.13e+00  resNorm 9.59e-03  ratio = 1.178e+02  28/40` | nrs.cpp:1055; last two ints are vectors used / nVector |
| Projection dropped a vector | `^solutionProjection fluid (pressure\|velocity): Discard new solution as it is linearly dependent!$` | `solutionProjection fluid pressure: Discard new solution as it is linearly dependent!` | printed by the elliptic projection code (not a nekRS error); 118 pressure + 6 velocity lines across our logs; seen in healthy runs too, so it is NOT a failure signal alone. Appears far more (every step) in the one diverging run. |
| Unconverged marker | none exists | | nekRS v26 prints **no** "did not converge" text. `iter` equal to the maxIter (N/src/core/elliptic/elliptic.cpp:266 sets it) is the only sign, and maxIter is not in the log. Solver `iter` of the pressure at 10 to 20 and velocity at 265 to 286 (the diverging run, just before the blow-up) vs 1 to 5 normally is the practical warning. grep for "converge" in our logs finds nothing from nekRS. |

Non-finite residual inside CG/GMRES aborts through `nekrsCheck` (section 4): `cg.hpp:84` "`<name> unreasonable initial residual norm!`", `cg.hpp:346, 440` "`<name> invalid resiual norm while running linear solver!`" (sic, typo is in the source), gmres.hpp:59, 467. Not seen in any real log (CFL guard fires first).

### Cilia IQN coupling (udf)

| Signal | Regex | Real example | Source |
|---|---|---|---|
| IQN converged step | `^(F) (\d+) (F) (\d+)  iqn$` (time, correctors used, rel. residual, cumulative count of steps that hit maxIter) | `6.4000000000e-02 3 6.597e-06 0  iqn` | `cilia.udf` |
| IQN non-convergence | same line with `iter == couplingMaxIter` (50) **or** 4th field increasing | `1.8000000000e-02 50 3.004e-04 1  iqn` (maxIter 50 hit; the counter goes 1, 2, 3 on following steps) | `cilia.udf` (`iqnMaxed++` when `!converged`) |

## 3. Cilia udf diagnostic lines (parsed by gate.py)

`gate.py:34-40` splits on whitespace and keys on the last token (`vals` / `wall`), `float()` on the rest.

| Signal | Regex | Real example | Source |
|---|---|---|---|
| vals: time, ubar, \|V\|max | `^(F) (F) (F)  vals$` | `6.4000000000e-02 3.1790275927e+00 5.8007330111e+00  vals` | `cilia.udf`, every `diagInterval` steps (1) |
| wall: time + 8 wall integrals | `^(F) (?:(F) ){7}(F)  wall$` (9 numbers) | `6.4000000000e-02 6.6771494341e-03 8.5506681822e-04 -2.0726461384e+04 ... wall` | `cilia.udf` |
| rod test line (rod test only) | `^(F) (F) (F) (F) (F)  rod$` | | `cilia.udf` |
| panel dump (`dumpPanelSteps>0` only) | `^panel (\d+) (F) (\d+) (\d+)( F)+$`, and `^panel_cext (\d+)( \S+)+$` | | `cilia.udf`; big, off in production |
| setup banner | `^cilia: (.*)$` | `cilia: couplingScheme = iqn  tol = 1e-05  maxIter = 50  omega = 0.2  reuse = 8  filter = 0.001; ...` | `cilia.udf` |

`vals` ordering vs nekRS: the udf prints `vals`/`wall` (and `iqn`) **before** the step's solver block of the same step (udfExecuteStep runs at the start); in the logs `iqn`, `vals`, `wall` precede `step=N FLUID p`. Do not assume `t=` line comes first.

Physics sanity (not a threshold proposal, just what to flag): `vals` 2nd field `ubar` and 3rd `|V|max` going `nan`/`inf` or >1e3 are the udf-level blow-up signals; in the diverging run `|V|max` was 4.06e+02 and ubar 3.15 at t=0.256, versus ubar about 3 and |V|max about 6 healthy.

## 4. Failures

### nekRS exception (`nekrsCheck` / `nekrsAbort`)

Macro: `N/src/platform/nekrsSys.hpp.in:110-157`. Without cpptrace (the build used here: `ENABLE_CPPTRACE OFF`, N/CMakeLists.txt:157) the thrown text is `"Aborting in <file>:L<line>\n<func>:\n<message>"`. Real, from the diverging run (install path shortened):

```
Aborting in <nekRS>/src/app/nrs/nrs.cpp:L1152
printStepInfo:
Unreasonable FLUID CFL (value: 118.742)!

--------------------------------------------------------------------------
MPI_ABORT was invoked on rank 0 in communicator MPI_COMM_WORLD
with errorcode 1.
```

| Signal | Regex | Source |
|---|---|---|
| nekRS aborted (any `nekrsCheck`) | `^Aborting in (\S+):L(\d+)$` (next two lines: function, message) | nekrsSys.hpp.in:130 |
| CFL blow-up / NaN / Inf CFL | `^Unreasonable FLUID CFL \(value: (\S+)\)!$` (value may be `nan` / `inf`) | nrs.cpp:1150-1156: fires if `cfl > 100` (with active fields) or `isnan(cfl)` or `isinf(cfl)`; disable only with `CHECK FLUID CFL = FALSE` |
| Non-finite residual | `unreasonable initial residual norm!` ; `invalid resiual norm while running linear solver!` | cg.hpp:84, 346, 440; gmres.hpp:59, 467 |
| MPI abort wrapper | `^MPI_ABORT was invoked on rank (\d+) in communicator (\S+)$` (Open MPI, hpcx 2.13.1) | seen in 2 real logs |
| Exit code | `^finished with exit code (-?\d+)$` is **absent** on an abort (the exception path never reaches `finalize`, N/src/lib/nekrs.cpp:699); present with `0` on success. Missing line + `step=` lines stopped = abnormal end. | a normal run ends with it; the diverging run does not |

NaN/Inf: there is no dedicated NaN printf in v26. A NaN in the flow shows up as `CFL= nan` (printf `%.3f` of NaN gives `nan` or `-nan`) just before the abort, and in `divUErr`. In the udf, NaN would appear as `nan`/`-nan` in `vals`/`wall`/`iqn`. Regex for any: `(?i)(?<![A-Za-z])-?(nan|inf)(?![A-Za-z])` applied only to lines that do NOT start with `<<<` (the `.par`/udf echo contains the words "inf" in comments, e.g. "f_c = inf"). No real NaN line in any log (the CFL guard aborts at `> 100` first), so the exact NaN printf text is from the C library, unverified.

### UDF_Setup / build failures

- Build failure: `nekrsCheck(err, ..., "see %s for more details\n", cmake.log)`, N/src/core/udf/udf.cpp:218, so the log gets `Aborting in .../udf.cpp:L218`, then `udfBuild:` (function name unverified), then `see <cache>/udf/cmake.log for more details`. Compiler errors go to that `cmake.log`, not the job log. Success marker: `[100%] Built target udf` then `done (10.4674s)`.
- The udf's own checks (`cilia.udf`, `nekrsCheck(!relaxCN && ...)`) go through the same `Aborting in ...` form. Others are plain `printf`/`cerr` then `std::abort()`:
  - `^\[ERROR\] r_cut must be below half the box for the minimum image$` (`cilia.udf`)
  - `^\[ERROR\] wall integrals need axis-aligned genbox elements \(element (\d+)\)$` (`cilia.udf`)
  - `^\[ERROR\] (\S+) not found!$` (`cilia.udf`, goes to stderr; with `-o` only, stderr is also in the `.out` if the script does not split it)
  - `^cilia: WARNING no matching (\S+) for restart at t = (F)` (`cilia.udf`, non-fatal, restart without force history)
  - Careful: these `[ERROR]` strings also occur in the udf echo block as `<<<         printf("[ERROR] ...` in every log (65 + 60 + 59 hits). Always exclude lines starting with `<<<`, or anchor with `^\[ERROR\]`.
- A `std::abort()` gives `SIGABRT`; Open MPI then prints `mpirun noticed that process rank 0 ... exited on signal 6 (Aborted).` (generic Open MPI text, no real example in our logs).

### Segfault / MPI-level

No segfault or `mpirun noticed` line exists in any of our logs; the strings below are from Open MPI / glibc convention, unverified here: `^\[.*\] \*\*\* Process received signal \*\*\*$`, `Signal: Segmentation fault \(11\)`, `mpirun noticed that process rank (\d+) with PID (\d+) on node (\S+) exited on signal (\d+)`. nekRS installs its own handlers only for the update-file signal (driver.cpp `sig_processUpdFile`).

### SLURM

Only one SLURM text is observed in real logs (a manual `scancel`, twice):

```
[2026-10-29T05:33:24.261] error: *** JOB <id> ON <node> CANCELLED AT 2026-10-29T05:33:24 DUE to SIGNAL Terminated ***
```

Regex: `^\[(\S+)\] error: \*\*\* JOB (\d+) ON (\S+) CANCELLED AT (\S+) DUE to (.+?) \*\*\*$`. Reason field: `SIGNAL Terminated` = scancel. Standard Slurm (slurmstepd) texts, from Slurm convention, **not observed in our logs, so mark unverified**: time limit `DUE TO TIME LIMIT` (same line form: `CANCELLED AT ... DUE TO TIME LIMIT ***`), preemption `DUE TO PREEMPTION`, node failure `DUE TO NODE FAILURE`, host OOM `slurmstepd: error: Detected 1 oom_kill event in StepId=... Some of the step tasks have been OOM Killed.`, and `srun: error: <node>: task N: Out Of Memory`. One regex catching all the cancel forms: `\*\*\* JOB (\d+) ON (\S+) CANCELLED AT (\S+) DUE (?i:to) (.+?) \*\*\*`. GPU OOM is not a SLURM event: it is an OCCA/CUDA error from nekRS (text not seen in any log; `occa max memory usage:` is printed at the end of a good run, `N/src/...` runtime stats).
Time limit and `sacct` State (`TIMEOUT`, `OUT_OF_MEMORY`, `FAILED`, `CANCELLED`) are more reliable than log text: add `sacct -j <id> -o State,ExitCode,Elapsed,MaxRSS` to the watcher.

### Sequence-script markers (batch jobs that run several cases)

Our batch wrappers echo `=== <case> <date>` and `=== <case> done <date>, exit <rc>`; these are our own markers, not nekRS output. Regex: `^=== (\S+) done .*, exit (\d+)$`. Real: `=== small4_iqn done Thu Oct 29 05:32:39 MST 2026, exit 1` (a case that failed with exit 1 while the job continued). These batch logs hold only the `grep ' vals$' | tail -1` tail of each case, not the full output (the full output goes to `$CASE.out`).

## 5. Noise volume (bytes and lines per timestep)

Measured on real full logs (each step = one `elapsedStep` line):

| Log | Setup | Size | Steps | Bytes/step | Lines/step |
|---|---|---|---|---|---|
| Run A | Stokes, no IQN, small4 | 1,184,763 B, 15,404 lines (about 100 KB is header/udf echo/AMG tables) | 1000 | about 1.08 KB | about 15 (`vals` + `wall` + 5 solve + 4 proj + div + t + elapsed + `::`) |
| Run B | IQN, about 2.4 correctors/step | 4,707,257 B, 59,728 lines | 2000 | about 2.35 KB | about 30 (each corrector repeats the 10-line solver block) |
| Run C | IQN, longer | 35.8 MB | | | |

So plan for about 1 to 3 KB and 15 to 30 lines per step. A 2-cycle run at dt 1e-3 (2000 steps) is about 5 MB. A 50-corrector IQN step (maxIter) is about 50 x 1 KB = 50 KB. Header (setup, udf echo, Hypre/AMG tables, compilation) is about 100 KB, once. Panel dumps (`dumpPanelSteps`) would add one line per panel per forcing call; they are off in production. `nekRS` also prints the `runtime statistics` block (about 1.5 KB) only at the end (and every `runTimeStatFreq` steps if set).

Consequence for a watcher: `tail -3` shows only `::`, `elapsedStep` and a `vals`/`wall` fragment; one grep pass should pull just: the last `step=.*t=.*CFL=` line, the last `elapsedStep` line, `Aborting in`, `Unreasonable`, `MPI_ABORT`, `CANCELLED`, `finished with exit code`, plus `iqn` lines where field 2 == 50.

## 6. Validation

A test script (scratchpad, not kept) ran the regexes in this file against four logs, including the diverging run. Counts: step 4907, elapsed 2128, solve 19374, proj 19344, divUErr 4908, vals 2136, wall 2131, iqn 2003, Discard 61, `Aborting in` 1, `Unreasonable` 1, `MPI_ABORT` 1, `CANCELLED` 1, `finished with exit code` 1, `=== ... done` 5. No line was matched by two regexes and the counts agree with `grep -c`.
Gaps (could not verify from real logs): NaN text, segfault text, SLURM time-limit / OOM text, GPU OOM text, `adjustDt` verbose line, build-failure text. Each is marked above.
