# -*- coding: utf-8 -*-
"""
arch_metrics_hpc.py — 并行/异构计算架构（HPC/GPU）评估

实现《并行异构计算架构评估指南》v0.8 定义的 4 子维评分与 12 条 HPC 规则
（HPC-001~012）的静态分析检测。

已实现：启用检测 + 4 子维评分 + 12 条规则检测（HPC-001~012）
        + 豁免审计 + 适用性归一化 + 门禁状态。

版本绑定：
  - 指南版本：0.8
  - Skill 版本：1.0
"""

import os
import re
import json
import argparse
from pathlib import Path

from arch_quality.arch_core import (
    FileIndex,
    load_weights_from_skill, ensure_output_dir, write_report,
    read_text_smart,
)

SKILL_PATH = str(Path(__file__).parent / "skills" / "hpc-architecture.md")

GUIDE_VERSION = "0.8"
SKILL_VERSION = "1.0"

# ── 扩展名与构建文件 ──
CPP_EXTS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx",
            ".txx", ".ixx", ".cppm", ".mpp"}
PY_EXTS = {".py"}
HPC_SOURCE_EXTS = CPP_EXTS | PY_EXTS
GPU_SOURCE_EXTS = {".cu", ".cuh", ".hip"}
BUILD_FILE_NAMES = {"cmakelists.txt", "cmakecache.txt", "config.h",
                    "config.h.in", "meson.build", "makefile"}
BUILD_FILE_EXTS = {".cmake"}

# ── 维度 ──
DIMENSIONS = ["backend_consistency", "mpi_halo", "load_topology", "hybrid_parallel"]
DIM_LABEL = {
    "backend_consistency": "后端接口一致性",
    "mpi_halo": "MPI 域分解与 halo 交换",
    "load_topology": "负载均衡与进程拓扑",
    "hybrid_parallel": "混合并行（MPI×OpenMP）冲突",
}
DIMENSION_RULES = {
    "backend_consistency": {"HPC-001": 30, "HPC-002": 30, "HPC-003": 10, "HPC-004": 30},
    "mpi_halo": {"HPC-005": 55, "HPC-006": 35, "HPC-007": 10},
    "load_topology": {"HPC-008": 95, "HPC-009": 5},
    "hybrid_parallel": {"HPC-010": 40, "HPC-011": 35, "HPC-012": 25},
}

WAIVER_ABUSE_RATIO_LIMIT = 0.30

# ── 检测信号 ──
MPI_SIGNAL_RE = re.compile(r"\b(MPI_[A-Za-z_]+|mpi\.h|mpif\.h|Pstream)\b")
OMP_SIGNAL_RE = re.compile(r"#\s*pragma\s+omp\b|\bomp_get_[a-z_]+\b")
THREAD_SIGNAL_RE = re.compile(
    r"\b(pthread_create|std::thread|tbb::|taskflow::|Threads::Task)\b")
# 泛用 GPU/HPC 信号（含 Kokkos 泛用）：用于 is_hpc
GPU_SIGNAL_RE = re.compile(
    r"\b(cuda(Malloc|Memcpy|Free|DeviceSynchronize|Stream|HostAlloc)|__global__|"
    r"hip(Malloc|Memcpy|Launch)|sycl::|cl::|Kokkos::)\b")
# 设备后端信号（GPU 子维适用性）：不含泛用 Kokkos
GPU_DEVICE_RE = re.compile(
    r"\b(cuda(Malloc|Memcpy|Free|DeviceSynchronize|Stream|HostAlloc)|__global__|"
    r"hip(Malloc|Memcpy|Launch)|sycl::|cl::)\b|#\s*pragma\s+omp\s+target")
KOKKOS_GPU_RE = re.compile(
    r"\b(KOKKOS_ENABLE_(CUDA|HIP|SYCL)|DEAL_II_KOKKOS_ENABLE_(CUDA|HIP|SYCL)|"
    r"Kokkos::(Cuda|HIP|SYCL)|CudaSpace|HIPSpace)\b")



# 规则扫描排除目录（第三方/示例/测试，避免健康样本被捆绑代码误伤）
EXTRA_EXCLUDE_DIRS = {
    "externals", "external", "extern", "third_party", "thirdparty", "3rdparty",
    "vendor", "deps", "dependencies", "examples", "example", "tests", "test",
    "miniapps", "benchmarks", "benchmark", "tutorials", "tutorial", "subprojects",
    "bundled", "bundle", "contrib", "thirdparty", "3rdparty",
}


def _is_excluded_path(abs_path: str, root: str) -> bool:
    try:
        rel = os.path.relpath(abs_path, root)
    except ValueError:
        rel = abs_path
    return any(p.lower() in EXTRA_EXCLUDE_DIRS for p in Path(rel).parts)


def _strip_literals(content: str) -> str:
    content = re.sub(r'"(?:\\.|[^"\\])*"', '""', content)
    content = re.sub(r"'(?:\\.|[^'\\])*'", "''", content)
    return content


