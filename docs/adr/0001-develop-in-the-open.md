# Develop all solver code in the open under MIT

All solver code (the udf, its GPU kernels, the cases and the gate) is developed in public under MIT, because nekRS developers, CFD researchers and future employers or funders should be able to read, run and check it, and curated snapshots of private work showed them neither the reasoning nor the history. Development before this point was private and stays unpublished, so the public history starts at v0.1.0 and `git blame` stops at the move, which is why comments have to carry their own reasons.

## Considered options

- **Keep the kernels proprietary and publish the rest.** Rejected, knowing a competitor can reuse the kernels. A reader couldn't then run or check what the docs claim.
- **Keep publishing occasional snapshots.** Rejected: a reader sees a few commits and no reasoning, and tasks and evidence stay out of reach.

## Consequences

- Published code and its history can't be taken back, so leaks are stopped before a push, and anything that gets out is fixed forward with a normal commit.
- Run logs and machine-specific settings aren't published. A result that needs its data gets its own dataset record.
