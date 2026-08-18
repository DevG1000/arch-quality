"""
数值精度评估外部验证基线构建脚本

对本地可用的开源项目运行工具，保存 JSON 结果作为基线。
基线用于回归测试：每次工具代码修改后，比对输出是否一致。

用法：
    python scripts/build_numerical_baselines.py

依赖：
    - 以下项目需已克隆到本地：
      D:\opensource\MOOSE
      D:\opensource\dealii
      D:\opensource\FreeFEM-sources
      D:\opensource\mfem
      D:\opensource\dolfinx
"""

import sys, os, json, time, subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BUILD_SCRIPT = os.path.join(SCRIPT_DIR, '_build_one_baseline.py')

PROJECTS = {
    'MOOSE': r'D:\opensource\MOOSE',
    'deal.II': r'D:\opensource\dealii',
    'FreeFEM': r'D:\opensource\FreeFEM-sources',
    'MFEM': r'D:\opensource\mfem',
    'FEniCSx': r'D:\opensource\dolfinx',
}

SNAPSHOT_DIR = os.path.join(PROJECT_ROOT, 'tests', 'regression', 'snapshots', 'numerical_baselines')


def main():
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    print('=' * 60)
    print('数值精度评估外部验证基线构建')
    print(f'输出目录: {SNAPSHOT_DIR}')
    print('=' * 60)

    for name, path in PROJECTS.items():
        if not os.path.isdir(path):
            print(f'[SKIP] {name}: 项目路径不存在 {path}')
            continue

        snap_path = os.path.join(SNAPSHOT_DIR, f'{name}.json')
        print(f'\n[RUN] {name} @ {path}')
        t0 = time.time()

        try:
            result = subprocess.run(
                [sys.executable, BUILD_SCRIPT, name, path],
                capture_output=True, text=True, timeout=900000,
                cwd=PROJECT_ROOT
            )
            elapsed = time.time() - t0

            if result.returncode == 0:
                print(f'  OK ({elapsed:.0f}s)')
                # Show last line (saved path)
                for line in result.stdout.strip().split('\n'):
                    if line.startswith('saved:'):
                        print(f'  {line}')
            else:
                print(f'  FAIL ({elapsed:.0f}s)')
                print(f'  stderr: {result.stderr[:200]}')

        except subprocess.TimeoutExpired:
            print(f'  TIMEOUT (>{elapsed:.0f}s)')
        except Exception as e:
            print(f'  ERROR: {e}')

    print('\n' + '=' * 60)
    print('完成')
    baselines = [f for f in os.listdir(SNAPSHOT_DIR) if f.endswith('.json')]
    print(f'基线文件: {len(baselines)} 个')
    for b in sorted(baselines):
        fp = os.path.join(SNAPSHOT_DIR, b)
        with open(fp, 'r') as f:
            d = json.load(f)
        print(f'  {b:20s} overall={d["overall"]:5.2f}  NVR={len(d["nvr_violations"])}')
    print('=' * 60)


if __name__ == '__main__':
    main()