# ── 规则检测正则（W2）──
GPU_RAW_RE = re.compile(
    r"\b(cudaMalloc|cudaMemcpyAsync|cudaMemcpy|cudaFree|cudaDeviceSynchronize|"
    r"hipMalloc|hipMemcpy)\b|<<<\s*[^<>]{0,120}>>>")
GUARD_RE = re.compile(
    r"#\s*if(?:def)?\b[^\n]*(?:CUDA|HIP|CUDACC|GPU|KOKKOS_ENABLE|MFEM_USE_CUDA)"
    r"|cudaGetDeviceCount|hipGetDeviceCount|omp_get_num_devices|Device::Allows")
LAUNCH_LITERAL_RE = re.compile(
    r"\b(?:num_teams|thread_limit)\s*\(\s*\d+\s*\)|<<<\s*\d+\s*,\s*\d+\s*>>>")
COPY_RE = re.compile(r"\b(cudaMemcpyAsync|cudaMemcpy)\b")
PERSIST_RE = re.compile(
    r"#\s*pragma\s+omp\s+target\s+data|#\s*pragma\s+omp\s+enter\s+data")
ISEND_RE = re.compile(r"\bMPI_Isend\b")
WAIT_RE = re.compile(
    r"\bMPI_(Wait|Waitall|Waitany|Waitsome|Test|Testall|Testany|Request_free)\b")
COLLECTIVE_RE = re.compile(
    r"\bMPI_(Allreduce|Bcast|Reduce|Allgather|Allgatherv|Gather|Scatter)\b")
LOOP_HEADER_RE = re.compile(r"\b(for|while)\s*\(([^)]*)\)")
BLOCKING_SEND_RE = re.compile(r"\bMPI_(Send|Recv)\b")
NONBLOCK_RE = re.compile(r"\bMPI_(Isend|Irecv|Sendrecv)\b")
WEIGHTS_RE = re.compile(
    r"\b(PartitionWeights|get_cell_weights|p4est_weights|loadDistribution|"
    r"weighted|METIS_[A-Za-z_]*[Ww]eight)\b")
NONUNIFORM_RE = re.compile(
    r"\b(p4est_refine|p4est_coarsen|refineLocally|coarsenLocally|"
    r"dynamicRefine|AMR|multiRegion|multiMaterial)\b")
PARTITION_RE = re.compile(
    r"\b(p4est_partition|METIS_Part\w*|ParMETIS|decomposePar|repartition|loadBalance)\b")
WORLD_RE = re.compile(r"\bMPI_COMM_WORLD\b")
SPLIT_RE = re.compile(r"\bMPI_Comm_(split|dup)\b")
OMP_PARALLEL_RE = re.compile(r"#\s*pragma\s+omp\s+parallel\b")
OMP_PARALLEL_BLOCK_RE = re.compile(r"#\s*pragma\s+omp\s+parallel\b(?!\s+for)")
OMP_PARALLEL_FOR_RE = re.compile(r"#\s*pragma\s+omp\s+parallel\s+for\b")
OMP_MASTER_RE = re.compile(r"#\s*pragma\s+omp\s+(master|single|critical|atomic)\b")
OMP_DS_RE = re.compile(r"\b(reduction|private|firstprivate|atomic|critical)\b")
THREAD_NEST_RE = re.compile(r"\b(std::thread|pthread_create)\b")
STREAM_ABSTRACTION_RE = re.compile(r"\b(UOPstream|UIPstream|Pstream)\b")
DUAL_GUARD_RE = re.compile(
    r"#\s*if(?:def)?\b[^\n]*\b(__CUDACC__|USE_CUDA|HAVE_CUDA)\b")
CPU_LOOP_RE = re.compile(r"\bfor\s*\(")

# 规则元数据：rule -> (name, dimension, severity, output_level)
RULE_META = {
    "HPC-001": ("CPU/GPU 双实现一致性", "backend_consistency", "MEDIUM", "WARNING"),
    "HPC-002": ("设备可用性守卫", "backend_consistency", "MEDIUM", "WARNING"),
    "HPC-003": ("kernel launch 配置硬编码", "backend_consistency", "LOW", "INFO"),
    "HPC-004": ("H2D/D2H 冗余搬运", "backend_consistency", "MEDIUM", "WARNING"),
    "HPC-005": ("halo 交换配对/宽度", "mpi_halo", "HIGH", "WARNING"),
    "HPC-006": ("热循环集合通信滥用", "mpi_halo", "MEDIUM", "WARNING"),
    "HPC-007": ("通信/计算未重叠", "mpi_halo", "LOW", "INFO"),
    "HPC-008": ("负载划分未加权（候选）", "load_topology", "MEDIUM", "WARNING"),
    "HPC-009": ("通信域/拓扑未隔离", "load_topology", "LOW", "INFO"),
    "HPC-010": ("非线程安全 MPI 调用", "hybrid_parallel", "HIGH", "WARNING"),
    "HPC-011": ("OpenMP 共享变量误用", "hybrid_parallel", "MEDIUM", "WARNING"),
    "HPC-012": ("并行域嵌套违规", "hybrid_parallel", "HIGH", "WARNING"),
}

