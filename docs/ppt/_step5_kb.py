# -*- coding: utf-8 -*-
"""步骤 5: 知识库展示"""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
kb = r'D:\opensource\knowledge-base\arch-quality'
print('===== 架构质量知识卡片 =====')
print()
if os.path.exists(kb):
    for f in sorted(os.listdir(kb)):
        if f.endswith('.md'):
            name = f[:-3]
            try:
                print('  ' + name)
            except UnicodeEncodeError:
                print('  (Chinese name card)')
print()
print('存放位置: D:\\opensource\\knowledge-base')
print('打开方式: Obsidian → 打开本地仓库 → 选择该目录')
