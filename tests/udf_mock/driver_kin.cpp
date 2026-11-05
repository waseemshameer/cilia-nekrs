// Device kinematics + device binning vs the host versions, on the same box mesh and partitions as
// driver_halo.cpp. Per rank, for the device layout = all cilia and = this rank's localCilia, at nPhase times
// (half a grid over one beat, half random in [0, 200)): kinematicsCompare (x, V, t l, wrapped points; binStart and
// binPanel identical) and o_binLost = 0 (no panel outside its footprint).
// Usage: mpirun -np R ./t_kin <coordinates> <x0> <x1> <y0> <y1> <nelx> <nely> <nelz> <slab|block|scatter> <nPhase>
//        <fb|rod> <arclength|uniform> [rodAxis]
#include <random>
static dfloat X0, X1, Y0, Y1, Z1 = 1.5;
static int NX, NY, NZ, R, mode;

int elemRank(int ix, int iy, int iz) {
  if (mode == 0) return ((ix + NX / (2 * R)) % NX) * R / NX;
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
  kinematics = argv[11];
  panelLength = argv[12];
  if (argc > 13) rodAxis = argv[13];

  N_p = 20; epsilon = 0.1; rcutFactor = 3.8; kernel2 = 1; binWidth = 0.5;
  {
    std::ifstream in(coordinatesFile);
    dfloat x, y, b;
    while (in >> x >> y >> b) { xc.push_back(x); yc.push_back(y); beta_c.push_back(b); N_cilia++; }
  }
  N_part = N_cilia * N_p;
  l_panel = L_c / N_p;
  epsinv2 = 1.0 / (epsilon * epsilon);
  rcut2 = (rcutFactor * epsilon) * (rcutFactor * epsilon);

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
  o_xpc = platform->device.malloc<dfloat>(N_part * 3);
  o_V = platform->device.malloc<dfloat>(N_part * 3);
  o_TL = platform->device.malloc<dfloat>(N_part * 4);
  o_px = platform->device.malloc<dfloat>(N_part);
  o_py = platform->device.malloc<dfloat>(N_part);
  o_pz = platform->device.malloc<dfloat>(N_part);

  setupBins();
  setupOwnership();
  std::vector<int> all(N_cilia);
  for (int k = 0; k < N_cilia; k++) all[k] = k;

  std::mt19937 g(11 + rank);
  std::uniform_real_distribution<double> U(0, 200);
  dfloat worst[4] = {0, 0, 0, 0};
  long diffs = 0, lost = 0, checks = 0, binned = 0;
  for (int layout = 0; layout < 2; layout++) {
    setupDeviceKinematics(layout == 0 ? all : localCilia);
    for (int q = 0; q < nPhase; q++) {
      const double t = (q < nPhase / 2) ? (double)q / (nPhase / 2) : U(g);
      deviceKinematics(t);
      kinematicsCompare(t);
      checks++;
      for (int c = 0; c < 4; c++) worst[c] = std::max(worst[c], kinErr[c]);
      diffs += kinDiff[0] + kinDiff[1];
      std::vector<int> st((size_t)nbx * nby * nbz + 1);
      o_binStart.copyTo(st.data(), st.size());
      binned += st.back() == kinPanels;
    }
    int l = 0;
    o_binLost.copyTo(&l, 1);
    lost += l;
  }
  long tot[3] = {diffs, lost, binned}, sum[3];
  MPI_Allreduce(tot, sum, 3, MPI_LONG, MPI_SUM, MPI_COMM_WORLD);
  MPI_Allreduce(MPI_IN_PLACE, worst, 4, MPI_DFLOAT, MPI_MAX, MPI_COMM_WORLD);
  const bool ok = sum[0] == 0 && sum[1] == 0 && sum[2] == (long)checks * R && worst[0] < 1e-13 && worst[1] < 1e-13 &&
                  worst[2] < 1e-13 && worst[3] < 1e-13;
  if (rank == 0)
    printf("R=%d %s %s %s%s: %ld checks/rank (all + local cilia), max rel diff x %.2e V %.2e tl %.2e p %.2e; bin entries"
           " differing %ld, lost %ld, fully binned %ld/%ld  %s\n", R, m.c_str(), kinematics.c_str(), panelLength.c_str(),
           kinematics == "rod" ? (" " + rodAxis).c_str() : "", checks, worst[0], worst[1], worst[2], worst[3], sum[0],
           sum[1], sum[2], (long)checks * R, ok ? "PASS" : "FAIL");
  MPI_Finalize();
  return ok ? 0 : 1;
}
