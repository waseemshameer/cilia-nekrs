# Releasing

## What a version means

**An answer change** is either of these:

1. `small4` at production settings fails `gate.py` against the current reference.
2. The change deliberately alters the model or its resolution (mesh, N, N_p, ε, dt), even if the gate passes.

Everything else, such as speed work or solver tolerances, counts as unchanged if the gate passes. Part 2 exists because a small deliberate change can pass: N_p 40 → 80 scores L2 1.61e-4, inside the production band, yet moves ū by 0.12%.

**Numbers** stay at 0.y.z for now:

- **Patch:** a fix with the same answers and nothing to change on the user's side. A patch never changes answers.
- **Minor:** changed answers, a changed `[CASEDATA]` key or `gate.py` option, a new feature, a speed gain, or a nekRS upgrade.
- **From 1.0:** major means answers changed or something broke, minor means additions and speed, and patch stays the same. 1.0 won't come before the wall-shear limit in the README is settled.

What these promise is declared in ["What stays stable"](running.md#what-stays-stable).

## When to release

There's no calendar and no release per pull request. One of these triggers it:

1. A finished milestone: something a reader can use. Only the next release has an open GitHub milestone, and closing its last Issue means a release is due.
2. A fix for a wrong answer or crash in the latest release, released straight away.
3. A number about to be quoted: a talk, paper or application cites a tag, not a loose commit.

## Steps

1. **Runs,** on commits whose listed files (`tools/listed_files.txt`) match the commit to be tagged:
   - `small4` on 1 GPU at production settings, gated against `cases/small4/reference.out`. The timing comes from this same run. A claimed speed gain also needs back-to-back runs on one node.
   - `tiled8` for 2 cycles at N_p = 40 on 1 and 4 GPUs, same node and commit. `gate.py` on the 4-GPU log with the 1-GPU log as `--ref` must pass, and the report gives corrector counts and capped steps. `small4` can't test the multi-rank cilia code, since on 2 ranks one rank owns all 4 cilia. This costs about 5.1 GPU-h on A100s, because the 1-GPU run holds all 4 GPUs. Same node stays the rule because a split across nodes moved the efficiency from 0.76 to 0.81.
   - A chain can be reused if the listed files match. A docs-only patch needs nothing new.
2. **Changelog:** turn `## Unreleased` into `## vX.Y.Z (YYYY-MM-DD)`, opening with these lines:
   ```
   **Answers:** changed. <what moved, the worst metric, the score against the new reference>
   **Speed:** <s/cycle>, small4, one A100.
   **nekRS:** v26.0 `96b3cf9e`.
   ```
   With unchanged answers the first line reads `**Answers:** unchanged (gate PASS, L2 …, L∞ …)`.
3. **`CITATION.cff`:** update the version and date. From v0.4.0, add the concept DOI once the first record exists.
4. **README speed section:** replace the numbers with those measured at this tag, labelled with the tag. Add no multi-GPU numbers until a release has measured them. Update `docs/performance.md` to match.
5. **Built files:** rebuild `docs/model.pdf` and built figures only if this release changes their content, and commit them only then. Each PDF version adds about 0.6 MB to every clone.
6. **Check,** before the tag, because tags never move:
   ```bash
   python3 tools/check_release.py vX.Y.Z --gate <small4 commit> --multi <tiled8 commit>
   ```
7. **Tag and release:** an annotated tag on `main`, and a GitHub Release whose notes link to the changelog.
8. **DOI:** from v0.4.0, Zenodo creates a DOI from the GitHub Release, with metadata from `CITATION.cff` only. Don't add a `.zenodo.json`, because Zenodo would then ignore `CITATION.cff`. The record is close to permanent. The README and `CITATION.cff` carry the concept DOI, and a specific result cites its version DOI.

Tags never move. A bad release is fixed by a new one, with a note added to the bad one's changelog entry.

## Data

- **No Git LFS.** A tag holds its own reference, so a reader never has a download step.
- **Meshes** over 20 MB are never committed (see [case.md](case.md#meshes)).
- **The reference** is replaced in place, keeping its name, only on an answer change. CI fails if `reference.out` changes without `Answers: changed` in the changelog.
- **Run data** isn't part of a software release. Publishing a dataset is a separate Zenodo record for that one result.

## Upgrading nekRS

Tagged releases only, never tracking `next`, for a named reason stated in the pull request (a fix we need, a feature we'd use, or a speed gain worth testing), and between campaigns, because efficiency numbers only compare on one nekRS version. Update `NEKRS_VERSION`, then:

1. Before any run, read the new `RELEASE.md` and check the [scaling.md](scaling.md) settings against the new parser.
2. Run `small4` at production settings and gate it against the same `reference.out` with the same limits.
3. Run the `tiled8` 1-vs-4-GPU chain above.
4. Run old and new builds back to back on one node for speed. There's no pass line: the numbers go in the pull request.
5. If the gate fails, the reference stays and so does the old version until the cause is traced to a nekRS change. A correct change is an answer change with a new reference. An unexplained one is reported upstream.
6. Every upgrade is at least a minor release, because users have to rebuild nekRS.
7. `fixAlignedAvgNormals()` stays until its log line shows max |n_avg − n| = 0 on the new version, then goes in its own pull request with its own gate.
