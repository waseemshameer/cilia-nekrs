# Contributing

This is one developer's project, and I reply when I can.

**Reports.** Open an Issue with the tag or commit, nekRS version, backend and GPU, case, and the relevant log lines.

**Code changes.** Open an Issue first.

**Results.** A change to a listed file (`tools/listed_files.txt`) needs a gate result: run `small4` to t = 2, run `gate.py` (see [docs/running.md](docs/running.md#regression-gate)), and put `Gate: PASS <commit>` in the pull request. The listed files at that commit must match the branch head, or CI fails. CI runs without a GPU, so it can't check answers.

**Comments.** A comment must make sense to someone with no private access. It says what the code does and why, and any number states what it was measured on. It has no task labels, job IDs, node names or cluster names. It links to an Issue, ADR or doc only when the reason won't fit in the comment or the workaround is still open.

**Licence.** Contributions come in under MIT, with no DCO.

## Problems in nekRS itself

These go to [nekRS](https://github.com/Nek5000/nekRS), in public, not by email:

- **Bug:** an Issue, after searching existing ones and reproducing on stock nekRS, with a short case that doesn't need this udf where possible.
- **Question or advice:** a Discussion.
- **Patch:** a pull request to `next`, one change each, per their `CONTRIBUTING.md`. Ask first for anything large.

This repo works around a nekRS problem in the udf first. A patch is the last resort: if the udf can't reach the problem, it's a pull request to `next` plus one file in `patches/` with that pull request's link at the top, deleted in the upgrade that includes the fix.
