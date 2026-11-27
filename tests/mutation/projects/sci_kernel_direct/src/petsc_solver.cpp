#include <petscksp.h>
#include <petscvec.h>

void solveSystem() {
    KSP ksp;
    Vec x;
    PetscInitialize(nullptr, nullptr, nullptr, nullptr);
    KSPCreate(PETSC_COMM_WORLD, &ksp);
    KSPSolve(ksp, x, x);
}
