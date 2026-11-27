#include <petscksp.h>

#if PETSC_VERSION_MAJOR >= 3
void solveSystem() {
    PetscErrorCode ierr;
    KSP ksp;
    Vec x;
    ierr = KSPCreate(PETSC_COMM_WORLD, &ksp); CHKERRQ(ierr);
    ierr = KSPSolve(ksp, x, x); CHKERRQ(ierr);
}
#endif
