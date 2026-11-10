#include <mpi.h>

MPI_Comm split_comm(int color) {
  MPI_Comm sub;
  MPI_Comm_split(MPI_COMM_WORLD, color, 0, &sub);
  return sub;
}

void exchange(double* sbuf, double* rbuf, int n, int left, int right) {
  MPI_Request req[2];
  MPI_Isend(sbuf, n, MPI_DOUBLE, right, 0, MPI_COMM_WORLD, &req[0]);
  MPI_Irecv(rbuf, n, MPI_DOUBLE, left, 0, MPI_COMM_WORLD, &req[1]);
  MPI_Waitall(2, req, MPI_STATUSES_IGNORE);
}
