# -*- coding: utf-8 -*-
"""
OpenFOAM MMS 验证测试 — scalarTransportFoam + scalarCodedSource

制造解:  u(x,y) = sin(πx)·sin(πy)
PDE:     -∇·(DT·∇T) = S   (DT=1, 稳态, 纯扩散)
源项:    S(x,y) = 2π²·sin(πx)·sin(πy)
理论阶:  2 (二阶中心差分)

每个网格在独立子目录中运行, 避免交叉污染。
"""

import os, math, shutil, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
MESHES = [("coarse", 20, 20), ("medium", 40, 40), ("fine", 80, 80)]

FOAM_BASH = ". /usr/lib/openfoam/openfoam2512/etc/bashrc"

# ── util ────────────────────────────────────────────────


def of_cmd(cmd, cwd, timeout=120):
    """在 WSL bash 中 source OpenFOAM 后执行命令"""
    full = f"{FOAM_BASH} && {cmd}"
    r = subprocess.run(["bash", "-c", full], cwd=cwd,
                       capture_output=True, text=True, timeout=timeout)
    return r


# ── 文件生成 ──────────────────────────────────────────


def write_header(class_, object_):
    lines = [
        "FoamFile",
        "{",
        f'    version     2.0;',
        f'    format      ascii;',
        f'    class       {class_};',
        f'    object      {object_};',
        "}",
    ]
    return "\n".join(lines)


def write_0_T():
    return write_header("volScalarField", "T") + """
dimensions      [0 0 0 0 0 0 0];
internalField   uniform 0;
boundaryField
{
    left    { type fixedValue; value uniform 0; }
    right   { type fixedValue; value uniform 0; }
    bottom  { type fixedValue; value uniform 0; }
    top     { type fixedValue; value uniform 0; }
    frontAndBack { type empty; }
}
"""


def write_0_U():
    return write_header("volVectorField", "U") + """
dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (0 0 0);
boundaryField
{
    left    { type fixedValue; value uniform (0 0 0); }
    right   { type fixedValue; value uniform (0 0 0); }
    bottom  { type fixedValue; value uniform (0 0 0); }
    top     { type fixedValue; value uniform (0 0 0); }
    frontAndBack { type empty; }
}
"""


def write_transport():
    return write_header("dictionary", "transportProperties") + """
DT   DT   [0 2 -1 0 0 0 0] 1.0;
"""


def write_fv_options():
    return write_header("dictionary", "fvOptions") + """

MMSSource
{
    type            scalarCodedSource;
    active          true;
    name            MMSSource;
    selectionMode   all;
    fields          (T);

    codeInclude
    #{
        #include "fvCFD.H"
    #};

    codeAddSup
    #{
        const scalar pi = M_PI;
        const scalarField& V = mesh_.V();
        const vectorField& C = mesh_.C();
        forAll(C, cellI)
        {
            scalar x = C[cellI].x();
            scalar y = C[cellI].y();
            eqn.source()[cellI] -= 2.0*pi*pi * Foam::sin(pi*x) * Foam::sin(pi*y) * V[cellI];
        }
    #};

    codeAddSupRHS
    #{
    #};
    codeSetValue
    #{
    #};
    codeCorrect
    #{
    #};
    codeConstrain
    #{
    #};
}
"""


def write_control():
    return write_header("dictionary", "controlDict") + """
application     scalarTransportFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         1;
deltaT          1;
writeControl    timeStep;
writeInterval   1;
purgeWrite      0;
writeFormat     ascii;
writePrecision  12;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;
"""


def write_fv_schemes():
    return write_header("dictionary", "fvSchemes") + """
ddtSchemes      { default         steadyState; }
gradSchemes     { default         Gauss linear; }
divSchemes      { default         none;
                  div(phi,T)      Gauss linear; }
laplacianSchemes{ default         Gauss linear corrected; }
interpolationSchemes { default    linear; }
snGradSchemes   { default         corrected; }
"""


def write_fv_solution():
    return write_header("dictionary", "fvSolution") + """
solvers
{
    T
    {
        solver          PBiCG;
        preconditioner  DILU;
        tolerance       1e-10;
        relTol          0;
    }
}
SIMPLE { nNonOrthogonalCorrectors 0; }
"""


def write_block_mesh(nx, ny):
    L = 1.0
    hdr = write_header("dictionary", "blockMeshDict")
    return hdr + f"""
convertToMeters 1;
vertices
(
    (0 0 0)
    ({L} 0 0)
    ({L} {L} 0)
    (0 {L} 0)
    (0 0 0.1)
    ({L} 0 0.1)
    ({L} {L} 0.1)
    (0 {L} 0.1)
);
blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} 1) simpleGrading (1 1 1)
);
edges ();
patches
(
    patch left    ( (0 4 7 3) )
    patch right   ( (1 5 6 2) )
    patch bottom  ( (0 1 5 4) )
    patch top     ( (3 7 6 2) )
    empty frontAndBack ( (0 3 2 1) (4 5 6 7) )
);
mergePatchPairs ();
"""


# ── 创建单个网格 case ──────────────────────────────────


