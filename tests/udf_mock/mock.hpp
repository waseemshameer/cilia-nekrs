// Minimal nekRS/OCCA mock to build cilia.udf host code + OKL kernels (as serial C++) on the laptop
#pragma once
#include <vector>
#include <string>
#include <memory>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <limits>
#include <tuple>
#include <mpi.h>
// -DNEKRS_USE_DFLOAT_FLOAT builds the udf as nekrs-fp32 does; the same macro switches dfloat in nekRS's nekrsSys.hpp
#ifdef NEKRS_USE_DFLOAT_FLOAT
typedef float dfloat;
#define MPI_DFLOAT MPI_FLOAT
#else
typedef double dfloat;
#define MPI_DFLOAT MPI_DOUBLE
#endif
typedef int dlong;
#define p_Nq 2
#define p_Np 8
using std::min; using std::max;
inline double fmax(double a, double b) { return a > b ? a : b; }
#define nekrsCheck(cond, comm, code, fmt, ...) do { if (cond) { fprintf(stderr, fmt, __VA_ARGS__); std::exit(code); } } while (0)
namespace occa {
struct json {};
struct memory {
  std::shared_ptr<std::vector<char>> buf; size_t esz = 1, cnt = 0;
  bool isInitialized() const { return (bool)buf; }
  size_t size() const { return cnt; }
  template <class T> operator T*() const { return buf ? (T*)buf->data() : nullptr; }
  void copyFrom(const void *src, long count = -1, long off = 0) {
    if (count < 0) count = cnt - off;
    memcpy(buf->data() + off * esz, src, count * esz);
  }
  void copyFrom(const memory &src, long count = -1, long dOff = 0, long sOff = 0) {
    if (count < 0) count = src.cnt - sOff;
    memmove(buf->data() + dOff * esz, src.buf->data() + sOff * src.esz, count * esz);
  }
  void copyTo(void *dst, long count = -1, long off = 0) const {
    if (count < 0) count = cnt - off;
    memcpy(dst, buf->data() + off * esz, count * esz);
  }
};
}
struct Device {
  template <class T> occa::memory malloc(size_t n) {
    occa::memory m; m.esz = sizeof(T); m.cnt = n; m.buf = std::make_shared<std::vector<char>>(n * sizeof(T));
    // poison like uninitialised device memory: all-ones bytes are a NaN in both float and double
    memset(m.buf->data(), 0xFF, n * sizeof(T));
    return m;
  }
  occa::memory malloc(size_t bytes) { return malloc<char>(bytes); }
  void finish() {}
};
struct LinAlg {
  void fill(long n, double v, occa::memory &o) { dfloat *p = o; for (long i = 0; i < n; i++) p[i] = v; }
  dfloat min(long n, occa::memory &o, MPI_Comm c) { dfloat *p = o, m = std::numeric_limits<dfloat>::max(); for (long i = 0; i < n; i++) m = std::min(m, p[i]);
    MPI_Allreduce(MPI_IN_PLACE, &m, 1, MPI_DFLOAT, MPI_MIN, c); return m; }
  dfloat max(long n, occa::memory &o, MPI_Comm c) { dfloat *p = o, m = -std::numeric_limits<dfloat>::max(); for (long i = 0; i < n; i++) m = std::max(m, p[i]);
    MPI_Allreduce(MPI_IN_PLACE, &m, 1, MPI_DFLOAT, MPI_MAX, c); return m; }
  double maxAbsoluteError(long, int, long, double, occa::memory &, occa::memory &, MPI_Comm) { return 0; }
  double amaxMany(long, int, long, occa::memory &, MPI_Comm) { return 0; }
};
struct Comm { MPI_Comm mpiComm() { return MPI_COMM_WORLD; } int mpiRank() { int r; MPI_Comm_rank(MPI_COMM_WORLD, &r); return r; } };
struct Timer { void tic(const std::string &) {} void toc(const std::string &) {} void addUserStat(const std::string &) {} };
struct Par { template <class T> void extract(const char *, const char *, T &) {} };
struct Options { std::string getArgs(const char *) { return ""; } template <class T> void getArgs(const char *, T &v) { v = 1e-3; } };
namespace bdryBase { enum { bcType_zeroDirichletX_zeroNeumann, bcType_zeroDirichletX_udfNeumann, bcType_zeroDirichletY_zeroNeumann,
  bcType_zeroDirichletY_udfNeumann, bcType_zeroDirichletZ_zeroNeumann, bcType_zeroDirichletZ_udfNeumann }; }
struct Bc { int typeId(int, const std::string &) { return -1; } };
struct App { Bc *bc = new Bc; };
struct Platform { Device device; LinAlg *linAlg = new LinAlg; Comm comm; Timer timer; Par *par = new Par; Options options; App *app = new App; };
inline Platform *platform = new Platform;
struct Mesh {
  int dim = 3, Nelements = 0, Np = 8, Nq = 2, Nfaces = 6, Nfp = 4, Nsgeo = 18; long Nlocal = 0; double volume = 1;
  int *EToB = nullptr; dfloat gllz[2] = {-1, 1}, gllw[2] = {1, 1};
  occa::memory o_x, o_y, o_z, o_Jw, o_sgeo;
  std::tuple<std::vector<dfloat>, std::vector<dfloat>, std::vector<dfloat>> xyzHost() { return {}; }
};
struct Fluid { long fieldOffset = 0; occa::memory o_U, o_P, o_JwF, o_ex; std::string velocityName = "velocity";
  occa::memory &o_explicitTerms() { return o_ex; } };
struct Nrs {
  Mesh *meshV = new Mesh; Fluid *fluid = new Fluid; occa::memory o_coeffEXT; double dt[3] = {1e-3, 1e-3, 1e-3};
  int outerCorrector = 1; bool timeStepConverged = true; bool checkpointStep = false;
  void (*userSource)(double) = nullptr; void (*preFluid)(double, int) = nullptr; bool (*userConvergenceCheck)(int) = nullptr;
  void copyToNek(double, int) {} void writeCheckpoint(double, bool) {}
};
inline Nrs *nrs = new Nrs;
struct bcData { double uxFluid, uyFluid, uzFluid; };
inline bool isField(const char *) { return true; }
namespace nek { inline void userchk() {} }
// eval mock: u at the panels = u0 + K F (F = the force applied this corrector, o_f), set by the test driver
void mockEval(dfloat *u);
// find mock: the rank owning point (x, y, z), set by the test driver
int mockProc(dfloat x, dfloat y, dfloat z);
struct FindData { std::vector<int> code, proc; };
struct pointInterpolation_t {
  std::vector<dfloat> px, py, pz; FindData d;
  pointInterpolation_t(Mesh *, MPI_Comm) {}
  void setPoints(occa::memory &, occa::memory &, occa::memory &) { px.clear(); }
  void setPoints(const std::vector<dfloat> &x, const std::vector<dfloat> &y, const std::vector<dfloat> &z) { px = x; py = y; pz = z; }
  void find() { d.code.assign(px.size(), 0); d.proc.resize(px.size()); for (size_t i = 0; i < px.size(); i++) d.proc[i] = mockProc(px[i], py[i], pz[i]); }
  FindData &data() { return d; }
  void eval(int, long, occa::memory &, int, occa::memory &o_out, int) { mockEval((dfloat *)o_out); }
};
