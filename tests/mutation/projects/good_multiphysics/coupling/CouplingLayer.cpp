# Centralized coupling layer
# All coupling logic concentrated here

class Field {
public:
    double* data;
};

class CouplingLayer {
public:
    // standardized data structure
    void exchangeField(Field& f) {
        // bidirectional data exchange
        // one exchange per time step
        // coupling convergence control
        double residual = 1e-8;
        double tolerance = 1e-6;
    }

    void syncTimeStep() {}

    void mapField(mesh* m) {}
};
