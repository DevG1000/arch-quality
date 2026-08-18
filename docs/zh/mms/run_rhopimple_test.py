import sys
sys.path.insert(0, "/mnt/d/opensource/arch-quality/docs/zh/mms")
with open("/mnt/d/opensource/arch-quality/docs/zh/mms/openfoam_rhopimple_mms.py") as f:
    src = f.read()
src = src.replace(
    "coarse\", 10, 10), (\"medium\", 20, 20), (\"fine\", 40, 40",
    "test\", 6, 6"
)
exec(src)
