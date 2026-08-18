# -*- coding: utf-8 -*-
"""现场演示脚本 — v4 (预置脚本, 一键执行)"""

import subprocess, sys, os

ROOT = r'D:\opensource\arch-quality'
SCRIPTS = os.path.join(ROOT, 'docs', 'ppt')

def run_step(title, script_name):
    path = os.path.join(SCRIPTS, script_name)
    print('\n' + '=' * 60)
    print(f'  {title}')
    print('=' * 60)
    print(f'\n$ python {script_name}')
    # Run directly without capturing output (avoids encoding issues)
    sys.stdout.flush()
    r = subprocess.run([sys.executable, path], cwd=ROOT, timeout=300)
    if r.returncode != 0:
        print(f'[exit code: {r.returncode}]')

def main():
    print('模板元编程评估系统 v4.1 — 现场演示')
    print()

    run_step('步骤 1: 项目评估演示 (Eigen)', '_step1_eigen.py')
    run_step('步骤 2: 豁免注解体系', '_step2_waiver.py')
    run_step('步骤 3: output_level 体系', '_step3_output.py')
    run_step('步骤 4: 单元测试', '_step4_tests.py')
    run_step('步骤 5: 知识库展示', '_step5_kb.py')

    print('\n' + '=' * 60)
    print('  演示完成')
    print('=' * 60)

if __name__ == '__main__':
    main()
