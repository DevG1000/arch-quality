class MatShape {
public:
    TopoDS_Shape inner() const { return shape_; }
    static MatShape wrap(const TopoDS_Shape& s) { return MatShape(s); }
    int NbChildren() const { return 1; }
private:
    MatShape(const TopoDS_Shape& s) : shape_(s) {}
    TopoDS_Shape shape_;
};