def create_case(case_dir, nx, ny):
    """在 case_dir 下创建完整 OpenFOAM case"""
    if os.path.exists(case_dir):
        shutil.rmtree(case_dir)
    os.makedirs(os.path.join(case_dir, "0"))
    os.makedirs(os.path.join(case_dir, "constant"))
    os.makedirs(os.path.join(case_dir, "system"))

    files = {
        "0/T": write_0_T(),
        "0/U": write_0_U(),
        "constant/transportProperties": write_transport(),
        "constant/fvOptions": write_fv_options(),
        "system/controlDict": write_control(),
        "system/fvSchemes": write_fv_schemes(),
        "system/fvSolution": write_fv_solution(),
        "system/blockMeshDict": write_block_mesh(nx, ny),
    }
    for rel, cnt in files.items():
        p = os.path.join(case_dir, rel)
        with open(p, "w") as f:
            f.write(cnt)

    # blockMesh & scalarTransportFoam
    for cmd in ("blockMesh 2>&1", "scalarTransportFoam 2>&1"):
        r = of_cmd(cmd, cwd=case_dir)
        if r.returncode != 0:
            print(f"  [ERROR] '{cmd}' failed")
            print(r.stderr[-400:] if r.stderr else r.stdout[-400:])
            return False
    return True


# ── 读取并计算 L2 误差 ────────────────────────────────


def read_internal_field(path):
    """从 OpenFOAM volScalarField ascii 文件中提取 internalField 的值列表"""
    with open(path) as f:
        text = f.read()

    # 定位 internalField 节
    marker = "internalField   "
    idx = text.find(marker)
    if idx < 0:
        return None

    tail = text[idx + len(marker):].lstrip()

    if tail.startswith("uniform"):
        # uniform <value>;
        val = tail.split()[1].rstrip(";")
        try:
            return [float(val)]
        except:
            return None

    if tail.startswith("nonuniform"):
        # nonuniform List<scalar> N\n(\n...\n);
        paren = tail.find("(")
        if paren < 0:
            return None
        body = tail[paren + 1:]
        end = body.find(")")
        if end < 0:
            return None
        chunk = body[:end]
        vals = []
        for line in chunk.split("\n"):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            for tok in line.split():
                tok = tok.rstrip(";")
                try:
                    vals.append(float(tok))
                except:
                    pass
        return vals

    return None


def compute_l2(case_dir, nx, ny):
    sol_path = os.path.join(case_dir, "1", "T")
    if not os.path.exists(sol_path):
        print(f"  [ERROR] solution not found: {sol_path}")
        return None

    vals = read_internal_field(sol_path)
    if vals is None:
        print(f"  [ERROR] could not parse T field")
        return None

    ncell = nx * ny
    if len(vals) != ncell:
        print(f"  [WARN] read {len(vals)} values, expected {ncell}")
        vals = vals[:ncell]

    L, dx = 1.0, 1.0 / nx
    err = 0.0
    for j in range(ny):
        for i in range(nx):
            idx = j * nx + i
            if idx >= len(vals):
                break
            xc = (i + 0.5) * dx
            yc = (j + 0.5) * dx
            u_exact = math.sin(math.pi * xc) * math.sin(math.pi * yc)
            err += (vals[idx] - u_exact) ** 2
    l2 = math.sqrt(err / ncell)
    return l2


# ── 主流程 ─────────────────────────────────────────────


def main():
    errors, names, hs = [], [], []

    for name, nx, ny in MESHES:
        case_dir = os.path.join(ROOT, f"mms_{name}")
        print(f"[{name}] creating case ({nx}x{ny})...", end=" ")
        ok = create_case(case_dir, nx, ny)
        if not ok:
            print("FAILED")
            return
        print("OK")

        err = compute_l2(case_dir, nx, ny)
        if err is None:
            return
        h = 1.0 / nx
        errors.append(err)
        names.append(name)
        hs.append(h)
        print(f"  h={h:.6f}, L2 error={err:.6e}")

    print("\n" + "=" * 60)
    print("MMS Verification Result")
    print("=" * 60)
    print("  Manufactured solution: u = sin(πx) · sin(πy)")
    print("  Solver: scalarTransportFoam + scalarCodedSource")
    print("  Expected order: 2.0 (2nd order central difference)\n")

    orders = []
    for i in range(1, len(errors)):
        p = math.log(errors[i] / errors[i - 1]) / math.log(hs[i] / hs[i - 1])
        orders.append(p)
        st = "PASS" if abs(p - 2.0) <= 0.1 else "FAIL"
        print(f"  {names[i-1]:>8} -> {names[i]:>8}:  "
              f"p_obs = {p:.3f}  (expected 2.0)  [{st}]")

    if orders:
        pavg = sum(orders) / len(orders)
        all_pass = all(abs(o - 2.0) <= 0.1 for o in orders)
        print(f"\n  Average observed order: {pavg:.3f}")
        print(f"  Overall result: [{'PASS' if all_pass else 'FAIL'}]")
    print("=" * 60)


if __name__ == "__main__":
    main()