def _strip_comments(content: str) -> str:
    """剥离 C/C++ 行注释 // 与块注释 /* */（避免注释提及关键词造成误报）"""
    content = re.sub(r"//[^\n]*", "", content)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    return content


def _iter_special_files(root: str, limit: int = 3000):
    """补充扫描 FileIndex 未索引的文件：.cu/.cuh/.hip 与构建文件。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if (d.lower() not in FileIndex.EXCLUDE_DIRS
                    and d.lower() not in EXTRA_EXCLUDE_DIRS
                    and not d.startswith("."))
        )
        for fn in sorted(filenames):
            low = fn.lower()
            ext = os.path.splitext(low)[1]
            if ext in GPU_SOURCE_EXTS or low in BUILD_FILE_NAMES or ext in BUILD_FILE_EXTS:
                out.append(os.path.join(dirpath, fn))
                if len(out) >= limit:
                    return out
    return out


CONFIG_FILE_NAMES = {"decomposepardict", "dockerfile", "makefile", "cmakelists.txt"}
CONFIG_FILE_EXTS = {".slurm", ".sh", ".bat", ".ps1", ".yaml", ".yml", ".cmake"}


def _iter_config_files(root: str, limit: int = 800):
    """收集配置/启动脚本（decomposeParDict、Slurm、shell、YAML 等），供拓扑 advisory 使用。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if (d.lower() not in FileIndex.EXCLUDE_DIRS
                and d.lower() not in EXTRA_EXCLUDE_DIRS
                and not d.startswith("."))
        )
        for fn in sorted(filenames):
            low = fn.lower()
            ext = os.path.splitext(low)[1]
            if low in CONFIG_FILE_NAMES or ext in CONFIG_FILE_EXTS:
                out.append(os.path.join(dirpath, fn))
                if len(out) >= limit:
                    return out
    return out


def _detect_hpc(root: str, index: FileIndex, special_files=None) -> bool:
    """启用检测：源码/构建文件出现 MPI/OpenMP/线程/GPU 信号之一。"""
    special_files = special_files or []
    source_files = [f for f in index.files
                    if f["ext"] in HPC_SOURCE_EXTS
                    and not _is_excluded_path(f["abs_path"], root)]
    for f in source_files[:500]:
        try:
            content = _strip_comments(read_text_smart(f["abs_path"]))
        except Exception:
            continue
        if (MPI_SIGNAL_RE.search(content) or OMP_SIGNAL_RE.search(content)
                or THREAD_SIGNAL_RE.search(content) or GPU_SIGNAL_RE.search(content)):
            return True
    for p in special_files:
        if _is_excluded_path(p, root):
            continue
        try:
            content = _strip_comments(read_text_smart(p))
        except Exception:
            continue
        if (MPI_SIGNAL_RE.search(content) or OMP_SIGNAL_RE.search(content)
                or THREAD_SIGNAL_RE.search(content) or GPU_SIGNAL_RE.search(content)
                or KOKKOS_GPU_RE.search(content)):
            return True
    return False


def _waiver_re(name: str):
    return re.compile(
        r"/\*\s*@" + name + r"\s*:\s*(?P<reason>\S(?:[^*]|\*(?!/))*)\s*\*/"
        r"|//\s*@" + name + r"\s*:\s*(?P<reason2>\S[^\n]*?)\s*$",
        re.MULTILINE,
    )


def _waiver_invalid_re(name: str):
    return re.compile(
        r"/\*\s*@" + name + r"\s*(?::\s*)?\*/"
        r"|//\s*@" + name + r"\s*(?::\s*)?$",
        re.MULTILINE,
    )


def _waiver_reason(m) -> str:
    return ((m.groupdict().get("reason") or m.groupdict().get("reason2") or "")
            .strip())



def _brace_end(content: str, start: int) -> int:
    depth = 0
    for i in range(start, len(content)):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(content)


def _line_of(content: str, idx: int) -> int:
    return content.count("\n", 0, idx) + 1


def _loop_body_after(content: str, pos: int):
    """定位 pos 之后紧随的 for/while 循环体（大括号块或单语句），避免误取后续循环的 {。"""
    m = re.search(r"\b(for|while)\s*\(", content[pos:pos + 240])
    if not m:
        return None
    start = pos + m.start()
    lp = content.find("(", start)
    depth = 0
    end = -1
    for j in range(lp, len(content)):
        if content[j] == "(":
            depth += 1
        elif content[j] == ")":
            depth -= 1
            if depth == 0:
                end = j
                break
    if end < 0:
        return None
    k = end + 1
    while k < len(content) and content[k] in " \t\r\n":
        k += 1
    if k < len(content) and content[k] == "{":
        return content[k:_brace_end(content, k)]
    semi = content.find(";", k)
    if semi < 0:
        semi = min(len(content), k + 300)
    return content[k:semi + 1]


