# -*- coding: utf-8 -*-
"""步骤 4: 运行单元测试"""
import subprocess, sys, os
root = os.path.join(os.path.dirname(__file__), '..', '..')
r = subprocess.run(
    [sys.executable, '-m', 'pytest', 'tests/test_template_metrics.py', '-q', '--tb=line'],
    cwd=root, capture_output=True, text=True, timeout=120
)
print((r.stdout + r.stderr))
