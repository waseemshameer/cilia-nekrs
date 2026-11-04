# udf_mock: build the udf on a laptop (no nekRS)

`mock.hpp` stubs the nekRS/OCCA API the udf uses; `okl2cpp.py` turns the OKL kernels into serial C++ (inner loops run
one after the other, so the shared-memory reductions work). Each driver below builds the udf into one test program and
checks one part of the distributed iqn path on a box mesh of linear elements split among the ranks (`slab` in x
wrapping the periodic seam, `block` in x-y, `scatter` = 4 x 4 x 3 chunks hashed to ranks). `mockProc` stands in for
`find()`'s rank.

```bash
python3 okl2cpp.py ../../cilia.udf new_udf.cpp     # once per udf version
```

**Halo check** (`driver_halo.cpp`): `setupBins` + `setupOwnership`. Checks the root owners, that every panel within
r_cut of a rank's element box (half the phases on a grid over the beat, half random) is local there, and
`haloExchange`.

```bash
mpicxx -std=c++17 -O2 -I. -include new_udf.cpp driver_halo.cpp -o t_halo
mpirun --oversubscribe -np 4 ./t_halo ../../cases/tiled8/coordinates_tiled8.txt -4 4 -4 4 80 80 12 block 200
```

**Device kinematics and binning** (`driver_kin.cpp`): same mesh and partitions as `driver_halo.cpp`. For the device
layout = all cilia and = the rank's `localCilia`, at `nPhase` times (half a grid over one beat, half random in
[0, 200)): `deviceKinematics` vs `panelKinematics` + `hostBinSort` via `kinematicsCompare` (x, V, t l, wrapped points;
`binStart`/`binPanel` identical), and `o_binLost = 0`.

```bash
mpicxx -std=c++17 -O2 -I. -include new_udf.cpp driver_kin.cpp -o t_kin
mpirun --oversubscribe -np 4 ./t_kin ../../cases/tiled8/coordinates_tiled8.txt -4 4 -4 4 80 80 12 block 100 fb arclength
mpirun -np 1 ./t_kin ... block 100 rod uniform z      # rod: last argument rodAxis
```

**Distributed IQN** (`driver_dist.cpp`): `setupBins`, `setupOwnership`, `setupDeviceKinematics(localCilia)`,
`setupDistributedIqn`, and `ciliaPreFluid`/`ciliaConverged` for `steps` steps with a synthetic coupled problem (u at
the own panels = shear + the Stokeslet flow of the F of all panels, summed in global order, so it does not depend on
the rank count). Writes the converged global F per step (`F.bin`; `cmp.py a.bin b.bin 3N_part`) and the `iqn` lines
(correctors per step) to the log. Every 5th step: (halo) `o_fl` holds the global F of every local cilium, bitwise;
(spread) the fused `JwF0 + spread` equals a brute-force sum over all panels at every local node. `synthetic9` = 9
cilia on a jittered 3 x 3 grid. F from runs on different rank counts should be bitwise equal wherever the partition
keeps each dot product's sum order.

```bash
mpicxx -std=c++17 -O2 -I. -include new_udf.cpp driver_dist.cpp -o t_dist
mpirun --oversubscribe -np 4 ./t_dist synthetic9 -1 3 -1 3 20 20 6 block 20 8 1e-9 8 F.bin
mpirun --oversubscribe -np 4 ./t_dist ../../cases/tiled4/coordinates_tiled4.txt -2 2 -2 2 40 40 12 block 12 8 1e-8 8 F.bin
```