def _pragma_blocks(content: str, pragma_re):
    """返回 [(pragma_start, brace_start, brace_end)]；跳过无大括号的语句形式。"""
    blocks = []
    for m in pragma_re.finditer(content):
        j = content.find("{", m.end())
        if j < 0 or j - m.end() > 400:
            continue
        blocks.append((m.start(), j, _brace_end(content, j)))
    return blocks


def _loop_var_before(content: str, idx: int, window: int = 600):
    """在 idx 之前 600 字符内取最近一个 for/while 的循环变量名。"""
    head = content[max(0, idx - window):idx]
    last = None
    for m in LOOP_HEADER_RE.finditer(head):
        last = m
    if not last:
        return None
    header = last.group(2)
    m = re.search(r"\b(?:int|long|size_t|auto|unsigned)\s+(\w+)", header)
    if m:
        return m.group(1)
    tok = header.strip().split()
    return tok[0] if tok else None


IMPL_EXTS = {".c", ".cc", ".cpp", ".cxx"}


def _enclosing_loop_var(content: str, idx: int, window: int = 400):
    """返回 idx 所在循环体的循环变量名；若 idx 不在循环体内则 None。"""
    start = max(0, idx - window)
    head = content[start:idx]
    matches = list(re.finditer(r"\b(for|while)\s*\(", head))
    if not matches:
        return None
    m = matches[-1]
    abs_open = content.find("{", start + m.end())
    if abs_open < 0 or abs_open - (start + m.end()) > 300:
        return None
    end = _brace_end(content, abs_open)
    if not (abs_open <= idx <= end):
        return None
    close = content.find(")", start + m.end())
    header = content[start + m.end():close + 1] if close >= 0 else ""
    vm = re.search(r"\b(?:int|long|size_t|auto|unsigned)\s+(\w+)", header)
    if vm:
        return vm.group(1)
    tok = header.strip().split()
    return tok[0] if tok else None


