// The distributed iqn path on a box mesh of linear elements split among the ranks (partitions as in
// driver_halo.cpp / driver_kin.cpp). ciliaPreFluid / ciliaConverged run a synthetic coupled problem: u at the own
// panels = background shear + the regularised-Stokeslet flow (width epsFlow) of the F of ALL panels, summed in global
// panel order (allgathered), so the problem is the same for any rank count. Per step the converged global F goes to a
// file (compare ranks with cmp.py) and, every 5th step and the last, two checks run:
//   halo:  o_fl (local layout) holds the global F of every local cilium, bitwise;
//   spread: o_JwF (fused JwF0 + spread of the local panels, JwF0 = 0) vs a brute-force sum over ALL panels at every
//           local mesh node, max |diff| / max |brute| < 1e-12.
// Usage: mpirun -np R ./t_dist <coordinates|synthetic9> <x0> <x1> <y0> <y1> <nelx> <nely> <nelz> <slab|block|scatter>
//        <steps> <couplingRestart> <couplingTol> <couplingReuse> <F.bin> [restartTest]
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

// All ranks: the own-layout host slice (nc per panel) of every rank placed in global panel order
std::vector<dfloat> allgatherOwn(const std::vector<dfloat> &slice, int nc) {
  const size_t w = (size_t)N_p * nc;
  std::vector<int> cnt(nRanks, 0), disp(nRanks + 1, 0);
  for (int k = 0; k < N_cilia; k++) cnt[ciliumOwner[k]] += w;
  for (int r = 0; r < nRanks; r++) disp[r + 1] = disp[r] + cnt[r];
  std::vector<dfloat> all(disp[nRanks]), out((size_t)N_cilia * w);
  MPI_Allgatherv(slice.data(), (int)slice.size(), MPI_DFLOAT, all.data(), cnt.data(), disp.data(), MPI_DFLOAT, MPI_COMM_WORLD);
  std::vector<int> next(disp.begin(), disp.end() - 1);
  for (int k = 0; k < N_cilia; k++) {
    const int r = ciliumOwner[k];
    std::copy(all.begin() + next[r], all.begin() + next[r] + w, out.begin() + (size_t)k * w);
    next[r] += w;
  }
  return out;
}

static dfloat epsFlow = 0.13, gainScale = 1.0;
void mockEval(dfloat *u) {
  std::vector<dfloat> xs(3 * nOwnPanels), fs(3 * nOwnPanels);
  if (nOwnPanels > 0) { o_xo.copyTo(xs.data(), xs.size()); o_f.copyTo(fs.data(), fs.size()); }
  const std::vector<dfloat> XG = allgatherOwn(xs, 3), FG = allgatherOwn(fs, 3);
  const dfloat e0 = epsilon;
  for (int i = 0; i < nOwnPanels; i++) {
    const dfloat *X = xs.data();
    dfloat us[3] = {(dfloat)(0.05 * X[i*3 + 2]), 0.0, 0.0};   // background shear
    for (int j = 0; j < N_part; j++) {
      dfloat d[3], r = 0;
      for (int c = 0; c < 3; c++) { d[c] = X[i*3 + c] - XG[j*3 + c]; r += d[c]*d[c]; }
      r = sqrt(r);
      epsilon = epsFlow;
      dfloat a, b; regStokeslet(r, a, b);
      epsilon = e0;
      dfloat Fd = 0; for (int c = 0; c < 3; c++) Fd += FG[j*3 + c] * d[c];
      for (int c = 0; c < 3; c++) us[c] += gainScale * (a * FG[j*3 + c] + (r > 0 ? b * Fd * d[c] / (r*r) : 0)) / mu_hat;
    }
    for (int c = 0; c < 3; c++) u[i + c * nQ] = us[c];
  }
}

