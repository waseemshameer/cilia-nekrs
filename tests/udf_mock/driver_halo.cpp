// Checks setupOwnership on N ranks with a genbox-like box mesh (linear elements) split among the ranks.
// 1. every root's owner is the rank whose element holds it, and each cilium has exactly one owner;
// 2. brute force over many beat phases: every panel whose min-image distance to an element's bounding box is below
//    r_cut is local on that element's rank (the bounding box contains every GLL node, so this is stricter);
// 3. haloExchange delivers each halo cilium's entries from its owner.
// Usage: mpirun -np R ./t_halo <coordinates> <x0> <x1> <y0> <y1> <nelx> <nely> <nelz> <slab|block|scatter> <nPhase>
#include <random>
static dfloat X0, X1, Y0, Y1, Z1 = 1.5;
static int NX, NY, NZ, R, mode;   // mode 0 slab in x, 1 blocks in x-y, 2 scattered 4 x 4 x 3 chunks

int elemRank(int ix, int iy, int iz) {
  if (mode == 0) return ((ix + NX / (2 * R)) % NX) * R / NX;   // shifted, so one slab wraps the periodic seam
  if (mode == 1) {
    int rx = 1; for (int a = 1; a * a <= R; a++) if (R % a == 0) rx = a;
    const int ry = R / rx;
    return (((ix + NX / (2 * rx)) % NX) * rx / NX) * ry + ((iy + NY / (2 * ry)) % NY) * ry / NY;
  }
  unsigned h = (unsigned)(ix / 4) * 73856093u ^ (unsigned)(iy / 4) * 19349663u ^ (unsigned)(iz / 3) * 83492791u;
  return h % R;
}
int mockProc(dfloat x, dfloat y, dfloat z) {
  const int ix = std::clamp((int)std::floor((x - X0) / (X1 - X0) * NX), 0, NX - 1);
  const int iy = std::clamp((int)std::floor((y - Y0) / (Y1 - Y0) * NY), 0, NY - 1);
  const int iz = std::clamp((int)std::floor(z / Z1 * NZ), 0, NZ - 1);
  return elemRank(ix, iy, iz);
}
void mockEval(dfloat *) {}

