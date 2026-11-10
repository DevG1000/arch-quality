#include <mpi.h>

void residual_loop(const double* a, int n, int maxIter) {
  double loc = 0.0, glob = 0.0;
#pragma omp parallel for reduction(+:loc)
  for (int i = 0; i < n; ++i) loc += a[i];
  for (int iter = 0; iter < maxIter; ++iter) {
    MPI_Allreduce(&loc, &glob, 1, MPI_DOUBLE, MPI_SUM, MPI_COMM_WORLD);
  }
}
