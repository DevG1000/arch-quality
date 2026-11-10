#include <mpi.h>

void partition_bad() {
  refineLocally();                 // non-uniform signal
  METIS_PartGraphKway(0);          // partition API, no weights -> HPC-008
}