int main(int argc, char **argv) {
  MPI_Init(&argc, &argv);
  int rank; MPI_Comm_rank(MPI_COMM_WORLD, &rank); MPI_Comm_size(MPI_COMM_WORLD, &R);
  const std::string coordArg = argv[1];
  X0 = atof(argv[2]); X1 = atof(argv[3]); Y0 = atof(argv[4]); Y1 = atof(argv[5]);
  NX = atoi(argv[6]); NY = atoi(argv[7]); NZ = atoi(argv[8]);
  const std::string m = argv[9];
  mode = m == "slab" ? 0 : m == "block" ? 1 : 2;
  const int steps = atoi(argv[10]);
  couplingRestart = atoi(argv[11]);
  couplingTol = atof(argv[12]);
  couplingReuse = atoi(argv[13]);
  const char *outName = argv[14];

  N_p = 20; epsilon = 0.1; rcutFactor = 3.4; kernel2 = 1; binWidth = 0.5;
  if (coordArg == "synthetic9") {   // 9 cilia on a 3 x 3 grid of spacing 0.5, jittered
    std::mt19937 g(1);
    std::uniform_real_distribution<double> U(0, 1);
    for (int k = 0; k < 9; k++) { xc.push_back(0.5 * (k % 3) + 0.1 * U(g)); yc.push_back(0.5 * (k / 3) + 0.1 * U(g)); beta_c.push_back(0.4 * (U(g) - 0.5)); N_cilia++; }
  } else {
    std::ifstream in(coordArg);
    dfloat x, y, b;
    while (in >> x >> y >> b) { xc.push_back(x); yc.push_back(y); beta_c.push_back(b); N_cilia++; }
  }
  N_part = N_cilia * N_p;
  mu_hat = 1e-3; subtractSelfFlow = 1; panelLength = "arclength";
  couplingScheme = "iqn"; couplingIQN = true; relaxNone = true; relaxScheme = "none"; couplingMaxIter = 50;
  ciliaBinning = 1; binningCheck = 0;
  const dfloat pi = 4.0 * atan(1.0);
  C_par = 2.0 * pi / log(slenderness); C_perp = 2 * C_par; l_panel = L_c / N_p;
  epsinv2 = 1.0 / (epsilon * epsilon);
  rcut2 = (rcutFactor * epsilon) * (rcutFactor * epsilon);
  invnorm = 1.0 / (epsilon * epsilon * epsilon * pow(pi, 1.5));

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
  auto up = [&](occa::memory &o, const std::vector<dfloat> &v) { o = platform->device.malloc<dfloat>(std::max<size_t>(v.size(), 1)); o.copyFrom(v.data(), v.size()); };
  up(mesh->o_x, x); up(mesh->o_y, y); up(mesh->o_z, z);
  up(mesh->o_Jw, std::vector<dfloat>(x.size(), 1.0));
  xmin = platform->linAlg->min(mesh->Nlocal, mesh->o_x, MPI_COMM_WORLD);
  ymin = platform->linAlg->min(mesh->Nlocal, mesh->o_y, MPI_COMM_WORLD);
  Lx = platform->linAlg->max(mesh->Nlocal, mesh->o_x, MPI_COMM_WORLD) - xmin;
  Ly = platform->linAlg->max(mesh->Nlocal, mesh->o_y, MPI_COMM_WORLD) - ymin;
  interp = new pointInterpolation_t(mesh, MPI_COMM_WORLD);
  f_old.assign(N_part * 3, 0.0); fstar_old.assign(N_part * 3, 0.0);

  setupBins();
  setupOwnership();
  setupDeviceKinematics(localCilia);
  setupDistributedIqn();

  const long off = std::max<long>(mesh->Nlocal, 1);
  nrs->fluid->fieldOffset = off;
  nrs->o_coeffEXT = platform->device.malloc<dfloat>(3);
  nrs->fluid->o_JwF = platform->device.malloc<dfloat>(3 * off);
  nrs->fluid->o_U = platform->device.malloc<dfloat>(3 * off);
  platform->linAlg->fill(3 * off, 0.0, nrs->fluid->o_JwF);
  const double dt = 1e-3;
  FILE *fo = rank == 0 ? fopen(outName, "wb") : nullptr;
  dfloat worstSpread = 0, worstHalo = 0;
  int nChecks = 0;
  for (int s = 1; s <= steps; s++) {
    const double t = s * dt;
    dfloat c[3] = {1, 0, 0};
    if (s == 2) { c[0] = 2; c[1] = -1; }
    if (s >= 3) { c[0] = 3; c[1] = -3; c[2] = 1; }
    nrs->o_coeffEXT.copyFrom(c, 3);
    platform->linAlg->fill(3 * off, 0.0, nrs->fluid->o_JwF);   // makeForcing's cilia-free o_JwF
    for (int it = 1; ; it++) {
      nrs->outerCorrector = it;
      ciliaPreFluid(t, s);
      if (ciliaConverged(it)) break;
    }
    std::vector<dfloat> Fown(3 * nOwnPanels);
    if (nOwnPanels > 0) o_f.copyTo(Fown.data(), Fown.size());
    const std::vector<dfloat> FG = gatherOwnToRoot(Fown, 3);
    if (rank == 0) fwrite(FG.data(), sizeof(dfloat), FG.size(), fo);

    if (s % 5 == 0 || s == steps) {
      nChecks++;
      std::vector<dfloat> XG = allgatherOwn([&] { std::vector<dfloat> v(3 * nOwnPanels); if (nOwnPanels > 0) o_xo.copyTo(v.data(), v.size()); return v; }(), 3);
      std::vector<dfloat> FA = allgatherOwn(Fown, 3);
      // halo: o_fl of the local layout vs the global F
      std::vector<dfloat> fl(3 * kinPanels);
      if (kinPanels > 0) o_fl.copyTo(fl.data(), fl.size());
      dfloat dh = 0;
      for (size_t kk = 0; kk < localCilia.size(); kk++)
        for (int e = 0; e < 3 * N_p; e++)
        {
          const dfloat de = std::abs(fl[kk * 3 * N_p + e] - FA[(size_t)localCilia[kk] * 3 * N_p + e]);
          dh = std::max(dh, de == de ? de : (dfloat)INFINITY);   // a NaN (never filled) counts as a failure
        }
      worstHalo = std::max(worstHalo, dh);
      // spread: fused JwF vs brute force over all panels at the local nodes
      std::vector<dfloat> jw(3 * off);
      nrs->fluid->o_JwF.copyTo(jw.data(), jw.size());
      dfloat err = 0, ref = 0;
      for (long id = 0; id < mesh->Nlocal; id++) {
        dfloat f3[3] = {0, 0, 0};
        for (int i = 0; i < N_part; i++) {
          dfloat dy = y[id] - XG[i*3 + 1]; dy -= Ly * std::floor(dy / Ly + 0.5);
          dfloat dx = x[id] - XG[i*3 + 0]; dx -= Lx * std::floor(dx / Lx + 0.5);
          dfloat dz = z[id] - XG[i*3 + 2];
          const dfloat r2 = dx*dx + dy*dy + dz*dz;
          if (dy*dy >= rcut2 || dx*dx >= rcut2 - dy*dy || dz*dz >= rcut2 - dy*dy - dx*dx) continue;
          dfloat delta = exp(-r2 * epsinv2) * invnorm;
          delta *= 2.5 - r2 * epsinv2;
          for (int c = 0; c < 3; c++) f3[c] += FA[i*3 + c] * delta;
        }
        for (int c = 0; c < 3; c++) {
          const dfloat de = std::abs(jw[id + c * off] - f3[c]);
          err = std::max(err, de == de ? de : (dfloat)INFINITY);
          ref = std::max(ref, std::abs(f3[c]));
        }
      }
      dfloat er[2] = {err, ref};
      MPI_Allreduce(MPI_IN_PLACE, er, 1, MPI_DFLOAT, MPI_MAX, MPI_COMM_WORLD);
      MPI_Allreduce(MPI_IN_PLACE, er + 1, 1, MPI_DFLOAT, MPI_MAX, MPI_COMM_WORLD);
      worstSpread = std::max(worstSpread, er[1] > 0 ? er[0] / er[1] : er[0]);
    }
  }
  if (rank == 0) fclose(fo);
  MPI_Allreduce(MPI_IN_PLACE, &worstHalo, 1, MPI_DFLOAT, MPI_MAX, MPI_COMM_WORLD);
  const bool ok = worstHalo == 0 && worstSpread < 1e-12;
  if (rank == 0)
    printf("R=%d %s: %d steps, %d checks; halo F max diff %.1e, fused spread vs brute max rel diff %.2e  %s\n", R,
           m.c_str(), steps, nChecks, worstHalo, worstSpread, ok ? "PASS" : "FAIL");
  MPI_Finalize();
  return ok ? 0 : 1;
}
