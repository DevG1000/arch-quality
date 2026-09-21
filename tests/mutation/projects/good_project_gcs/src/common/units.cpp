double inch_to_mm(double inches) {
    return unit::convert(inches, unit::Inch, unit::MM);
}