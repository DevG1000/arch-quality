# -*- coding: utf-8 -*-
"""
mms_demo.py — MMS 概念验证演示（纯 Python，不依赖 OpenFOAM）

使用有限差分法求解 -laplacian(u) = S，通过 MMS 验证二阶精度。

制造解: u = sin(pi*x) * sin(pi*y)
PDE:    -laplacian(u) = S
源项:   S = 2*pi^2 * sin(pi*x) * sin(pi*y)
理论阶: 2（二阶中心差分）
"""

import math
import sys


def compute_source(x, y):
    """计算制造解对应的源项 S(x,y)"""
    pi = math.pi
    return 2 * pi * pi * math.sin(pi * x) * math.sin(pi * y)


def exact_solution(x, y):
    """制造解 u(x,y) = sin(pi*x) * sin(pi*y)"""
    return math.sin(math.pi * x) * math.sin(math.pi * y)


def solve_laplacian(nx, ny):
    """
    用有限差分法求解 -laplacian(u) = S
    
    二阶中心差分，五点格式。
    边界条件: u = 0 (Dirichlet)
    """
    L = 1.0
    dx = L / nx
    dy = L / ny
    
    # 内部节点数 (nx-1) × (ny-1)
    ni = nx - 1
    nj = ny - 1
    
    # 构建矩阵 A 和右端项 b
    n = ni * nj
    A = [[0.0] * n for _ in range(n)]
    b = [0.0] * n
    
    def idx(i, j):
        return i * nj + j
    
    for i in range(ni):
        for j in range(nj):
            row = idx(i, j)
            x = (i + 1) * dx
            y = (j + 1) * dy
            
            # 中心点系数
            A[row][row] = 2.0 / dx / dx + 2.0 / dy / dy
            b[row] = compute_source(x, y)
            
            # 左邻居
            if i > 0:
                A[row][idx(i - 1, j)] = -1.0 / dx / dx
            else:
                b[row] += exact_solution(0, y) / dx / dx  # 左边界 u=0
            
            # 右邻居
            if i < ni - 1:
                A[row][idx(i + 1, j)] = -1.0 / dx / dx
            else:
                b[row] += exact_solution(L, y) / dx / dx  # 右边界 u=0
            
            # 下邻居
            if j > 0:
                A[row][idx(i, j - 1)] = -1.0 / dy / dy
            else:
                b[row] += exact_solution(x, 0) / dy / dy  # 下边界 u=0
            
            # 上邻居
            if j < nj - 1:
                A[row][idx(i, j + 1)] = -1.0 / dy / dy
            else:
                b[row] += exact_solution(x, L) / dy / dy  # 上边界 u=0
    
    # 高斯-赛德尔迭代求解
    u = [0.0] * n
    for _ in range(10000):
        max_err = 0.0
        for i in range(ni):
            for j in range(nj):
                row = idx(i, j)
                old = u[row]
                s = b[row]
                # 减去邻居项
                if i > 0: s -= A[row][idx(i - 1, j)] * u[idx(i - 1, j)]
                else: s -= 0  # 边界已计入 b
                if i < ni - 1: s -= A[row][idx(i + 1, j)] * u[idx(i + 1, j)]
                if j > 0: s -= A[row][idx(i, j - 1)] * u[idx(i, j - 1)]
                if j < nj - 1: s -= A[row][idx(i, j + 1)] * u[idx(i, j + 1)]
                u[row] = s / A[row][row]
                err = abs(u[row] - old)
                if err > max_err:
                    max_err = err
        if max_err < 1e-12:
            break
    
    return u, ni, nj, dx


def compute_error(u, ni, nj, dx):
    """计算 L2 误差"""
    err = 0.0
    count = 0
    for i in range(ni):
        for j in range(nj):
            x = (i + 1) * dx
            y = (j + 1) * dx
            u_exact = exact_solution(x, y)
            u_num = u[i * nj + j]
            err += (u_num - u_exact) ** 2
            count += 1
    return math.sqrt(err / count)


def main():
    print("=" * 60)
    print("MMS 概念验证演示（纯 Python 实现）")
    print("=" * 60)
    print()
    print("  制造解: u = sin(pi*x) * sin(pi*y)")
    print("  PDE:    -laplacian(u) = S")
    print("  源项:   S = 2*pi^2 * sin(pi*x) * sin(pi*y)")
    print("  理论阶: 2（二阶中心差分）")
    print()
    
    # 多套网格
    grids = [10, 20, 40]
    errors = []
    hs = []
    
    for nx in grids:
        ny = nx
        u, ni, nj, dx = solve_laplacian(nx, ny)
        err = compute_error(u, ni, nj, dx)
        h = 1.0 / nx
        errors.append(err)
        hs.append(h)
        print("  网格 %3d×%-3d  h=%.4f  L2 误差=%.6e" % (nx, ny, h, err))
    
    print()
    print("-" * 60)
    print("MMS 验证结果")
    print("-" * 60)
    
    orders = []
    all_pass = True
    for i in range(1, len(errors)):
        p = math.log(errors[i] / errors[i - 1]) / math.log(hs[i] / hs[i - 1])
        expected = 2.0
        status = "PASS" if abs(p - expected) <= 0.1 else "FAIL"
        if status == "FAIL":
            all_pass = False
        orders.append(p)
        print("  %s -> %s: p_obs = %.3f (expected %.1f) [%s]" %
              (grids[i - 1], grids[i], p, expected, status))
    
    if orders:
        p_avg = sum(orders) / len(orders)
        print()
        print("  平均观察阶: %.3f" % p_avg)
        print("  总体结果: [%s]" % ("PASS" if all_pass else "FAIL"))
        print()
        if all_pass:
            print("  => 代码验证通过: 二阶精度实现正确。")
        else:
            print("  => WARNING: 观察阶偏离预期，检查实现。")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
