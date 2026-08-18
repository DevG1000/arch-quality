# Structural mechanics solver module
# Boundary: independent compile unit

class StructuralSolver {
public:
    virtual void solve() = 0;
    virtual ~StructuralSolver() {}
protected:
    double stiffness;  // internal data, not exposed
};
