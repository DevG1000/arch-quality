#include <mpi.h>

void reduce_bad(double* a, int n) {
  double s = 0.0;
#pragma omp parallel
  {
    MPI_Allreduce(&s, &s, 1, MPI_DOUBLE, MPI_SUM, MPI_COMM_WORLD); // HPC-010
  }
}
