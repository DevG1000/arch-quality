class MatShape {
public:
    TopoDS_Shape inner() const;
    static MatShape wrap(const TopoDS_Shape& s);
};