int main(int argc, char **argv) {
  MPI_Init(&argc, &argv);
  int rank; MPI_Comm_rank(MPI_COMM_WORLD, &rank); MPI_Comm_size(MPI_COMM_WORLD, &R);
  coordinatesFile = argv[1];
  X0 = atof(argv[2]); X1 = atof(argv[3]); Y0 = atof(argv[4]); Y1 = atof(argv[5]);
  NX = atoi(argv[6]); NY = atoi(argv[7]); NZ = atoi(argv[8]);
  const std::string m = argv[9];
  mode = m == "slab" ? 0 : m == "block" ? 1 : 2;
  const int nPhase = atoi(argv[10]);

  // Production model settings (cases/tiled2/tiled2.par)
  N_p = 20; epsilon = 0.1; rcutFactor = 3.8; kernel2 = 1; panelLength = "arclength"; binWidth = 0.5;
  {
    std::ifstream in(coordinatesFile);
    dfloat x, y, b;
    while (in >> x >> y >> b) { xc.push_back(x); yc.push_back(y); beta_c.push_back(b); N_cilia++; }
  }
  N_part = N_cilia * N_p;
  const dfloat pi = 4.0 * atan(1.0);
  epsinv2 = 1.0 / (epsilon * epsilon);
  rcut2 = (rcutFactor * epsilon) * (rcutFactor * epsilon);
  const dfloat rcut = sqrt(rcut2);

  // This rank's elements, 8 corner nodes each
  auto mesh = nrs->meshV;
  std::vector<dfloat> x, y, z;
  const dfloat hx = (X1 - X0) / NX, hy = (Y1 - Y0) / NY, hz = Z1 / NZ;
  for (int iz = 0; iz < NZ; iz++)
    for (int iy = 0; iy < NY; iy++)
      for (int ix = 0; ix < NX; ix++) {
        if (elemRank(ix, iy, iz) != rank) continue;
        for (int c = 0; c < 8; c++) {
          x.push_back(X0 + (ix + (c & 1)) * hx);
          y.push_back(Y0 + (iy + ((c >> 1) & 1)) * hy);
          z.push_back((iz + ((c >> 2) & 1)) * hz);
        }
        mesh->Nelements++;
      }
  mesh->Nlocal = x.size();
  mesh->o_x = platform->device.malloc<dfloat>(std::max<size_t>(x.size(), 1)); mesh->o_x.copyFrom(x.data(), x.size());
  mesh->o_y = platform->device.malloc<dfloat>(std::max<size_t>(y.size(), 1)); mesh->o_y.copyFrom(y.data(), y.size());
  mesh->o_z = platform->device.malloc<dfloat>(std::max<size_t>(z.size(), 1)); mesh->o_z.copyFrom(z.data(), z.size());
  xmin = platform->linAlg->min(mesh->Nlocal, mesh->o_x, MPI_COMM_WORLD);
  ymin = platform->linAlg->min(mesh->Nlocal, mesh->o_y, MPI_COMM_WORLD);
  Lx = platform->linAlg->max(mesh->Nlocal, mesh->o_x, MPI_COMM_WORLD) - xmin;
  Ly = platform->linAlg->max(mesh->Nlocal, mesh->o_y, MPI_COMM_WORLD) - ymin;
  interp = new pointInterpolation_t(mesh, MPI_COMM_WORLD);

  setupBins();
  setupOwnership();

  long bad = 0;
  // 1. owners
  for (int k = 0; k < N_cilia; k++) {
    const dfloat rx = xc[k] - Lx * std::floor((xc[k] - xmin) / Lx), ry = yc[k] - Ly * std::floor((yc[k] - ymin) / Ly);
    if (ciliumOwner[k] != mockProc(rx, ry, 0.0)) bad++;
  }
  // 2. brute force: needed on this rank => local
  std::vector<char> isLocal(N_cilia, 0), used(N_cilia, 0);
  for (int k : localCilia) isLocal[k] = 1;
  std::mt19937 g(7 + rank);
  std::uniform_real_distribution<double> U(0, 1);
  long nNeeded = 0, missing = 0;
  dfloat worst = 1e300;   // smallest distance of a needed-but-missing panel (diagnostic)
  for (int q = 0; q < nPhase; q++) {
    const double t = (q < nPhase / 2) ? (double)q / (nPhase / 2) : U(g);
    std::vector<dfloat> xp, V, TL, px, py, pz;
    panelKinematics(t, xp, V, TL, px, py, pz);
    for (int mm = 0; mm < N_part; mm++) {
      const int k = mm / N_p;
      // the grid elements whose box can be within r_cut of the panel (periodic in x, y), then the exact distance
      const int ix0 = (int)std::floor((px[mm] - rcut - X0) / hx), ix1 = (int)std::floor((px[mm] + rcut - X0) / hx);
      const int iy0 = (int)std::floor((py[mm] - rcut - Y0) / hy), iy1 = (int)std::floor((py[mm] + rcut - Y0) / hy);
      const int iz0 = std::max(0, (int)std::floor((pz[mm] - rcut) / hz)), iz1 = std::min(NZ - 1, (int)std::floor((pz[mm] + rcut) / hz));
      bool need = false;
      dfloat dmin = 1e300;
      for (int iz = iz0; iz <= iz1 && !need; iz++)
        for (int jy = iy0; jy <= iy1 && !need; jy++)
          for (int jx = ix0; jx <= ix1 && !need; jx++) {
            const int ix = ((jx % NX) + NX) % NX, iy = ((jy % NY) + NY) % NY;
            if (elemRank(ix, iy, iz) != rank) continue;
            const dfloat lo[3] = {X0 + ix * hx, Y0 + iy * hy, iz * hz};
            dfloat cx = px[mm] - (lo[0] + 0.5 * hx); cx -= Lx * std::floor(cx / Lx + 0.5);
            dfloat cy = py[mm] - (lo[1] + 0.5 * hy); cy -= Ly * std::floor(cy / Ly + 0.5);
            const dfloat dx = std::max((dfloat)0, std::abs(cx) - 0.5 * hx);
            const dfloat dy = std::max((dfloat)0, std::abs(cy) - 0.5 * hy);
            const dfloat dz = std::max((dfloat)0, std::max(lo[2] - pz[mm], pz[mm] - lo[2] - hz));
            const dfloat d2 = dx * dx + dy * dy + dz * dz;
            if (d2 < rcut2) { need = true; dmin = sqrt(d2); }
          }
      if (need) {
        nNeeded++;
        used[k] = 1;
        if (!isLocal[k]) { missing++; worst = std::min(worst, dmin); }
      }
    }
  }
  long nUsed = 0;
  for (int k : localCilia) nUsed += used[k];
  // 3. halo exchange: own entries = id-coded values, halo entries NaN beforehand
  const int nc = 3;
  std::vector<dfloat> v(localCilia.size() * N_p * nc, std::nan(""));
  for (int pos : ownLocal)
    for (int j = 0; j < N_p * nc; j++) v[(size_t)pos * N_p * nc + j] = localCilia[pos] * 1000.0 + j;
  haloExchange(v, nc);
  long badX = 0;
  for (size_t pos = 0; pos < localCilia.size(); pos++)
    for (int j = 0; j < N_p * nc; j++) badX += v[pos * N_p * nc + j] != localCilia[pos] * 1000.0 + j;

  long tot[4] = {bad, missing, badX, nNeeded}, all[4];
  MPI_Reduce(tot, all, 4, MPI_LONG, MPI_SUM, 0, MPI_COMM_WORLD);
  for (int r = 0; r < R; r++) {
    MPI_Barrier(MPI_COMM_WORLD);
    if (r == rank)
      printf("rank %d: elements %d, own %zu, local %zu (needed at some phase %ld), neighbours %zu, missing %ld%s\n", rank,
             mesh->Nelements, ownLocal.size(), localCilia.size(), nUsed, nbrRank.size(), missing,
             missing ? (" (closest " + std::to_string(worst) + ")").c_str() : "");
    fflush(stdout);
  }
  MPI_Barrier(MPI_COMM_WORLD);
  if (rank == 0)
    printf("%s R=%d %s: owner errors %ld, needed-but-not-local %ld (of %ld needed panel-phases), exchange errors %ld  %s\n",
           coordinatesFile.c_str(), R, m.c_str(), all[0], all[1], all[3], all[2],
           (all[0] || all[1] || all[2]) ? "FAIL" : "PASS");
  MPI_Finalize();
  return (all[0] || all[1] || all[2]) ? 1 : 0;
}
