#include <mpi.h>

void exchange(float* buf, int n, int right) {
  MPI_Request req;
  MPI_Isend(buf, n, MPI_FLOAT, right, 0, MPI_COMM_WORLD, &req);
  // no Wait/Test -> HPC-005
}
