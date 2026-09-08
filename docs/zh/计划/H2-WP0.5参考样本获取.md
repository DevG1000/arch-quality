# H2 WP-0.5 参考样本获取与 CI 注册

> **版本**：v1.0
> **日期**：2026-09-07
> **归属**：H2 扩展化执行计划 v2 → WP-0.5（W1-W2，WP-1/3 前置）
> **状态**：完成。意见 9 落地：OCCT/SALOME 获取策略（镜像/裁剪/授权）+ `projects.yaml` 注册（校验和 + 获取方式）+ 可复现获取脚本 + CI 门禁注册

---

## 一、获取策略评估

### 1.1 Open CASCADE Technology（OCCT）— 维度④ GCS 样本

| 项 | 决策 | 说明 |
|:---|:-----|:-----|
| 镜像 | **GitHub 官方 mirror** `github.com/Open-Cascade-SAS/OCCT` | 上游 GitLab 同步，API/浅克隆稳定 |
| 固定 ref | `refs/tags/V8.0.1` = commit `b8f597c677811d1f9f4d8a97f5ae2825c0353a42` | 2026-07-30 发布，8.0 系列维护版 |
| 获取方式 | **浅克隆**（`git fetch --depth 1 origin refs/tags/V8.0.1`）| 全历史 ~2GB，浅克隆 35K 文件 |
| 授权 | **LGPL-2.1 with Open CASCADE Exception 1.0** | `LICENSE_LGPL_21.txt` + `OCCT_LGPL_EXCEPTION.txt`；静态分析源码合规 |
| 评估子目录 | `src/` | DataExchange / FoundationClasses / ModelingAlgorithms / ModelingData 等内核包 |

### 1.2 SALOME GEOM — 维度⑧ ACL 样本

| 项 | 决策 | 说明 |
|:---|:-----|:-----|
| 镜像 | **官方 GitHub 克隆** `github.com/SalomePlatform/geom` | 上游 `git.salome-platform.org/gitpub/modules/geometry.git` |
| 裁剪 | **仅几何模块（非全平台）** | SALOME 全平台构建依赖繁重、仓库分散；GEOM 即"外部内核封装 + STEP/IGES 防腐"典型样本 |
| 固定 ref | commit `3f85d2e295e5d5415a0b1fe5f5e128a84d244996` | master 头（SALOME GEOM 9.16.0，2026-08-07）|
| 获取方式 | 浅克隆固定 commit | 小仓库，秒级 |
| 授权 | **LGPL-2.1** | 静态分析源码合规 |
| 评估子目录 | `src/` | `STEPPlugin`/`IGESPlugin`/`BREPPlugin`/`STLPlugin`/`XAOPlugin`/`GEOMImpl`（OCCT 封装）|

### 1.3 兜底基线（H2 决策 4）

若 OCCT/SALOME 获取失败（网络/授权），GCS/ACL 回归用 **FreeCAD**（封装 OCCT，已在 projects.yaml）与 **BRL-CAD**（实体建模，已在 projects.yaml）兜底。三者覆盖"真实 CAD 内核使用"语义。

---

## 二、交付物

| 交付物 | 说明 |
|:-------|:-----|
| `projects.yaml` 注册 `occt` + `salome-geom` | `fetch.repo/ref/method/dir` + `license` + `checksums` 段（`git_ref:<repo>:<sha>`）+ 头部 schema 注释 |
| `scripts/fetch_project.py` | 按 projects.yaml 可复现获取 + HEAD commit 校验 + `--check-all` + 幂等复用 |
| `ci_gate_roadmap.bat` 新增门禁 [6/6] | `python scripts/fetch_project.py --check-all`（记录阶段，按门禁治理准则渐进升级）|

### fetch_project.py 语义

```bash
python scripts/fetch_project.py salome-geom --dest <dir>   # 获取 + 校验
python scripts/fetch_project.py --check-all                # 注册完整性检查
```

- `fetch.ref`：`refs/tags/<tag>`（OCCT）或 40-hex commit SHA（salome-geom），`git fetch --depth 1 origin <ref>`
- 克隆后 `rev-parse HEAD` 与 `checksums` 段比对，**不一致 → 退出码 1**（防项目演进漂移，禁止更新快照掩盖）
- 目标目录已是正确 commit → 幂等复用（不重复克隆）

---

## 三、实测验证（干净环境可复现）

| 项目 | 获取 | HEAD 校验 | 幂等 | 样本内容 |
|:-----|:----:|:---------:|:----:|:---------|
| salome-geom | ✅ 浅克隆 | `3f85d2e...` 一致 | ✅ | STEPPlugin/IGESPlugin/BREPPlugin（ACL 防腐样本）|
| occt | ✅ 浅克隆 tag V8.0.1 | `b8f597c...` 一致 | ✅ | 35,413 文件；DataExchange/FoundationClasses/ModelingData（GCS 内核样本）|

> 验收：样本项目在干净 CI 可复现获取（fetch 脚本 + 校验和 + 幂等），已实测通过。

---

## 四、遗留 / 后续

| 项 | 归属 |
|:---|:-----|
| `occt`/`salome-geom` 的 GCS/ACL 回归快照（`eval.snapshot` 占位）| WP-2 / WP-4 |
| GCS/ACL 引擎注册进 profile schema（`PROFILE_ENGINE_MAP`）| WP-2 / WP-4 |
| 既有 18 个 H1 项目补 `fetch.ref` + 校验和（当前 `--check-all` 仅 WARN）| H3（渐进）|
| SALOME 全平台（非几何模块）采集 | 不排期（裁剪策略以 GEOM 为准）|

---

*H2 WP-0.5 完成，WP-1（维度④ 四件套）与 WP-3（维度⑧ 四件套）的前置语料已可复现获取。*