class HpcArchitectureMetrics:
    """并行/异构计算架构评估"""

    def __init__(self, root: str):
        self.root = root
        self.index = FileIndex(root)
        self.weights = {}
        self._all_contents = {}     # abs_path → 已剥离注释内容
        self._benchmark_ok = {}     # rel_path → reason
        self._deferred = {}
        self._gpu_only = {}
        self._invalid_waivers = []
        self._is_hpc = False
        self._special_files = _iter_special_files(root)
        self._config_files = _iter_config_files(root)
        self._init_weights()
        self._is_hpc = _detect_hpc(root, self.index, self._special_files)
        if self._is_hpc:
            self._scan_files()

    def _init_weights(self):
        _DIM_KEYS = set(DIM_LABEL.values())
        try:
            raw = load_weights_from_skill(SKILL_PATH)
            self.weights = {k: v for k, v in raw.items() if k in _DIM_KEYS}
            if len(self.weights) != 4:
                raise ValueError(f"只解析到 {len(self.weights)} 个维度权重")
        except Exception:
            self.weights = {
                "后端接口一致性": 0.30,
                "MPI 域分解与 halo 交换": 0.30,
                "负载均衡与进程拓扑": 0.20,
                "混合并行（MPI×OpenMP）冲突": 0.20,
            }

    def _rel_path(self, abs_path: str) -> str:
        try:
            return os.path.relpath(abs_path, self.root).replace("\\", "/")
        except ValueError:
            return str(abs_path).replace("\\", "/")

    def _consume_waivers(self, raw: str, rel: str):
        for name, store in (("hpc_benchmark_ok", self._benchmark_ok),
                            ("hpc_deferred", self._deferred),
                            ("hpc_gpu_only", self._gpu_only)):
            m = _waiver_re(name).search(raw)
            if m:
                store[rel] = _waiver_reason(m)
            elif _waiver_invalid_re(name).search(raw):
                self._invalid_waivers.append(
                    {"file": rel, "annotation": "@" + name,
                     "issue": "缺少 reason，豁免无效"})

    def _scan_files(self):
        for f in self.index.files:
            if f["ext"] not in HPC_SOURCE_EXTS:
                continue
            try:
                raw = read_text_smart(f["abs_path"])
            except Exception:
                continue
            rel = self._rel_path(f["abs_path"])
            self._consume_waivers(raw, rel)
            self._all_contents[f["abs_path"]] = _strip_comments(raw)
        for p in self._special_files:
            # 构建文件也读入，用于 GPU 后端（KOKKOS_ENABLE_*）适用性判定
            try:
                raw = read_text_smart(p)
            except Exception:
                continue
            rel = self._rel_path(p)
            self._consume_waivers(raw, rel)
            self._all_contents[p] = _strip_comments(raw)

    def _is_production(self, abs_path: str) -> bool:
        return not _is_excluded_path(abs_path, self.root)

    def _iter_production(self):
        for p, c in self._all_contents.items():
            if self._is_production(p):
                yield p, c

    def _iter_cxx_production(self):
        for p, c in self._iter_production():
            if os.path.splitext(p)[1].lower() in (CPP_EXTS | GPU_SOURCE_EXTS):
                yield p, c

    def _iter_impl_production(self):
        for p, c in self._iter_cxx_production():
            if os.path.splitext(p)[1].lower() in IMPL_EXTS:
                yield p, c

    def _waiver_audit(self) -> dict:
        total = max(1, len(self._all_contents))
        limit = WAIVER_ABUSE_RATIO_LIMIT
        b, d, g = self._benchmark_ok, self._deferred, self._gpu_only
        combined = set(b) | set(d) | set(g)
        ratios = {
            "benchmark_ok": round(len(b) / total, 4),
            "deferred": round(len(d) / total, 4),
            "gpu_only": round(len(g) / total, 4),
            "combined": round(len(combined) / total, 4),
        }
        warning = None
        if ratios["combined"] > limit:
            warning = (
                f"豁免注解合计占比 {ratios['combined']:.1%} 超过上限 {limit:.0%}，"
                f"12 条规则覆盖度可能失真，请复核豁免必要性")
        return {
            "benchmark_ok": {
                "count": len(b), "ratio": ratios["benchmark_ok"],
                "scope": "HPC-003 不计数（影响 scoring）",
                "files": sorted(b)[:20],
            },
            "deferred": {
                "count": len(d), "ratio": ratios["deferred"],
                "scope": "降一级（仅 output_level）",
                "files": sorted(d)[:20],
            },
            "gpu_only": {
                "count": len(g), "ratio": ratios["gpu_only"],
                "scope": "HPC-002 降 INFO（仅 output_level）",
                "files": sorted(g)[:20],
            },
            "invalid_waivers": list(self._invalid_waivers),
            "abuse_limit": limit,
            "abuse_warning": warning,
        }

    def _applicability(self) -> dict:
        text = "\n".join(self._all_contents.values())
        mpi = bool(MPI_SIGNAL_RE.search(text))
        omp = bool(OMP_SIGNAL_RE.search(text))
        threads = bool(THREAD_SIGNAL_RE.search(text))
        kokkos = bool(re.search(r"\bKokkos::", text))
        gpu = bool(GPU_DEVICE_RE.search(text) or KOKKOS_GPU_RE.search(text))
        return {
            "backend_consistency": gpu,
            "mpi_halo": mpi,
            "load_topology": mpi,
            "hybrid_parallel": omp or threads or kokkos,
        }

    # ── 4 子维 ──
    def _calc_dim(self, dim: str, triggered: set):
        penalty = sum(pts for rid, pts in DIMENSION_RULES[dim].items()
                      if rid in triggered)
        detail = {
            "triggered": sorted(rid for rid in DIMENSION_RULES[dim] if rid in triggered),
            "penalty": penalty,
        }
        return max(0, 100 - penalty), detail

    def calc_backend_consistency(self):
        return self._calc_dim_cached("backend_consistency")

    def calc_mpi_halo(self):
        return self._calc_dim_cached("mpi_halo")

    def calc_load_topology(self):
        return self._calc_dim_cached("load_topology")

    def calc_hybrid_parallel(self):
        return self._calc_dim_cached("hybrid_parallel")

    def _calc_dim_cached(self, dim: str):
        if not hasattr(self, "_triggered_cache"):
            self._triggered_cache = {v["rule"] for v in self.check_hpc_rules()}
        return self._calc_dim(dim, self._triggered_cache)

    def check_hpc_rules(self):
        """12 条规则检测（HPC-001~012），按规则聚合为违规列表。"""
        raw = []
        for fn in (self._rule_001, self._rule_002, self._rule_003, self._rule_004,
                   self._rule_005, self._rule_006, self._rule_007, self._rule_008,
                   self._rule_009, self._rule_010, self._rule_011, self._rule_012):
            raw.extend(fn())
        return self._aggregate(raw)

    def _rule_001(self):
        out = []
        for p, c in self._iter_impl_production():
            if DUAL_GUARD_RE.search(c) and "#else" in c and CPU_LOOP_RE.search(c):
                out.append({"rule": "HPC-001", "file": self._rel_path(p), "count": 1,
                            "candidate": True,
                            "detail": "CPU/GPU 条件编译双分支且含 CPU 循环，需对照测试确认一致性"})
        return out

    def _rule_002(self):
        out = []
        for p, c in self._iter_cxx_production():
            c2 = _strip_literals(c)
            calls = GPU_RAW_RE.findall(c2)
            if not calls or GUARD_RE.search(c2):
                continue
            out.append({"rule": "HPC-002", "file": self._rel_path(p),
                        "count": len(calls), "confirmed": True, "candidate": False,
                        "detail": "GPU 调用点无 #ifdef/设备检测/回退"})
        return out

    def _rule_003(self):
        out = []
        for p, c in self._iter_cxx_production():
            rel = self._rel_path(p)
            if rel in self._benchmark_ok:
                continue
            ms = LAUNCH_LITERAL_RE.findall(_strip_literals(c))
            if ms:
                out.append({"rule": "HPC-003", "file": rel, "count": len(ms),
                            "candidate": False,
                            "detail": "launch 配置为与规模无关的魔法数"})
        return out

    def _rule_004(self):
        out = []
        for p, c in self._iter_cxx_production():
            if not COPY_RE.search(c) or PERSIST_RE.search(c):
                continue
            if not re.search(r"\b(for|while)\s*\(", c):
                continue
            out.append({"rule": "HPC-004", "file": self._rel_path(p),
                        "count": len(COPY_RE.findall(c)), "candidate": True,
                        "detail": "循环内 H2D/D2H 搬运且无 target data 常驻"})
        return out

    def _rule_005(self):
        out = []
        for p, c in self._iter_cxx_production():
            if not ISEND_RE.search(c):
                continue
            if WAIT_RE.search(c):
                continue  # 文件内已有 Wait/Test，视为配对（同作用域窄化）
            if STREAM_ABSTRACTION_RE.search(c) or "/Pstream/" in self._rel_path(p):
                continue  # OpenFOAM 类流抽象：Isend/Wait 分离在 Pstream 层
            out.append({"rule": "HPC-005", "file": self._rel_path(p),
                        "count": len(ISEND_RE.findall(c)), "candidate": True,
                        "detail": "MPI_Isend 后文件内未见 Wait/Test"})
        return out

    def _rule_006(self):
        out = []
        for p, c in self._iter_cxx_production():
            for m in COLLECTIVE_RE.finditer(c):
                var = _enclosing_loop_var(c, m.start(), window=400)
                if not var:
                    continue
                if re.search(r"iter|step|time|maxiter|niter|outer|loop", var, re.I):
                    continue  # 每迭代残差归约属常规，不判
                if re.search(r"^(i|j|k|e|p|idx|cell|face|elem|node)$", var, re.I):
                    out.append({"rule": "HPC-006", "file": self._rel_path(p),
                                "count": 1, "candidate": True,
                                "detail": f"元素循环变量 {var} 内集合通信可局部化"})
                    break
        return out

    def _rule_007(self):
        out = []
        for p, c in self._iter_cxx_production():
            if NONBLOCK_RE.search(c):
                continue
            hit = False
            for m in BLOCKING_SEND_RE.finditer(c):
                tail = c[m.end():m.end() + 300]
                if re.search(r"\b(for|while)\s*\(|\b(compute|solve|assemble|update|apply)\w*\s*\(", tail):
                    hit = True
                    break
            if hit:
                out.append({"rule": "HPC-007", "file": self._rel_path(p),
                            "count": 1, "candidate": False,
                            "detail": "阻塞 Send/Recv 紧邻计算且无重叠"})
        return out

    def _rule_008(self):
        weights = False
        nonuniform = []
        same_file_partition = False
        for p, c in self._iter_cxx_production():
            if WEIGHTS_RE.search(c):
                weights = True
            if NONUNIFORM_RE.search(c):
                nonuniform.append(self._rel_path(p))
                if PARTITION_RE.search(c):
                    same_file_partition = True
        if weights or not nonuniform or not same_file_partition:
            return []
        return [{"rule": "HPC-008", "file": nonuniform[0],
                 "count": len(nonuniform), "candidate": True,
                 "detail": "同文件存在自适应/多区域信号与分区 API，但未见加权配置"}]

    def _rule_009(self):
        world = [self._rel_path(p) for p, c in self._iter_cxx_production()
                 if WORLD_RE.search(c)]
        if len(world) < 2:
            return []
        if any(SPLIT_RE.search(c) for _p, c in self._iter_production()):
            return []
        return [{"rule": "HPC-009", "file": world[0], "count": 1,
                 "candidate": False,
                 "detail": "多模块共用 MPI_COMM_WORLD 且未见 Comm_split/Comm_dup"}]

    def _thread_support_level(self):
        """静态判定项目请求/可能获得的 MPI 线程级别。

        - MULTIPLE：显式且无条件请求 MPI_THREAD_MULTIPLE（跳过作用域检查）
        - UNKNOWN：条件请求（如 needsThread ? MULTIPLE : SINGLE）、仅 Query_thread，
                   无法静态确认 provided → 仍需检查作用域
        - LT_MULTIPLE：未请求 MULTIPLE（默认 SINGLE）→ 需检查作用域
        """
        has_init = has_query = has_mult = has_nonmult = False
        for _p, c in self._iter_cxx_production():
            c2 = _strip_literals(c)
            if "MPI_Init_thread" in c2:
                has_init = True
            if "MPI_Query_thread" in c2:
                has_query = True
            if "MPI_THREAD_MULTIPLE" in c2:
                has_mult = True
            if re.search(r"MPI_THREAD_(SINGLE|FUNNELED|SERIALIZED)", c2):
                has_nonmult = True
        if has_init and has_mult and not has_nonmult:
            return "MULTIPLE"
        if has_mult or has_query:
            return "UNKNOWN"
        return "LT_MULTIPLE"

    def _omp_mpi_scopes(self, c):
        """返回 [(起始行, 作用域文本)]，覆盖块形式与 parallel-for 语句形式。"""
        scopes = []
        for _ps, bs, be in _pragma_blocks(c, OMP_PARALLEL_BLOCK_RE):
            scopes.append((c.count("\n", 0, _ps) + 1, c[bs:be]))
        for m in OMP_PARALLEL_FOR_RE.finditer(c):
            body = _loop_body_after(c, m.end())
            if body is not None:
                scopes.append((c.count("\n", 0, m.start()) + 1, body))
        return scopes

    def _rule_010(self):
        level = self._thread_support_level()
        if level == "MULTIPLE":
            return []  # 显式无条件请求 MULTIPLE
        out = []
        for p, c in self._iter_cxx_production():
            for _line, body in self._omp_mpi_scopes(c):
                if not MPI_SIGNAL_RE.search(body):
                    continue
                if OMP_MASTER_RE.search(body):
                    continue
                out.append({"rule": "HPC-010", "file": self._rel_path(p),
                            "count": 1, "candidate": True,
                            "detail": f"omp 作用域内直接调用 MPI（thread level={level}，未确认 MULTIPLE）"})
                break
        return out

    def _rule_011(self):
        out = []
        for p, c in self._iter_cxx_production():
            for m in OMP_PARALLEL_FOR_RE.finditer(c):
                line_end = c.find("\n", m.end())
                if line_end < 0:
                    line_end = len(c)
                pragma = c[m.start():line_end]
                if OMP_DS_RE.search(pragma):
                    continue
                body = c[line_end:line_end + 800]
                lm = re.search(r"\bfor\s*\(\s*[A-Za-z_][\w:<>]*\s+(\w+)\s*=", body)
                idx = lm.group(1) if lm else None
                acc = re.search(r"\b(\w+)\s*(\+=|-=|\*=|/=)", body)
                if acc and acc.group(1) != idx:
                    var = acc.group(1)
                    # 变量在循环体内声明（如 auto& interp = output[i]）→ 局部累加，非共享
                    local_decl = re.search(
                        r"(?:auto|[A-Za-z_][\w:<>]*)\s*&?\s*" + re.escape(var) + r"\s*[=({]",
                        body[:acc.start()])
                    if local_decl:
                        continue
                    out.append({"rule": "HPC-011", "file": self._rel_path(p),
                                "count": 1, "candidate": True,
                                "detail": f"共享变量 {var} 无 reduction/private"})
                    break
        return out

    def _rule_012(self):
        out = []
        for p, c in self._iter_cxx_production():
            hit = False
            for _ps, bs, be in _pragma_blocks(c, OMP_PARALLEL_BLOCK_RE):
                block = c[bs:be]
                if OMP_PARALLEL_RE.search(block[1:]) or THREAD_NEST_RE.search(block):
                    hit = True
                    break
            if hit:
                out.append({"rule": "HPC-012", "file": self._rel_path(p),
                            "count": 1, "candidate": True,
                            "detail": "并行域嵌套（omp 套 omp / 并行区内起线程）"})
        return out

    def _aggregate(self, raw):
        out = {}
        for v in raw:
            rule = v["rule"]
            if rule not in RULE_META:
                continue
            if rule not in out:
                name, dim, sev, level = RULE_META[rule]
                out[rule] = {"rule": rule, "name": name, "dimension": dim,
                             "severity": sev, "output_level": level,
                             "count": 0, "candidate": False, "confirmed": False,
                             "files": [], "detail": ""}
            o = out[rule]
            o["count"] += int(v.get("count", 1))
            o["candidate"] = o["candidate"] or bool(v.get("candidate"))
            o["confirmed"] = o["confirmed"] or bool(v.get("confirmed"))
            f = v.get("file")
            if f and f not in o["files"] and len(o["files"]) < 5:
                o["files"].append(f)
            if v.get("detail"):
                o["detail"] = v["detail"]
        downgrade = {"ERROR": "WARNING", "WARNING": "INFO", "INFO": "INFO"}
        dropped = []
        for rule, o in out.items():
            fs = set(o["files"])
            if rule == "HPC-003" and fs and fs <= set(self._benchmark_ok):
                dropped.append(rule)
                continue
            if rule == "HPC-002" and fs and fs <= set(self._gpu_only):
                o["output_level"] = "INFO"
            elif fs and fs <= set(self._deferred):
                o["output_level"] = downgrade.get(o["output_level"], o["output_level"])
        for r in dropped:
            out.pop(r, None)
        return [out[k] for k in sorted(out)]

    def _gate(self, violations) -> tuple:
        rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        confirmed = [v for v in violations if v.get("confirmed")]
        if any(v.get("output_level") == "ERROR" for v in confirmed):
            status = "BLOCK"
        elif confirmed:
            status = "WARN"
        else:
            status = "PASS"
        max_sev = None
        if confirmed:
            max_sev = max(confirmed, key=lambda v: rank.get(v.get("severity"), 0)).get("severity")
        return status, max_sev

    def _topology_advisory(self) -> dict:
        """多级计算结构（Node/CPU/core/GPU）的 advisory 检查。

        **不计分**，不改变 overall/gate/confirmed；仅输出 present/absent/unknown + 证据。
        """
        patterns = {
            "multi_level_decomposition": r"\bmultiLevel\b|\bmultiLevelCoeffs\b",
            "weighted_partition": r"\bweightField\b|\bprocessorWeights\b|\bloadDistribution\b",
            "cpu_binding": r"--cpu-bind\b|\btaskset\b|\bnumactl\b",
            "gpu_binding": r"CUDA_VISIBLE_DEVICES|--gpus-per-task|--gpu-bind|--gres=gpu|ROCR_VISIBLE_DEVICES",
            "numa_affinity": r"\bnumactl\b|--cpu-bind\b",
            "gpu_backend": r"KOKKOS_ENABLE_(CUDA|HIP|SYCL)|Kokkos::(Cuda|HIP|SYCL)|cudaMalloc|hipMalloc|__global__",
        }
        evidence = {k: [] for k in patterns}
        scanned = 0
        for path in self._config_files:
            try:
                raw = read_text_smart(path)
            except Exception:
                continue
            scanned += 1
            c = _strip_comments(raw)
            c = re.sub(r"(?m)^\s*#.*$", "", c)  # shell/YAML 注释
            rel = self._rel_path(path)
            for key, pat in patterns.items():
                if len(evidence[key]) < 3 and re.search(pat, c, re.I):
                    evidence[key].append(rel)
        result = {"scored": False, "scanned_config_files": scanned}
        for key in patterns:
            result[key] = "present" if evidence[key] else ("absent" if scanned else "unknown")
            result[key + "_evidence"] = evidence[key]
        result["notes"] = [
            "advisory only: not scored; does not change overall/gate/confirmed",
            "present = signal found; absent = config scanned but no signal; unknown = no config scanned",
        ]
        return result

    def all_metrics(self) -> dict:
        if not self._is_hpc:
            return {
                "overall": None,
                "is_hpc": False,
                "applicability_set": [],
                "score_scope": "none",
                "dimensions": {
                    d: {"score": None, "applicable": False, "detail": {}}
                    for d in DIMENSIONS
                },
                "hpc_violations": [],
                "topology_advisory": {},
                "gate_status": "PASS",
                "confirmed_max_severity": None,
                "waiver_audit": {},
                "version_info": {
                    "guide_version": GUIDE_VERSION,
                    "skill_version": SKILL_VERSION,
                },
            }

        violations = self.check_hpc_rules()
        triggered = {v["rule"] for v in violations}
        app = self._applicability()
        dims = {}
        for d in DIMENSIONS:
            score, detail = self._calc_dim(d, triggered)
            dims[d] = {"score": score, "applicable": app[d], "detail": detail}

        applicable = [d for d in DIMENSIONS if app[d]]
        if applicable:
            wsum = sum(self.weights[DIM_LABEL[d]] for d in applicable)
            overall = sum(dims[d]["score"] * self.weights[DIM_LABEL[d]]
                          for d in applicable) / max(wsum, 1e-9)
            overall = round(overall, 2)
            scope = "subset"
        else:
            overall = None
            scope = "none"

        gate, max_sev = self._gate(violations)
        return {
            "overall": overall,
            "is_hpc": True,
            "applicability_set": applicable,
            "score_scope": scope,
            "dimensions": dims,
            "hpc_violations": violations,
            "topology_advisory": self._topology_advisory(),
            "gate_status": gate,
            "confirmed_max_severity": max_sev,
            "waiver_audit": self._waiver_audit(),
            "version_info": {
                "guide_version": GUIDE_VERSION,
                "skill_version": SKILL_VERSION,
            },
        }


def main():
    parser = argparse.ArgumentParser(description="并行/异构计算架构评估")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--hpc-only", action="store_true", help="仅检测 HPC 规则")
    args = parser.parse_args()

    metrics = HpcArchitectureMetrics(args.root)
    if args.hpc_only:
        result = {"hpc_violations": metrics.check_hpc_rules()}
    else:
        result = metrics.all_metrics()

    out_dir = ensure_output_dir(args.root)
    write_report(out_dir, "hpc-architecture-metrics.json", result)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        vi = result.get("version_info", {})
        print("并行/异构计算架构评估")
        print("=" * 50)
        print(f"  Guide version: {vi.get('guide_version', '?')}")
        print(f"  Skill version: {vi.get('skill_version', '?')}")
        print(f"  Is HPC project: {result.get('is_hpc', False)}")
        if result.get("is_hpc"):
            print(f"  Overall: {result.get('overall')}")
            print(f"  Applicability: {result.get('applicability_set')}")
            print(f"  Gate: {result.get('gate_status')}")
            for d, v in result.get("dimensions", {}).items():
                print(f"  - {d}: {v.get('score')} (applicable={v.get('applicable')})")
        else:
            print("  (not an HPC project)")


if __name__ == "__main__":
    main()
