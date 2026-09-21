# -*- coding: utf-8 -*-
"""fetch_project.py — projects.yaml 参考样本可复现获取与校验（H2 WP-0.5）

用法：
    python scripts/fetch_project.py --list
    python scripts/fetch_project.py occt --dest D:\\samples\\occt
    python scripts/fetch_project.py salome-geom --dest D:\\samples\\salome-geom
    python scripts/fetch_project.py --check-all

可复现性保证：
  - 按 projects.yaml 的 fetch.ref（refs/tags/<tag> 或 40-hex commit SHA）浅克隆
  - 克隆后校验实际 HEAD commit 与 checksums 段 git_ref:<repo>:<sha> 一致
  - 不一致或获取失败 → 退出码 1（防止"项目演进漂移"导致回归基线失效）

退出码：0=成功/校验通过, 1=失败/不一致
"""

import argparse
import os
import re
import subprocess
import sys

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS_YAML = os.path.join(PROJECT, "projects.yaml")

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def read(path):
    """智能读取（UTF-8-sig 优先，回退 GBK/GB18030/Latin-1）"""
    with open(path, "rb") as f:
        b = f.read()
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030", "latin-1"):
        try:
            return b.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return b.decode("latin-1", errors="replace")


def load_projects():
    import yaml
    with open(PROJECTS_YAML, "rb") as f:
        data = yaml.safe_load(f) or {}
    return data.get("projects", {}), data.get("checksums", {})


def git(*args, cwd=None):
    """执行 git 命令，返回 (ok, stdout)"""
    try:
        result = subprocess.run(
            ["git"] + list(args), capture_output=True, text=True,
            encoding="utf-8", errors="replace", cwd=cwd, timeout=1800)
    except Exception as e:
        return False, str(e)
    return result.returncode == 0, result.stdout.strip()


def dest_is_correct(dest, repo, expected_sha):
    """目标目录是否已是正确 commit 的浅克隆（幂等复用）"""
    if not os.path.isdir(os.path.join(dest, ".git")):
        return False
    ok, remote = git("remote", "get-url", "origin", cwd=dest)
    if not ok or remote != repo:
        return False
    ok, head = git("rev-parse", "HEAD", cwd=dest)
    return ok and head == expected_sha


def fetch_project(name, dest, projects, checksums):
    proj = projects.get(name)
    if not proj:
        print(f"[ERROR] 项目 {name} 不在 projects.yaml")
        return False
    fetch = proj.get("fetch", {})
    repo = fetch.get("repo", "")
    method = fetch.get("method", "shallow")
    ref = fetch.get("ref")
    if method == "local":
        print(f"[OK] {name}: local（无需获取）")
        return True

    if not repo:
        print(f"[ERROR] {name}: 缺少 fetch.repo")
        return False

    checksum_key = f"git_ref:{repo}"
    expected_sha = checksums.get(checksum_key, "")
    if not expected_sha:
        print(f"[WARN] {name}: checksums 段缺少 {checksum_key}，仅按 fetch.ref 校验")

    if dest_is_correct(dest, repo, expected_sha):
        print(f"[OK] {name}: 目标已是最新固定 commit {expected_sha[:12]}（幂等复用）")
        return True

    print(f"[GET] {name}: clone {repo} @ {ref or 'HEAD'} → {dest}")
    os.makedirs(dest, exist_ok=True)
    ok, err = git("init", cwd=dest)
    if not ok:
        print(f"[ERROR] git init 失败: {err}")
        return False
    ok, err = git("remote", "add", "origin", repo, cwd=dest)
    if not ok:
        print(f"[ERROR] git remote add 失败: {err}")
        return False

    refspec = ref or "HEAD"
    ok, err = git("fetch", "--depth", "1", "origin", refspec, cwd=dest)
    if not ok:
        print(f"[ERROR] git fetch {refspec} 失败: {err}")
        return False
    ok, err = git("checkout", "FETCH_HEAD", cwd=dest)
    if not ok:
        print(f"[ERROR] git checkout 失败: {err}")
        return False

    ok, head = git("rev-parse", "HEAD", cwd=dest)
    if not ok:
        print(f"[ERROR] 无法读取 HEAD: {head}")
        return False

    if expected_sha and head != expected_sha:
        print(f"[FAIL] {name}: HEAD {head} != 校验和 {expected_sha}（项目演进漂移，禁止更新快照掩盖）")
        return False
    if expected_sha:
        print(f"[OK] {name}: HEAD {head} 与校验和一致")
    else:
        print(f"[OK] {name}: HEAD {head}（无校验和，仅按 ref 获取）")
    return True


def check_all(projects, checksums):
    ok_all = True
    for name, proj in projects.items():
        fetch = proj.get("fetch", {})
        if fetch.get("method", "shallow") == "local":
            continue
        repo = fetch.get("repo", "")
        ref = fetch.get("ref")
        checksum = checksums.get(f"git_ref:{repo}")
        if not repo:
            print(f"  [FAIL] {name}: 缺 fetch.repo")
            ok_all = False
            continue
        if not ref:
            print(f"  [WARN] {name}: 缺 fetch.ref（无法固定 commit，可复现性弱）")
        if not checksum:
            print(f"  [WARN] {name}: 缺 checksums 校验和（git_ref:{repo}）")
        else:
            print(f"  [OK] {name}: repo={repo} ref={ref or 'HEAD'} checksum={checksum[:12]}")
    return ok_all


def main():
    ap = argparse.ArgumentParser(description="projects.yaml 样本可复现获取与校验（H2 WP-0.5）")
    ap.add_argument("project", nargs="?", help="项目名（见 projects.yaml）")
    ap.add_argument("--dest", default="", help="目标目录")
    ap.add_argument("--list", action="store_true", help="列出全部项目")
    ap.add_argument("--check-all", action="store_true", help="校验所有 fetch 字段完整性")
    args = ap.parse_args()

    projects, checksums = load_projects()

    if args.list:
        for name in projects:
            print(f"  {name}: {projects[name].get('desc', '')}")
        return 0

    if args.check_all:
        ok = check_all(projects, checksums)
        return 0 if ok else 1

    if not args.project:
        print("用法：python scripts/fetch_project.py <项目名> --dest <目录> （--list / --check-all）")
        return 1
    if not args.dest:
        print("[ERROR] 需要 --dest <目标目录>")
        return 1

    ok = fetch_project(args.project, args.dest, projects, checksums)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())