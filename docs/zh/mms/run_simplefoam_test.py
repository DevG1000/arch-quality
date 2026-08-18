"""Run simpleFoam MMS on coarse mesh only (test)"""
import sys, os
sys.path.insert(0, "/mnt/d/opensource/arch-quality/docs/zh/mms")
exec(open("/mnt/d/opensource/arch-quality/docs/zh/mms/openfoam_simplefoam_mms.py").read())

# Manually run just coarse
from openfoam_simplefoam_mms import create_case, compute_l2_U, compute_l2_p

case_dir = "/mnt/d/opensource/arch-quality/docs/zh/mms/simplefoam_mms_coarse"
print("Creating case...")
ok = create_case(case_dir, 20, 20)
print(f"Create: {'OK' if ok else 'FAIL'}")

if ok:
    errU = compute_l2_U(case_dir, 20, 20)
    errP = compute_l2_p(case_dir, 20, 20)
    print(f"L2(U) = {errU:.6e}")
    print(f"L2(p) = {errP:.6e}")
