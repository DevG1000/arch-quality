TEST(Step, RoundTrip) {
    STEPControl_Writer w; w.Write("t.stp");
    STEPControl_Reader r; r.ReadFile("t.stp"); r.TransferRoots();
    ASSERT_EQ(r.OneShape().NbChildren(), 1);
}