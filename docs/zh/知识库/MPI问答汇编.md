# MPI问答汇编（今日会话 Q&A 汇编）

> **命名**：MPI问答汇编（原 "MPI QA"）
> **内容**：本次会话全部问答（按主题分组，答案为摘要；细节见各链接文档）
> **日期**：2026-10-21
> **落点**：`docs/zh/知识库/`（用户口径 "zh/DOC/知识库"）

---

## 目录

- A. H3 规划与治理（Q1–Q6、Q16–Q17）
- B. 智能体与知识库（Q7–Q8）
- C. WP-0 基线实测与 G0（Q9–Q13）
- D. 归一化与权重（Q14–Q15）
- E. WP-9 H2 遗留缺陷（Q18）
- F. WP-3 维度⑥ + 设计依据 + 专家校对（Q19–Q26）
- G. HPC 知识速览（Q27–Q32）
- H. 评分行为与 LLM（Q33–Q35、Q40 详版）
- I. 报告整理（Q36–Q39）
- J. HPC 知识详细版（Q41–Q46，对应 G 组）
- K. HPC 进阶问答详细版（Q47–Q55：halo/通信子拓扑/OpenMP举例/假共享/嵌套/非线程安全/浮点归约/TBB·Taskflow）
- L. HPC 补充详细版（Q56–Q57：数据常驻 / 执行配置 HPC-003）
- M. HPC 进阶问答详细版（Q58–Q72）
- N. 指南完善记录（v0.4→v0.7）


## 关键词索引（速查）

> 用法：先按主题找关键词，再跳到对应 Q 号。

### HPC 概念
| 关键词 | 问答 |
|:--|:--|
| 域分解 / 分区 / domain decomposition | Q27、Q41 |
| halo / ghost / 边界副本 | Q47 |
| halo「一层」/ stencil 宽度 | Q48 |
| 通信子 / communicator / Comm_split / Comm_dup | Q49 |
| 拓扑 / cartesian / Cart_shift / reorder | Q49 |
| 负载均衡 / 加权分区 / p4est / PartitionWeights | Q41、Q26 |
| 强/弱扩展 | Q41 |

### MPI
| 关键词 | 问答 |
|:--|:--|
| MPI 基础 / rank / size / tag | Q28、Q42 |
| 点对点 / Send / Recv / Sendrecv / Isend / Wait | Q42 |
| 集合通信 / Allreduce / Bcast / Barrier | Q42 |
| 死锁 / 阻塞 vs 非阻塞 | Q42、Q47 |
| 线程级 / THREAD_MULTIPLE / FUNNELED / SERIALIZED | Q42、Q53 |
| CUDA-aware MPI / RMA | Q42 |

### OpenMP
| 关键词 | 问答 |
|:--|:--|
| OpenMP 基础 / 并行域 / fork-join | Q29、Q43、Q50 |
| 数据作用域 / shared / private / reduction | Q43、Q50 |
| 调度 / static / dynamic / guided | Q43、Q50 |
| 假共享 / cache line / padding / alignas | Q51 |
| 并行域嵌套 / 假并行（嵌套默认关闭）| Q52 |
| 非线程安全函数 / rand / strtok / localtime | Q53 |
| MPI×OpenMP 混合 | Q43、Q52、Q53 |
| TBB / Taskflow | Q55 |

### GPU / target
| 关键词 | 问答 |
|:--|:--|
| target offload | Q30、Q44 |
| map / to / from / tofrom / alloc | Q44、Q56 |
| 数据常驻 / target data / enter/exit data / update | Q56 |
| 执行配置 / num_teams / thread_limit / 硬编码 launch | Q57 |
| 设备守卫 / omp_get_num_devices / omp_is_initial_device / 静默回退 | Q44、Q57 |
| teams / distribute / parallel for / simd 层级 | Q44、Q57 |
| 编译器后端 / outline / fat binary / libomptarget | Q31、Q45 |
| PTX / SASS / AMDGCN / HSACO / SPIR-V / sm_XX / gfx | Q32、Q46 |

### 数值
| 关键词 | 问答 |
|:--|:--|
| 浮点归约 / 结合律 / CPU-GPU 分歧 / FMA / Kahan | Q54 |

### 规则 → 问答
| 规则 | 问答 |
|:--|:--|
| HPC-001 CPU/GPU 双实现一致性 | Q24、Q45、Q54 |
| HPC-002 设备可用性守卫 | Q24、Q44 |
| HPC-003 launch 配置硬编码 | Q57 |
| HPC-004 H2D/D2H 冗余搬运 | Q44、Q56 |
| HPC-005 halo 交换配对 | Q41、Q47、Q48 |
| HPC-006 热循环集合通信 | Q42 |
| HPC-007 通信/计算重叠 | Q41、Q47 |
| HPC-008 负载划分加权 | Q26、Q41 |
| HPC-009 拓扑/通信子（窄化 INFO）| Q49 |
| HPC-010 线程安全 MPI | Q26、Q53 |
| HPC-011 OpenMP 共享变量 | Q43、Q50 |
| HPC-012 并行域嵌套 | Q52 |
| HPC-013/014 运行时扩展性/负载 | Q41（概念）；运行时项见设计依据 |

### 方法论 / 治理
| 关键词 | 问答/文档 |
|:--|:--|
| 专家校对实证法（源码 rg 核验）| Q22、Q24、Q26 |
| 正样本 / 负样本校准 | Q24、Q26 |
| 启发式 vs LLM / LLM 精判 | Q34、Q35、Q40 |
| 验证不确定度 U_V / E=S−D | Q62、Q72 |
| U_D 实验不确定度 / GUM / A类B类 | Q72 |
| U_SN 数值不确定度 / GCI / 迭代 / 时间步 | Q63、Q72 |
| U_input 输入不确定度 / 灵敏度传播 / 蒙特卡洛 | Q72 |
| 覆盖率 / k=2 / 95% | Q72 |
| 验证域 / 外推 | Q62、Q72 |
| Agent 处理「低分」红线 | Q33 |
| 敏感性分析（稳定区间 / Kendall τ）| Q14、Q15 |
| 归一化（激活子集，Σw'=1）| 见《HPC评估方法论与知识速览》§1.5 |
| 回归基线「祝福」与程序化校验 | 见《HPC评估方法论与知识速览》§1.1 |

---

## A. H3 规划与治理

**Q1 请制订 H3 执行计划，并考虑 H1/H2 遗留问题。**
A：从 `H3待办清单`（25 项 A~G）出发，产出 `H3全维化执行计划v1.1`，把 H1 遗留（TPL 迁移/NVR-009/MPR-011/SOLID 正则）与 H2 遗留（归一化/multilang 性能/隐式实例化/ACL 校准/G1~G4）逐条映射到工作包，25/25 无悬空。目标：8/8 维度 + 归一化 + 智能体深化。

**Q2 H3 到哪一步？**
A：多次询问；最新状态：**WP-0 / WP-1 / WP-2 / WP-9 已完成，WP-3 进行中（阶段 1-2），其余待办**。详见 `H3阶段进展与决策记录.md`。

**Q3 5 项决策怎么选？**
A：①倾向(a)增强总分作超级维度；②倾向(a)求解器调权作 profile 覆盖；③实施 B2/B3/B5；④双维全量落地；⑤有偏移→语义变更重设基线。已写入计划 v1.1。

**Q4 送专家评审。**
A：产出 `H3专家评审报告.md`，评分 **65/100**，指出三大缺口（KPI 不可门禁、归一化工具衔接缺失、新维度可行性未分级），must-adopt 8 条。

**Q5 按 must-adopt 8 条修订 v2。**
A：产出 `H3全维化执行计划v2.md`：工具硬编码前缀改造、schema 扩展、KPI2 独立锚点、矩阵口径（B7 保持 KNOWN_HOLES→108）、KPI3 统一、基线程序化校验、新增 WP-11 跨环境、⑥⑦ 可行性分级。

**Q6 工作包 A1/A2/E1/F1/D1 是什么？**
A：A1=激活子集归一化；A2=维度权重定案；D1=TPL 编号迁移；E1=ACL 科学内核符号集；F1=元模型 §5.2 样本回填。均为 `H3待办清单` 的条目编号（字母=类别，数字=序号）。

**Q16 H2 到哪一步？**
A：**H2 阶段已 Closeout**（2026-10-16，KPI1~6 达标）；其遗留已全部并入 H3，归一化与权重已在 H3 WP-1/2 完成，其余在 H3 WP-5/6/8/9。

**Q17 H3 到哪一步？**（同 Q2）

---

## B. 智能体与知识库

**Q7 opencode agent 如何管理"用户记忆"和"知识库"？**
A：**没有内置持久记忆库**。记忆=分层上下文：`AGENTS.md`（项目指令，自动注入）+ agent 提示词（`prompt_file`）+ 按需 `skill` 注入 + 会话历史（易失）。知识库是**外置 Obsidian 库**（`D:\opensource\knowledge-base`），靠 `knowledge-base-management` skill + `extract_highlights.py` + Git 管理（日报→亮点→技术卡→索引）。

**Q8 上下文如何感知知识库？**
A：**靠 agent 系统提示词静态声明**（`.opencode/agents/architecture-quality.md` 的 `## Knowledge Base` + Rules #10），随会话注入；**内容不自动进上下文**，由 agent 运行时 `read/grep/bash` 主动读取（无向量检索/自动同步）。

---

## C. WP-0 基线实测与 G0

**Q9 给出 WP-0 方案。**
A：`H3-WP0基线实测方案.md`：T0.1 冻结、T0.2 归一化前基线（7 项目）、T0.3 性能、T0.4 ACL 计数、T0.5 语料、T0.6 G0、T0.7 跨环境铺垫。

**Q10 决策选 4（先做 T0.6 再定）。**
A：把 T0.6 前置为 **G0 门禁**，用实测数据决定 B2/B3/B5 归属。

**Q11 需要，实施（WP-0）。**
A：完成 T0.1~T0.7：7 项目基线、FreeCAD 7 引擎 **770.4s**（multilang 264.1s 超预算）、OCCT GCS-003=39、deal.II MLR-018=47636、ACL 计数；产出 `H3基线实测报告.md`。

**Q12 解释方法 A（apt）的结论。**
A：ubuntu-latest apt 的 OCCT=**7.6.3** ≠ 样本 **V8.0.1**（大版本差异、Debian 补丁），运行内核与静态基线不一致 → **否决 apt**。

**Q13 使用推荐方法。**
A：落地**方法 C：预构建 OCCT V8.0.1 缓存 + 专用 job**（`.github/workflows` 的 `runtime-kernel` + `scripts/ci/*`），不阻塞 PR，禁用 apt 7.6.3。

---

## D. 归一化与权重

**Q14 详细解释敏感性计算。**
A：OAT 网格扫描：读 WP-0 冻结的各维得分（与权重无关，改权重零成本重算 overall）→ 逐维在 `{0.05..0.20}` 取值 → 指标 max|Δoverall| / **Kendall τ**（排名）/ 等级变化（85/70/50）→ **稳定区间**（τ=1 且等级不变）。

**Q15 为什么要做敏感性分析？**
A：权重是主观先验、无唯一真值；LOOCV 测泛化、不能定权（评审意见 14）。敏感性分析检验"结论对权重的稳健性"，给出稳定区间供专家在区间内定值，并识别关键/非关键维度（numerical 最敏感）。

---

## E. WP-9 H2 遗留缺陷

**Q18 选 2（实施 WP-9）。**
A：G1 GCS 路径判定、G2 §2.1 对齐、G3 `@kernel_exempt` reason 含 `*`、G4 ACL 校准（STEPPlugin 识别 + 内核自身排除）。salome ACL-007 **40→0**、overall **26.5→47.5**；H2-002/003/P2-1 闭环；新增 7 测试、ACL 回归 12 passed。

---

## F. WP-3 维度⑥ + 设计依据 + 专家校对

**Q19 准备 WP-3 方案。**
A：维度⑥"并行/异构计算架构（HPC/GPU）"全链路：4 子维（后端/MPI-halo/负载/混合并行）+ 12 规则 + 文档包 + 引擎 + 回归 ≥5 + 集成点清单。

**Q20 Q1–Q5 全采纳，分阶段推进。**
A：4 子维 30/30/20/20；12 规则；语料 OpenFOAM/deal.II/SU2/Elmer/MFEM；顶层 0.15；KNOWN_HOLES HPC-013/014。按编制指南 5 阶段推进。

**Q21 设计依据太简单，研究其他维度完善。**
A：研读 GCS/求解器设计依据（~275–320 行），重写为 **v0.2（350 行）**：颗粒度/检查项/递进层级、5 类架构模式+编排谱系、5 本质差异、五案例"问题→方案→指标"表、四层催熟三证据、体系衔接、总体结论、术语表。

**Q22 专家校对，至少 5 个问题，含案例证据可溯源/无杜撰。**
A：产出 `设计依据专家校对报告.md`（基于本地源码 `rg` 实证）：**P0×2**（SU2 被当 GPU 样本=杜撰，全仓唯一 CUDA 命中 `externals/catch2.hpp`；案例缺锚点）、**P1×5**（deal.II 归属、V&V20 误引、HPC-009 假阳性、递进扣分、静态可检性夸大）、**P2×2**。
**Q23 选 A（修订）。**
A：设计依据改 **v0.3**：SU2 去 GPU、补附录 A 锚点、deal.II 改 TBB、V&V20 改方法学、HPC-009 窄化 INFO、去递进折半、加可行性预告、halo 表述精化、MPI-2.0 说明；第二轮复核**通过**。

**Q24 MFEM 验证。**
A：`Device`/`Configure`/`Allows`/`MFEM_USE_CUDA/HIP` **属实**；但 `.cu/.hip=0`、`MFEM_HOST_DEVICE` 191 → **统一单源内核**，launch 抽象在 `general/forall.hpp`。故 MFEM 对 **HPC-002** 是运行期守卫正样本；对 **HPC-001/003** 是**正样本（最佳实践，不应触发）**，缺陷阳性需 C 类合成。

**Q25 要（应用修正）。**
A：设计依据 5 处 MFEM 表述修正 + 第二轮报告 §六 记录。

**Q26 继续核验 OpenFOAM/deal.II/SU2。**
A：三者均为**正样本（健康）**：OpenFOAM（成对 `UOPstream/UIPstream` + `initInterfaceMatrixUpdate`，≈纯 MPI）→ HPC-005/007；deal.II（`PartitionWeights`/`get_cell_weights` 加权 p4est + TBB 线程）→ HPC-008；SU2（`MPI_Init_thread` 默认 FUNNELED、`--thread_multiple` 启 MULTIPLE）→ HPC-010。**校准原则**：四样本为正样本，缺陷样本须 C 类合成。已同步第二轮报告 §七。

---

## G. HPC 知识速览

**Q27 解释域分解。**
A：把大计算域切成子域、每子域交给一个 MPI 进程；流程=网格→分区→绑定 rank→halo 层→迭代交换。算法：几何/图(METIS/Scotch)/SFC(p4est)。OpenFOAM `decomposePar`、deal.II `p4est`。质量→HPC-005/007/008。

**Q28 介绍 MPI。**
A：分布式内存并行标准（进程独立内存、显式消息）。核心：rank/size/communicator/tag/datatype。原语：点对点（Send/Recv/Sendrecv/Isend/Irecv）、集合（Bcast/Allreduce/Barrier…）。坑：死锁、阻塞/非阻塞、**线程级（MPI-2.0 起）**、comm_split/拓扑、CUDA-aware。→HPC-005/006/007/010。

**Q29 介绍 OpenMP。**
A：共享内存多线程（`#pragma omp`）。概念：并行域/fork-join/工作共享/**数据作用域(shared/private/reduction)**/同步/调度。最大坑：数据竞争（缺 reduction）、假共享、并行域嵌套、并行区调非线程安全函数。→HPC-011/012/010。

**Q30 解释 target 异构 offload。**
A：`#pragma omp target` 把代码卸载到 GPU（一次编写）。`map(to/from/tofrom)` 管搬运（→HPC-004）、`teams/thread_limit` 管 launch（→HPC-003）、`omp_get_num_devices`/`omp_is_initial_device` 管守卫与回退（→HPC-002）；同源两次编译→数值分歧（→HPC-001）。

**Q31 解释"编译器后端翻译成 CUDA/HIP/其他 device 代码"。**
A：编译器把 target 区域外提成设备函数，用 LLVM NVPTX / AMDGPU / SPIR-V 后端降级成 **PTX / AMDGCN / SPIR-V**，由 libomptarget/libgomp 在设备加载；`teams→grid`、`thread_limit→block`、`map→memcpy`。多为 **IR lowering**，非源码生成 `.cu`。

**Q32 介绍 PTX / AMDGCN / SPIR-V。**
A：PTX=NVIDIA **虚拟 ISA**（文本、向前兼容，驱动 JIT 成 SASS）；AMDGCN=AMD **本机 ISA**（二进制、按 gfx、HSACO 由 HSA 加载）；SPIR-V=Khronos **便携二进制 IR**（跨厂商，由各驱动编到本机 ISA）。影响 HPC-001（数值分歧）/HPC-002（版本守卫）。

---

## H. 评分行为与 LLM

**Q33 智能体感觉某维度分太低怎么处理？**
A：**不调分**（分数由确定性引擎产出；评估 agent `edit/write=deny`）。流程：复核输入（子模块/build-dir/profile/test-dirs/Git）→ 拆解定位 → 归因（真低分/工具误判/语义权重）→ 真低分如实报告+建议；误判走校准（登记→对抗性验证→修引擎→带校验重设基线）。红线：不调阈值/权重/跳规则/忽略 ERROR/手改快照。

**Q34 启发式评估能否交给 LLM，会更准吗？**
A：能但不该"替代"，应**分层混合**：确定性启发式做计数/门禁/事实；LLM 做语义级候选精判与解释。LLM 风险：非确定性、幻觉（如 SU2 GPU 乌龙）、不可审计、成本、漂移。需**人工标注金标准 + P/R/F1 证明"更准"**，否则是主观断言。

**Q35 "LLM 精判"是什么意思？**
A：在启发式圈出的**候选**上做精确裁决（**确认/否决/降级/存疑**），目标提高精度（少误报），不是从头扫代码、不是打分。输入候选+证据；输出结构化 JSON（verdict/confidence/evidence `file:line`/reason）。红线：必须证据、无证据不采信、低置信降级 INFO、不生成候选、不改分。

**Q40 启发式评估能否交给 LLM？（详细版）**

> 结论：**分场景**。语义级/跨函数/意图类 LLM 通常更准（尤其 precision）；计数/确定性/事实存在性类 LLM 更差。正确姿势是**分层混合**，且"更准"必须用人工标注金标准证明。

1. **先定义"准"**：同任务、同标注标准下用 Precision / Recall / F1（+ 置信区间）。没有金标准，"更准"只是主观感觉。
2. **LLM 更准的场景**：跨函数/跨文件判定（`Isend` 的 `Wait` 在别的封装里）、意图/开放判断（负载是否加权、热循环 Allreduce 是否可局部化）、解释与建议、宏/模板/生成代码。
3. **LLM 更差的场景**：计数/统计（环数/密度/复杂度）、事实存在性（测试/头文件/import）、门禁/回归（需确定性）、大规模逐文件（成本）。
   - 真实教训：本会话曾把 SU2 说成"有 CUDA/GPU 后端"，源码核验发现全仓唯一命中第三方 `catch2.hpp` → LLM 会凭印象泛化出错。
4. **三种用法**：① 运行期替代（不推荐，非确定/不可门禁/成本高）；② **两段式精判**（启发式召回 → LLM 在候选上 confirm/reject/降级，推荐）；③ **离线规则工程**（LLM 起草规则/做初筛标注/分析假阳性，最终落确定性规则，性价比最高）。
5. **规则分类**：计数/门禁/复杂度/事实存在性 → 确定性；语义级/跨函数/意图 → LLM 精判（输出候选，不直接定论）；报告叙述/排序/建议 → LLM（不碰分）。
6. **如何证明"更准"**：建人工标注金标准（双人独立+仲裁）→ held-out 评估集（防自证）→ 对比 纯启发式/纯 LLM/混合 的 P/R/F1 → 对齐 H1 KPI5（核心规则假阳性 ≤10%）、H2 KPI4（标注一致率 ≥90%）。
7. **运行期约束（若上）**：证据锚定 `file:line`、无证据不采信、低置信降级 INFO、温度 0 + 固定模型/提示词版本、结果落盘进回归、只对低置信/语义级规则调用控成本。
8. **一句话**：能交给 LLM，但不该替代启发式；确定性负责可复现门禁，LLM 负责语义候选精判与离线规则工程，且须**证据 + 金标准**验证。

---

## I. 报告整理

**Q36 能否整理成报告？**
A：可以；给出单篇/两篇方案与结构。

**Q37 选 B（两篇）。**
A：`H3阶段进展与决策记录.md`（工程线）+ `HPC评估方法论与知识速览.md`（方法论+入门）。

**Q38 批准（写两篇）。**
A：已产出两篇（183 行 / 281 行），互链、标注证据口径（【已验证】/【建议】）。

**Q39 把今日 Q&A 整理成 "MPI QA"（本文件）。**

---

## J. HPC 知识详细版（Q41–Q46，对应 G 组 Q27–Q32）

> 说明：G 组给的是速览；本节是**详细版**（概念表/示例/对比/映射），供深入学习。

### Q41 域分解（Domain Decomposition）详细版

**定义**：把一个大计算域切成若干**子域**，每个子域交给一个 MPI 进程并行求解——把"一个巨型问题"变成"多个可并行的小问题"。

**为什么**：
| 目的 | 机制 |
|:--|:--|
| 内存 | 每进程只持有自己那片网格/场量 |
| 算力 | 多进程同时算各自子域，缩短墙钟 |
| 扩展 | 加节点 = 切更碎、分给更多 rank |

**流程**：
```
全域网格 ──分区──► [P0][P1][P2][P3]   (每子域绑定 rank)
                     │
            建立 halo/ghost 层（记录邻居）
                     │
            迭代中交换 halo 数据 → 各算子域 → 汇总
```

**核心概念**：
| 概念 | 含义 |
|:--|:--|
| 子域/分区 | 切出的一块网格 |
| rank/进程 | 一个子域通常对应一个 MPI rank |
| halo/ghost | 相邻子域边界数据的复制层 |
| halo 宽度 | 必须 ≥ stencil 阶数（如 4 阶差分≥2 层）|
| 重叠 overlap | 计算时"看似重叠"（Schwarz 靠重叠带迭代）|
| 界面 interface | 子域交界，越多通信越重 |
| 负载均衡 | 各子域工作量接近，否则个别 rank 拖尾 |

**两大类**：
| 类型 | 特点 | 代表 |
|:--|:--|:--|
| 非重叠（子结构）| 子域不相交，靠 halo 交换 | OpenFOAM、deal.II |
| 重叠（Schwarz）| 子域间有重叠带，迭代收敛 | 区域分解预条件子 |

> 与**功能分解**区分：域分解=按**空间**切数据；功能分解=按**物理场/任务**分进程。

**分区算法**：① 几何法（按坐标切，简单但不规则域效果差）；② 图法（METIS/Scotch，最小化跨分区边）；③ 空间填充曲线 SFC（Hilbert/Morton，p4est）；④ 手工/多级图划分。

**实例**：
- **OpenFOAM**：`decomposePar` + `system/decomposeParDict`（`numberOfSubdomains` + `method`: simple/hierarchical/scotch/metis/manual），生成 `processor0..N` 与 `processor*` 边界（halo 载体 `processorPolyPatch`）。
- **deal.II**：`p4est` 森林（八叉树+SFC）分区、`GridTools::partition_triangulation`、`parallel::distributed::Triangulation`；支持 `PartitionWeights`/`get_cell_weights` 加权（默认按单元数）。

**映射规则**：HPC-008（负载加权）、HPC-005（halo 配对）、HPC-007（重叠）、HPC-009（拓扑/通信子，窄化 INFO）。

---

### Q42 MPI（Message Passing Interface）详细版

**定义**：分布式内存并行的事实标准——进程各有独立地址空间，靠**显式消息**协作。

**两模型**：
| 模型 | 代表 | 内存 | 通信 |
|:--|:--|:--|:--|
| 共享内存（线程）| OpenMP/TBB | 共享地址空间 | 读写共享变量 |
| 分布式内存（进程）| **MPI** | 每进程独立 | 显式发消息 |

**核心概念**：`rank`（编号 0..size-1）、`size`（总数）、`communicator`（通信子，如 `MPI_COMM_WORLD`）、`tag`（消息标签）、`datatype`（元素类型，支持自定义）、SPMD（同一程序，按 rank 决定数据片）。

**点对点**：
```
MPI_Send(buf,count,type,dest,tag,comm);
MPI_Recv(buf,count,type,src,tag,comm,&st);
MPI_Sendrecv(...);                       // 收+发原子完成，防死锁
MPI_Isend/Irecv + MPI_Wait/Test          // 非阻塞，可重叠计算
```
> halo 交换就是点对点；**成对**是关键，否则死锁/数据错（HPC-005）。

**集合通信**：`Bcast`（广播）、`Scatter/Gather`（分发/收集）、`Allgather`、`Reduce/Allreduce`（归约，Allreduce 每人都拿到）、`Alltoall`、`Barrier`（同步屏障）。集合通信是同步点，热循环里影响扩展性（HPC-006）。

**关键点**：
1. **死锁**：两 rank 都先阻塞 `Send` 互相等 → 卡死；解法 `Sendrecv` 或 `Isend/Irecv`+`Waitall`。
2. **阻塞 vs 非阻塞**：非阻塞让通信与计算重叠（HPC-007），但 `Isend` 后必须 `Wait/Test`，否则缓冲复用竞态。
3. **线程级（自 MPI-2.0）**：`MPI_Init_thread` 声明级别：

| 级别 | 含义 |
|:--|:--|
| SINGLE | 单线程 |
| FUNNELED | 只有主线程调 MPI（最常用，SU2 默认）|
| SERIALIZED | 多线程但调用需串行化 |
| MULTIPLE | 任意线程可随时调（需实现支持）|

4. **通信子/拓扑**：`MPI_Comm_split` 分组；`MPI_Cart_create` 笛卡尔拓扑（HPC-009，未用本身不判罚）。
5. **CUDA-aware MPI**：GPU 缓冲直传，免显式 H2D/D2H。
6. **单边通信（RMA，MPI-3）**：`MPI_Put/Get` 读写远端内存。

**最小示例**：
```c
#include <mpi.h>
int main(int argc, char** argv){
    MPI_Init(&argc,&argv);
    int rank,size; MPI_Comm_rank(MPI_COMM_WORLD,&rank); MPI_Comm_size(MPI_COMM_WORLD,&size);
    double local=rank+1.0, global;
    MPI_Allreduce(&local,&global,1,MPI_DOUBLE,MPI_SUM,MPI_COMM_WORLD);
    MPI_Finalize(); return 0;
}
```
halo 骨架：
```c
MPI_Request req[2];
MPI_Isend(send_buf,n,MPI_DOUBLE,left, 0,comm,&req[0]);
MPI_Irecv(recv_buf,n,MPI_DOUBLE,right,0,comm,&req[1]);
/* 可先算内部区域（通信/计算重叠） */
MPI_Waitall(2,req,MPI_STATUSES_IGNORE);
```

**版本/实现/工具**：标准 MPI 4.1（线程级自 2.0、RMA 自 3）；实现 OpenMPI/MPICH/Intel MPI/MVAPICH/MS-MPI；工具 MUST/MPI-Checker、TAU/Score-P。

**映射规则**：HPC-005/006/007/010（+009 窄化 INFO）。

---

### Q43 OpenMP（共享内存多线程）详细版

**定义**：`#pragma omp` 把串行代码的循环/代码块自动分给多线程，跑单节点共享内存；常与 MPI 组混合并行。

**定位**：
| 模型 | 内存 | 粒度 | 场景 |
|:--|:--|:--|:--|
| MPI | 分布式 | 进程/跨节点 | 大算例聚类 |
| **OpenMP** | **共享** | **线程/单节点多核** | 节点内加速 |
| MPI×OpenMP | 混合 | 节点间 MPI+节点内线程 | 多核 cluster |

**核心概念**：线程、**并行域**（`#pragma omp parallel {}`）、fork-join、**工作共享**（for/sections/single）、**数据作用域**（shared/private/firstprivate/reduction）、同步（barrier/critical/atomic/lock）、调度（static/dynamic/guided）。

**常用指令**：
```c
#pragma omp parallel for reduction(+:s) schedule(static)
for (int i=0;i<n;i++) s += a[i]*a[i];

#pragma omp parallel
{
    #pragma omp for
    for (int i=0;i<n;i++) b[i]=f(a[i]);
    #pragma omp single
    printf("done by %d threads\n", omp_get_num_threads());
}

#pragma omp critical
{ shared_counter++; }        // 或 #pragma omp atomic

#pragma omp parallel
#pragma omp single
{ for (auto&t:tasks){ #pragma omp task
                      process(t);} }

#pragma omp target teams distribute parallel for   // GPU offload（见 Q44）
for (int i=0;i<n;i++) c[i]=a[i]+b[i];
```
API：`omp_get_thread_num()`、`omp_get_num_threads()`；环境变量 `OMP_NUM_THREADS=8`。

**数据作用域（最易错）**：
```c
// ❌ 错误：s 是 shared，多线程同时 += → 竞态
#pragma omp parallel for
for (int i=0;i<n;i++) s += a[i];

// ✅ 正确：reduction 私有副本 + 归约
#pragma omp parallel for reduction(+:s)
for (int i=0;i<n;i++) s += a[i];
```
| 子句 | 作用 |
|:--|:--|
| `shared(x)` | 所有线程同一份 |
| `private(x)` | 每线程一份未初始化副本 |
| `firstprivate(x)` | 每线程一份，用进入前值初始化 |
| `reduction(+:s)` | 私有副本，退出时按 `+` 合并 |
| `nowait` | 取消结束时的隐式 barrier |

**常见陷阱（对应规则）**：① 数据竞争（缺 private/reduction，HPC-011）；② 假共享（相邻元素同 cache line）；③ 并行域嵌套（HPC-012）；④ 并行区调非线程安全函数（`rand`、非 MULTIPLE 的 MPI → HPC-010）；⑤ 浮点归约顺序不确定（CPU/GPU 分歧来源，HPC-001）。

**与 MPI 混合**：节点间 MPI + 节点内 OpenMP；常用 **FUNNELED**（主线程碰 MPI）最安全（SU2 默认 `FUNNELED`，`--thread_multiple` 才升 MULTIPLE）。不要在 `omp parallel` 里随意调 MPI。

**对比**：TBB/Taskflow（deal.II 主力，任务/图并行）、std::thread（手写）、Kokkos/RAJA/SYCL（性能可移植）。

**映射规则**：HPC-011/012/010。

---

### Q44 OpenMP target 异构 offload 详细版

**定义**：`#pragma omp target` 把一段代码卸载到加速器（GPU/FPGA）执行，同一份代码 CPU/GPU 都能跑（性能可移植）。

**为什么/路线**：
| 路线 | 特点 |
|:--|:--|
| CUDA/HIP（如 MFEM `Device`）| 厂商专有、控制细、性能好 |
| **OpenMP target** | 标准、可移植、控制力略低 |
| Kokkos/RAJA | C++ 抽象层，"一次编写多后端" |

**执行模型**：
```
host(CPU)                      device(GPU)
────────                      ───────────
 数据 ──map(to)──►             设备内存
 #pragma omp target ────────►  teams(线程组/CTA)
   ... 计算 ...                  └ parallel for → 线程
 结果 ◄──map(from)──
```

**数据映射（HPC-004）**：
```c
#pragma omp target teams distribute parallel for map(to:a[0:n]) map(from:b[0:n])
for (int i=0;i<n;i++) b[i]=a[i]*2.0;
```
| 子句 | 方向 |
|:--|:--|
| `map(to:x)` | 主机→设备（只读输入）|
| `map(from:y)` | 设备→主机（输出）|
| `map(tofrom:z)` | 双向 |
| `map(alloc:buf)` | 只在设备分配 |

**数据常驻**（多次 kernel 复用，避免反复搬运）：
```c
#pragma omp target data map(to:a[0:n]) map(tofrom:b[0:n])
{
    #pragma omp target teams distribute parallel for
    for (int i=0;i<n;i++) b[i]=a[i]*2.0;
    #pragma omp target teams distribute parallel for
    for (int i=0;i<n;i++) b[i]+=1.0;
}
```
> 循环内反复 `map` = H2D/D2H 冗余搬运（HPC-004）。

**执行配置（HPC-003）**：`num_teams(T)` ≈ gridDim、`thread_limit(B)` ≈ blockDim；应按数据规模计算，写死魔法数即"硬编码 launch"。

**设备守卫（HPC-002）**：
```c
int ndev = omp_get_num_devices();      // 0 = 无加速器
int on_host;
#pragma omp target map(from:on_host)
{ on_host = omp_is_initial_device(); } // 1=主机, 0=设备
```
> 无设备/失败时 OpenMP 可能**静默回退 CPU**；不查 `omp_is_initial_device()` 会误以为在 GPU 跑。

**与 CUDA/HIP 关系**：target device 代码最终由编译器后端生成 CUDA/HIP（见 Q45）；OpenMP target 属"可移植异构"路线，评估仍归 HPC-001/002/003/004。

**常见陷阱**：忘 `map`/方向错（HPC-001/004）、循环内反复 map（HPC-004）、launch 硬编码（HPC-003）、不查设备/回退（HPC-002）、target 区调未 `declare target` 的函数、CPU/GPU 归约顺序差异（HPC-001）。

**完整示例**：
```c
#include <omp.h>
#include <stdlib.h>
#include <stdio.h>
int main(){
    int n=1<<20;
    double *a=malloc(n*sizeof(double)), *b=malloc(n*sizeof(double));
    for(int i=0;i<n;i++) a[i]=1.0;
    if(omp_get_num_devices()>0){
        #pragma omp target data map(to:a[0:n]) map(from:b[0:n])
        {
            #pragma omp target teams distribute parallel for
            for(int i=0;i<n;i++) b[i]=a[i]*2.0;
            #pragma omp target teams distribute parallel for
            for(int i=0;i<n;i++) b[i]+=1.0;
        }
    } else {
        for(int i=0;i<n;i++) b[i]=a[i]*2.0+1.0;   // CPU 回退
    }
    printf("b[0]=%f\n", b[0]);  // 期望 3.0
    free(a); free(b); return 0;
}
```

---

### Q45 "编译器后端翻译成 CUDA/HIP/其他 device 代码"详细版

**一句话**：编译器把 `#pragma omp target` 区域**外提**成设备函数，用 LLVM NVPTX / AMDGPU / SPIR-V 后端降级成设备二进制（**PTX / AMDGCN / SPIR-V**），由 `libomptarget`/`libgomp` 在设备加载执行。**"翻译成 CUDA/HIP"= IR 级 lowering，不是源码生成 `.cu`**（少数/旧方案才 source-to-source）。

**流水线**：
```
your.c (#pragma omp target)
   │ 前端：target 区域 outline 成独立设备函数
   ├──► 主机编译：host.o（启动桩 + 数据映射代码）
   └──► 设备编译（offload backend）：device.bin（PTX/AMDGCN/SPIR-V）
        └──► 打包成 fat binary / 多架构镜像 → 运行时加载
```

**四步**：① Outline（外提，隐式 `declare target`）；② 主机侧启动桩+映射；③ 设备侧编成设备二进制；④ 打包 fat binary，运行时按设备选择。

**后端产出**：
| 编译器 | 开关示例 | 设备后端/产物 | 运行时 |
|:--|:--|:--|:--|
| Clang | `-fopenmp-targets=nvptx64-nvidia-cuda` | LLVM NVPTX → **PTX** | libomptarget+CUDA 插件 |
| Clang | `-fopenmp-targets=amdgcn-amd-amdhsa` | LLVM AMDGPU → **AMDGCN/HSACO** | libomptarget+AMD 插件 |
| GCC | `-foffload=nvptx-none` | GCC NVPTX → PTX | libgomp+nvptx 插件 |
| GCC | `-foffload=amdgcn-amd-amdhsa` | 内嵌 LLVM AMDGPU | libgomp+gcn 插件 |
| Intel | `-fiopenmp -fopenmp-targets=spir64` | **SPIR-V** → Level Zero/OpenCL | Level Zero |
| NVHPC | `-mp=gpu` | NVVM → PTX | CUDA driver |

**指令映射**：`teams→grid/block`、`num_teams→gridDim`、`thread_limit→blockDim`、`distribute→迭代分给 team`、`parallel for→team 内线程`、`simd→向量化`、`map(to/from)→cudaMemcpy`、`target data→设备常驻映射表`。

**运行时（libomptarget）**：初始化设备/插件 → 按 map 分配+memcpy(H2D) → 加载 kernel（PTX→SASS 由驱动 JIT）→ 启动（grid/block）→ map(from) 拷回 → 释放。

**与 HPC-001 的关系**：target 代码**编译两次**（主机+设备），FMA 收缩/向量化/归约顺序不同 → 同一算子 CPU/GPU 结果有微小差异；这是 HPC-001 的隐蔽来源。

---

### Q46 PTX / AMDGCN / SPIR-V 详细版

**层级**：
```
源码 → 编译器IR → [虚拟ISA/便携IR] → [本机ISA]
CUDA   → NVVM    → PTX            → SASS      (NVIDIA)
HIP    → LLVM IR → AMDGCN(LLVM)   → HSACO     (AMD)
SYCL/OpenCL/OpenMP → SPIR-V       → Gen/Xe ISA (Intel 等)
```

**PTX（NVIDIA，Parallel Thread Execution）**：**虚拟 ISA**（非最终机器码）。nvcc/Clang NVPTX 编出 PTX（文本、虚拟寄存器/线程），驱动/`ptxas` 再 JIT/汇编成 **SASS**（`sm_80`/`sm_90`/`sm_100`）。**关键：向前兼容**——一份 PTX 可在未来 GPU 上由驱动 JIT。文件含 `.version`/`.target`/`.address_size`；特殊寄存器 `%tid.x`/`%ctaid.x`；内存空间 global/shared/local/constant/param。

**AMDGCN（AMD）**：**本机 ISA**（面向具体 gfx 架构）。架构族 GCN→RDNA/CDNA；目标 `gfx90a`(MI200)/`gfx942`(MI300)/`gfx1100`(RDNA3)。LLVM 三元组 `amdgcn-amd-amdhsa`（AMDGPU 后端）→ **HSACO**（ELF 机器码），由 **HSA/ROCm** 加载。与 PTX 区别：**AMDGCN 按 gfx，换架构通常需重编**（不向前兼容）。历史可移植层 HSAIL 已废弃。

**SPIR-V（Khronos）**：**便携二进制 IR**（非机器码、非虚拟 ISA，更抽象）。SPIR 是文本、SPIR-V 是二进制；被 OpenCL 2.1+/Vulkan/SYCL/OpenMP/WebGPU 工具链使用。编译器编成 SPIR-V → 厂商驱动编到本机：Intel IGC→Gen/Xe（Level Zero/OpenCL）、AMD ROCm→AMDGCN、NVIDIA 多经 Vulkan/OpenCL。好处：一份 IR 喂不同厂商驱动（性能可移植中间层），代价多一层、控制力不如直接 PTX/AMDGCN。

**对比**：
| | PTX（NVIDIA）| AMDGCN（AMD）| SPIR-V（Khronos）|
|:--|:--|:--|:--|
| 本质 | 虚拟 ISA | 本机 ISA | 便携二进制 IR |
| 产出 | nvcc/NVVM/NVPTX | LLVM AMDGPU | Clang/icx/SYCL |
| 消费 | CUDA 驱动/ptxas | HSA/ROCm | 各厂商驱动 |
| 最终码 | SASS | AMDGCN 机器码(HSACO) | Gen/Xe ISA 等 |
| 可移植 | 跨版本向前兼容 | 按 gfx，需重编 | 跨厂商 |
| 文本/二进制 | 文本 | 二进制 | 二进制 |
| 控制力 | 中高 | 高 | 中 |

**与维度关系**：不同 ISA/编译路径的 FMA/归约/精度差异 → CPU/GPU（跨厂商）结果微小差异（**HPC-001**）；PTX 向前兼容 / AMDGCN 需重编 / SPIR-V 依赖驱动 → 影响**设备/版本守卫**（**HPC-002**）。

---

---

## K. HPC 进阶问答详细版（Q47–Q55）

### Q47 halo / ghost 详细版

**定义**：相邻子域**边界数据的副本层**。每进程只拥有自己那片网格，但边界点做 stencil 时要读邻居的点，本进程没有 → 把邻居边界一层数据复制过来。

```
P0 的网格        P1 的网格
┌──────────┬──┐┌──┬──────────┐
│ 内部       │边││边│ 内部       │
└──────────┴──┘└──┴──────────┘
           └ halo ┘  ← 邻居边界层互相复制
```

| 要点 | 说明 |
|:--|:--|
| 为什么 | stencil 需要邻居点；跨进程不共享内存，只能复制 |
| 宽度 | ≥ stencil 阶数（2 阶≥1 层，4 阶≥2 层）；不够→边界算错 |
| 怎么来 | 迭代前 MPI 点对点交换（`Isend/Irecv`+`Waitall` 或 `Sendrecv`）|
| 成对性 | Send 必须有对应 Recv，否则死锁/数据错（**HPC-005**）|
| 通信量 | ≈ halo 面面积；界面越大越贵 |
| 别名 | OpenFOAM `processor` patch；VTK/gmsh 叫 ghost |
| 与重叠 | halo 让子域"看似重叠"（Schwarz 靠重叠带迭代）|

**一句话**：halo/ghost 是"让每个进程能算自己边界，而把邻居边界数据抄一份"的副本层；宽度、成对交换与同步决定正确性与通信开销（HPC-005/007）。

---

### Q48 halo "一层数据"详细版

"一层" = 在子域边界外**再复制一圈（一层）邻居单元的数据**，层数按单元/节点计数，与 stencil 跨度对应。

**1D 例子（2 阶中心差分，需 i±1）**：
```
全局:   0  1  2  3  4 │ 5  6  7  8  9
P0 拥有: 0  1  2  3  4 │(ghost: 5)
P1 拥有: (ghost: 4)│ 5  6  7  8  9
```
- P0 算单元 4（自己最右）需要单元 5（属 P1）→ P1 把单元 5 复制给 P0 = P0 的**一层 halo**；
- 反之 P0 复制单元 4 给 P1；"一层"= 每个邻居方向各 1 个单元厚。

**层数由 stencil 决定**：
| 差分精度 | 需要邻居 | halo 层数 |
|:--|:--|:--:|
| 2 阶中心（i±1）| 1 个 | **1 层** |
| 4 阶中心（i±2）| 2 个 | **2 层** |
| WENO/高阶重构 | 更宽 | 3+ 层 |

**2D/3D**：不是"一个单元"，而是**围子域的一圈"边框"**（各方向各一层，含角）；通信量 ≈ 周长 × 层数 × 场量数。

**"数据"是什么**：FV（单元中心，如 OpenFOAM）复制**单元场量值**；FEM（节点自由度，如 deal.II）复制**节点 DOF**；接收方 halo 单元**只读**。

**一次交换时序**：① 计算前互相发边界一层填 ghost → ② 各自计算（用 ghost）→ ③（FV）再交换通量/更新量保守恒 → ④ 下一迭代。①要成对（HPC-005），与②重叠（HPC-007）。

---

### Q49 通信子 / 拓扑 详细版

**通信子（Communicator）**：进程组 + 通信上下文；每次收发/集合都在某个通信子内，`tag` 匹配只在同一通信子生效。
- `MPI_COMM_WORLD`（全部）、`MPI_COMM_SELF`（自己）、`MPI_Comm_split`（分组）、`MPI_Comm_dup`（新 context）。
- 作用：**隔离**通信域，避免串消息、库与应用集合通信撞车；集合通信作用域=该通信子内全部进程。

```c
MPI_Comm field_comm;
MPI_Comm_split(MPI_COMM_WORLD, color, rank, &field_comm);  // 按物理场分组
```

**拓扑（Topology）**：给进程一个**逻辑排列**（非物理网络），让"找邻居"变简单。
- 笛卡尔：`MPI_Cart_create`（进程排 n 维网格）；`MPI_Cart_shift` 直接取某方向邻居 rank。
- 图：`MPI_Graph_create`（任意邻居关系）。
```c
int dims[2]={0,0}; MPI_Dims_create(nprocs,2,dims);
int periods[2]={1,1}; MPI_Comm cart;
MPI_Cart_create(MPI_COMM_WORLD,2,dims,periods,/*reorder=*/1,&cart);
int left,right; MPI_Cart_shift(cart,0,1,&left,&right);   // x 方向邻居
```
`reorder=1` 允许重排 rank 提升局部性；拓扑是逻辑覆盖层，不改硬件。

**与域分解**：规则块分解→笛卡尔拓扑 + `Cart_shift`；不规则分区→图拓扑；多物理场→`Comm_split` 隔离。

**常见坑（HPC-009 窄化）**：库占用 WORLD→串扰死锁；不同通信子做同一集合→挂死；多场共用 WORLD 不隔离；`reorder=0`；邻居方向错→halo 死锁。**注：未用 `comm_split`/cartesian 本身不是缺陷**，只有"多通信域混用未隔离"才是反模式（默认 INFO）。

---

### Q50 `#pragma omp` 并行举例（串行→多线程）

```c
#include <stdio.h>
#include <omp.h>
int main(){
    int N=8; double a[8],b[8];
    for(int i=0;i<N;i++) a[i]=i;
    #pragma omp parallel for schedule(static)
    for(int i=0;i<N;i++){ b[i]=a[i]*2; printf("thread %d -> i=%d\n",omp_get_thread_num(),i); }
    return 0;
}
```
编译运行：`gcc -fopenmp demo.c -o demo && OMP_NUM_THREADS=4 ./demo`

**8 次迭代如何分给 4 线程（static 连续切块）**：
```
共享内存中的 b[0..7]  ← 所有线程读写同一份，无复制
T0: i=0,1   T1: i=2,3   T2: i=4,5   T3: i=6,7
```

**`parallel for` = 两件事合体**：
```c
#pragma omp parallel          // ① 派生 N 线程
{ #pragma omp for             // ② 迭代分给这些线程
  for(...) ...; }
```

**代码块并行**（每线程各执行一遍）：
```c
#pragma omp parallel
{ printf("我是线程 %d / 共 %d\n", omp_get_thread_num(), omp_get_num_threads()); }
```

**为什么叫共享内存**：线程同进程、共享 `a[]/b[]/sum`；写同一变量会竞态 → 用 `reduction`：
```c
double sum=0;
#pragma omp parallel for reduction(+:sum)   // ✅
for(int i=0;i<N;i++) sum+=a[i];
// 注意：循环变量 i 默认私有；普通变量默认共享
```

**边界**：线程数由 `OMP_NUM_THREADS` 控；仅单节点；fork-join 有固定开销（循环太短不划算）；坑=数据竞争/假共享/并行域嵌套。

---

### Q51 假共享（False Sharing）详细版

**定义**：多线程写的是**不同变量**，但这些变量落在**同一条 cache line**（通常 64B），导致缓存行被反复作废/搬运——逻辑无共享、物理有共享。

**机制（缓存一致性协议按整条 line 工作）**：
```
┌──────── 同一 64B cache line ────────┐
│ sum[0] │ sum[1] │ sum[2] │ sum[3] │
└───▲────────▲────────▲────────▲─────┘
   T0       T1       T2       T3   （各写各的元素）
T0 写→T1/T2/T3 的 line 作废；T1 写→再作废 T0… 来回 ping-pong
```

**例子**：
```c
double partial[4];                 // 4×8=32B < 64B
#pragma omp parallel
{
    int t=omp_get_thread_num();
    for(int i=t;i<n;i+=4) partial[t]+=a[i];   // ❌ 各写各的，但同一 line
}
```

**真共享 vs 假共享**：
| | 真共享 | 假共享 |
|:--|:--|:--|
| 写的是 | 同一变量 | 不同变量 |
| 冲突 | 真实数据竞争（需 atomic/reduction）| 逻辑无冲突 |
| 代价 | 不可避免 | 本可避免（变量碰巧同行）|

**后果**：**只影响性能，不影响正确性**；静态看不出，需 perf/VTune/cache-miss 计数；可能慢 10 倍+。

**修法（让线程数据独占 cache line）**：
```c
struct alignas(64) Padded{ double v; };  Padded partial[4];      // 每个独占一行
double partial[4][8];                                            // 步长 8×8=64B
double local=0;
#pragma omp parallel for reduction(+:local)                      // 最常用
for(int i=0;i<n;i++) local+=a[i];
```

**与规则**：HPC-011 抓的是**正确性**（缺 private/reduction 的竞态）；假共享是**性能**问题、静态难判（运行时计数）→ 不属 HPC-001~012 硬规则，接近 HPC-013/014（运行时/KNOWN_HOLES），当性能优化项处理。

---

### Q52 并行域嵌套（HPC-012）详细版

**定义**：一个并行域里再开并行（`omp parallel` 套 `omp parallel`），或多线程区直接调 MPI/再开线程，导致行为异常、线程超订或未定义行为。

**三类典型**：
| 形态 | 例子 | 问题 |
|:--|:--|:--|
| ① 并行域套并行域 | `omp parallel` 里再 `omp parallel` | 嵌套默认关闭→内层退化单线程；开启→超订 |
| ② 多线程区调 MPI | `omp parallel` 内 `MPI_Allreduce` | 未 `THREAD_MULTIPLE`→未定义（与 HPC-010 重叠）|
| ③ 并行区内再 fork | 并行区里 `std::thread`/`pthread_create` | 线程爆炸、调度失控 |

**为什么是问题**：嵌套默认关闭（`OMP_NESTED=false`）→内层单线程"假并行"；开启嵌套→线程超订（8×8=64 抢 8 核）；MPI-in-omp 无线程守卫→未定义。

**错误/正确**：
```c
// ❌ 嵌套
#pragma omp parallel
{ #pragma omp parallel
  for(int i=0;i<n;i++) work(i); }

// ❌ 多线程区调 MPI
#pragma omp parallel
{ MPI_Allreduce(&local,&global,1,MPI_DOUBLE,MPI_SUM,comm); }

// ✅ 扁平化
#pragma omp parallel for
for(int i=0;i<n;i++) work(i);

// ✅ MPI+OpenMP：只有主线程碰 MPI
#pragma omp parallel
{
    #pragma omp for
    for(int i=0;i<n;i++) local+=work(i);
    #pragma omp master
    { MPI_Allreduce(&local,&global,1,MPI_DOUBLE,MPI_SUM,comm); }
}

// ✅ 用任务并行代替嵌套
#pragma omp parallel
#pragma omp single
{ for(auto&t:tasks){ #pragma omp task
                      process(t);} }
```

**若需多层**：`omp_set_max_active_levels(2)` 并评估超订；更好的是"外层 MPI（节点间）+ 内层 OpenMP（节点内）"，并保证 `外层线程×内核线程 ≤ 物理核`。

**规则属性**：HPC-012 severity **HIGH** / output_level **WARNING**；静态启发式（嵌套/并行区 MPI/并行区 pthread）；置信度中；与 HPC-010 常同时触发（报告去重）。

---

### Q53 并行区调非线程安全函数（rand、非 MULTIPLE 的 MPI → HPC-010）详细版

**线程安全** = 多线程并发调用同一函数不会因共享内部状态互相破坏。很多 C 库函数用了内部静态/全局状态（`rand` 种子、`strtok` 游标、`localtime` 返回缓冲），**不线程安全**。

**例子 A：`rand()`**：
```c
#pragma omp parallel for
for(int i=0;i<n;i++) x[i]=rand()%100;      // ❌ 共享种子→竞态
```
修：`rand_r(&seed)`（每线程独立 seed）或每线程 `std::mt19937`：
```c
#pragma omp parallel
{
    unsigned int seed=1234u+omp_get_thread_num();
    #pragma omp for
    for(int i=0;i<n;i++) x[i]=rand_r(&seed)%100;   // ✅
}
```

**例子 B：非 `THREAD_MULTIPLE` 的 MPI（HPC-010 主体）**：
| 级别 | 允许调用 |
|:--|:--|
| SINGLE | 单线程 |
| **FUNNELED** | **只有主线程**（最常用，SU2 默认）|
| SERIALIZED | 多线程但需串行化 |
| MULTIPLE | 任意线程 |

```c
// ❌ FUNNELED 下多线程调 MPI
#pragma omp parallel
{ MPI_Allreduce(&local,&global,1,MPI_DOUBLE,MPI_SUM,comm); }

// ✅ 修法1：只有主线程调
#pragma omp parallel
{
    #pragma omp for
    for(...) local+=work(i);
    #pragma omp master
    { MPI_Allreduce(&local,&global,1,MPI_DOUBLE,MPI_SUM,comm); }
}

// ✅ 修法2：显式申请 MULTIPLE
int provided; MPI_Init_thread(&argc,&argv,MPI_THREAD_MULTIPLE,&provided);
if(provided<MPI_THREAD_MULTIPLE){ /* 降级/报错 */ }
```

**其他常见非线程安全函数**：`strtok`→`strtok_r`、`localtime/gmtime`→`*_r`、`asctime/ctime`→`*_r`、`gethostbyname`→`getaddrinfo`、库内全局/静态变量→加锁/`thread_local`。

**后果**：非确定性、静默错、崩溃/挂死。

**检测与映射**：多线程区调非 MULTIPLE 的 MPI = **HPC-010 本体**；`rand/strtok/localtime` 等属"同类非线程安全函数"，作为 **HPC-010 扩展检测点**（HPC-010 名字是"线程安全 MPI"，报告注明区别）。

---

### Q54 浮点归约顺序不确定（CPU/GPU 分歧来源，HPC-001）详细版

**根因**：浮点加法**不满足结合律**，`(a+b)+c ≠ a+(b+c)`（舍入误差）→ "归约按什么顺序合并"改变末位结果；CPU/GPU 结合树不同→同一算法算出不同数。

**数值例子**：
```c
double a[3]={1e16, 1.0, -1e16};
// 顺序①： ((1e16+1.0)+(-1e16)) = 1e16 + (-1e16) = 0     （1.0 被舍）
// 顺序②： (1e16+(-1e16))+1.0   = 0 + 1.0       = 1
```

**为什么并行改变顺序**：线程数、`schedule`、归约树形状、运行次数都会改变结合顺序；CPU（8 线程树）vs GPU（warp shuffle + block shared + grid 归约）完全不同；再叠加 **FMA**（单次 vs 两次舍入）与 `--use_fast_math`（允许重排）→ 差异放大。

**误差量级**：相对误差 ~ `n·ε`（double ε≈2.2e-16，float≈1.2e-7）；相消时放大。

**与 HPC-001**：CPU 实现与 GPU kernel"逻辑一样"但归约/FMA/精度不同→结果不逐位一致；正确用法是**检测双实现是否存在及是否做容差比对**，而非要求逐位相等。

**应对**：
| 手段 | 说明 |
|:--|:--|
| 容差比较 | `|a-b| ≤ tol·max(1,|a|,|b|)`，不要 `==` |
| 提高精度 | double/long double |
| 补偿求和 | Kahan/Neumaier |
| 确定性归约 | 固定线程数/固定树形（可复现归约）|
| 关重排 | `-ffp-contract=off`、禁 `-ffast-math` |
| 参考实现 | 串行/高精度版本做基准，容差比对 |

```c
// Kahan 补偿求和
double s=0,c=0;
for(int i=0;i<n;i++){ double y=a[i]-c; double t=s+y; c=(t-s)-y; s=t; }
```

---

### Q55 TBB / Taskflow 详细版

**定位**：都是 C++ "任务/线程池"并行库（库+任务/图），与 OpenMP（`#pragma`）目标相同、风格不同。deal.II 节点内主要用这类 → "MPI + TBB/Taskflow 线程"。

**TBB（Intel Threading Building Blocks / oneTBB）**：线程池 + 并行算法 + work-stealing。
```cpp
#include <tbb/parallel_for.h>
#include <tbb/blocked_range.h>
tbb::parallel_for(tbb::blocked_range<int>(0,n),
  [&](const tbb::blocked_range<int>& r){
      for(int i=r.begin();i!=r.end();++i) b[i]=a[i]*2.0; });

double sum=tbb::parallel_reduce(tbb::blocked_range<int>(0,n),0.0,
  [&](const tbb::blocked_range<int>& r,double init){
      for(int i=r.begin();i!=r.end();++i) init+=a[i]; return init; },
  std::plus<double>());
```
关键：`blocked_range`（自动切块）、work-stealing、`task_group`/`flow_graph`、`global_control`（控线程数）。

**Taskflow**：header-only 的**任务图（DAG）**并行库。
```cpp
#include <taskflow/taskflow.hpp>
tf::Taskflow tf; tf::Executor ex;
auto A=tf.emplace([]{/*读*/}), B=tf.emplace([]{/*算1*/}),
     C=tf.emplace([]{/*算2*/}), D=tf.emplace([]{/*汇总*/});
A.precede(B,C); B.precede(D); C.precede(D);
ex.run(tf).wait();
```
特点：显式依赖（precede/succeed）、条件任务、subflow、`for_each`/`reduce`、GPU 任务（cudaFlow）。

**与 OpenMP 对比**：
| | OpenMP | TBB | Taskflow |
|:--|:--|:--|:--|
| 形式 | 编译器 pragma | C++ 库 | C++ 库(header-only) |
| 模型 | 循环并行/并行域 | 并行算法+任务 | 任务依赖图 DAG |
| 擅长 | 规整 for | 分治/递归/容器 | 复杂依赖/流水线/异构 |
| 线程管理 | 编译器+运行时 | 库内线程池(work-stealing) | 库内执行器(work-stealing) |

**为什么 deal.II 用 TBB**：自适应网格/递归/不规则算法，任务/分治比"规整 for"更契合；节点间 MPI + 节点内 TBB/Taskflow（局部 OpenMP）。

**与 HPC 规则映射**（措辞偏 OpenMP，需同义映射）：
| 风险 | TBB/Taskflow 说法 | 规则 |
|:--|:--|:--|
| 数据竞争 | lambda 按引用捕获共享变量并发写 | HPC-011 |
| 非线程安全调用 | 任务里调 `rand`/非 MULTIPLE 的 MPI | HPC-010 |
| 嵌套/超订 | 任务里再起线程/`parallel_for` 嵌套、与 MPI/OpenMP 混用 | HPC-012 |
| 假共享 | 任务写相邻数组元素 | 性能项(非硬规则) |

**常见坑**：lambda 按引用捕获竞态；任务粒度过细（grain size）；TBB+OpenMP+MPI 混用超订（`global_control` 限）；异常/取消传播；任务图下归约顺序仍可能变（HPC-001）。

---

---

## L. HPC 补充详细版（Q56–Q57）

### Q56 数据常驻（多次 kernel 复用，避免反复搬运）详细版

**问题**：每遇到一个 `#pragma omp target ... map(...)`，都可能把数据**重新**拷到设备、再拷回。连续跑多个 kernel 就是反复 H2D/D2H 搬运——即 **HPC-004（冗余搬运）** 的典型。

**做法**：用 `#pragma omp target data map(...) { ... }` 建立**设备数据环境**（"设备端缓存/会话"）。块内所有 target 区域**复用同一份设备副本**：进入块拷入、退出块拷回，中间不重复搬运。

**对比**：
```c
// ❌ 无数据常驻：每个 kernel 各搬一次
#pragma omp target teams distribute parallel for map(to:a[0:n]) map(from:b[0:n])
for (int i=0;i<n;i++) b[i]=a[i]*2;
#pragma omp target teams distribute parallel for map(to:a[0:n]) map(tofrom:b[0:n])
for (int i=0;i<n;i++) b[i]+=a[i];
// a 拷两次；b 拷回两次

// ✅ 数据常驻：拷一次、用多次
#pragma omp target data map(to:a[0:n]) map(tofrom:b[0:n])
{
    #pragma omp target teams distribute parallel for
    for (int i=0;i<n;i++) b[i]=a[i]*2;
    #pragma omp target teams distribute parallel for
    for (int i=0;i<n;i++) b[i]+=a[i];
}
// a 只拷入一次；b 进入拷入、退出拷回各一次
```

**map 方向（在 target data 块里）**：
| 子句 | 进入块 | 退出块 |
|:--|:--|:--|
| `map(to:x)` | 拷到设备 | 不拷回 |
| `map(from:y)` | 不拷入 | 拷回主机 |
| `map(tofrom:z)` | 拷入 | 拷回 |
| `map(alloc:buf)` | 仅设备分配 | 不拷 |

**非词法作用域：`target enter/exit data`**（常驻期跨函数/循环）：
```c
#pragma omp target enter data map(to:a[0:n])       // 提前拷入
for (int step=0; step<steps; step++) {
    #pragma omp target teams distribute parallel for
    for (int i=0;i<n;i++) a[i]+=f(a[i]);           // 每步复用设备副本
}
#pragma omp target exit data map(from:a[0:n])      // 结束时拷回
```
> 常驻期间主机改了数据 → 用 `#pragma omp target update to/from(...)` 同步一次。

**类比**：把数据"搬进 GPU 宿舍住一段时间"——进宿舍搬一次（enter），期间多次使用不再来回跑（kernel 复用），退宿搬回（exit），而不是"每干一件事就搬进搬出"。

**注意点**：
| 坑 | 说明 |
|:--|:--|
| 设备内存压力 | 常驻占显存，别把整个大数组无脑常驻 |
| 生命周期 | `enter` 必须配对 `exit`，否则设备内存泄漏 |
| 一致性 | 常驻期间主机改数据 → `target update to/from` |
| 多设备 | 需显式管理关联（`omp_target_associate_ptr` 等）|

**与规则**：HPC-004（冗余搬运）的正解；检测应把"循环/多次 kernel 内反复 `map`"判为冗余，"`target data` 常驻"为良好实践；HPC-002（设备守卫）仍需先确认有设备；HPC-003（launch）是另一件事。

---

### Q57 执行配置（HPC-003）详细版：num_teams ≈ gridDim、thread_limit ≈ blockDim

**OpenMP 执行层级 → CUDA 映射**：
```
target → teams → distribute → parallel for → simd
```
| OpenMP | CUDA | 含义 |
|:--|:--|:--|
| `num_teams(T)` | **gridDim** | block（线程组）数 |
| `thread_limit(B)` | **blockDim** | 每 block 线程数 |
| 总线程 | `gridDim × blockDim` | T × B |

**不写 vs 写死**：
- 不写：编译器/运行时按规模与设备限制**自动选**（OpenMP 5.x `teams loop` 更自适应）；
- 写死：`num_teams(1024) thread_limit(256)` 这类常量 → ①不随 N 变（N 小则大量空转，N 大则不够）；②不随设备变（不同 GPU 的 SM 数/每 block 上限不同）；③丧失性能可移植。

**正确做法：按数据规模推导**
```c
int B = 256;                                  // 每 block 线程（≤ 设备上限，可调）
int W = 4;                                    // 每线程处理元素数（控制粒度）
int T = (N + B*W - 1) / (B*W);                // ceil(N/(B*W)) 个 block
#pragma omp target teams num_teams(T) thread_limit(B) distribute parallel for
for (int i=0;i<N;i++) b[i]=a[i]*2.0;
```
- `T` 由 N/B/W 推导，不是常量；`B` 按设备能力（`omp_get_thread_limit()`/设备属性）设定；
- 更省心：`#pragma omp target teams loop` 让编译器自动决定；
- 运行时观察：`omp_get_num_teams()` / `omp_get_team_num()` / `omp_get_num_threads()`。

**规则属性**：HPC-003 severity **LOW** / output_level **INFO**（性能/可移植性启发式，置信度中）；检测 `num_teams(<字面量>)`/`thread_limit(<字面量>)`、CUDA `<<<1024,256>>>` 等魔法数且未由 N/设备推导。

**避免误判**：小规模/基准测试/教学示例写常量未必是缺陷 → 设豁免/降级（如 `@benchmark_ok`，或仅在"规模明显大于常量"时提示）；真正要抓的是业务热路径里"与 N/设备无关的写死配置"。

**与相邻规则**：HPC-003 管"启动多少线程/块"；HPC-004 管"数据搬多少次"；HPC-001 管"数值一致性"。三者不同。

**一句话**：`num_teams`≈gridDim、`thread_limit`≈blockDim；按 `N/B/W` 推导并查设备上限，写死常量即"硬编码 launch"（HPC-003 低置信 INFO）。

---

---

## M. HPC 进阶问答详细版（Q58–Q72）

### Q58 Amdahl / Gustafson 详细版

**Amdahl（强扩展，固定问题）**：
```
S(n) = 1 / ( (1-p) + p/n )      极限 S_max = 1/(1-p)
```
- p=0.9 → 上限 10×；p=0.95 → 20×；p=0.99 → 100×。串行段是天花板。

**Gustafson（弱扩展，问题随核数放大）**：
```
S(n) = n - α·(n-1)              （α = 并行运行中的串行占比）
```
- α=0.1、n=100 → S≈90.1（近线性）。

| | Amdahl | Gustafson |
|:--|:--|:--|
| 问题规模 | 固定 | 随核数放大 |
| 扩展 | 强扩展 | 弱扩展 |
| 结论 | 有上限、偏悲观 | 近线性、偏乐观 |

**局限**：忽略通信、负载不均、内存带宽、I/O；实测更差。**HPC-013（扩展曲线）为运行时 KNOWN_HOLES。**

### Q59 编译器 IR 详细版

**IR = 源码与机器码之间的中间表示**，前后端解耦（M+N 而非 M×N），承载优化。

**层级**：AST/HIR → **SSA 中层（LLVM IR / GCC GIMPLE）** → 低层（MachineIR/RTL）→ 目标（PTX/AMDGCN/SPIR-V）。

| IR | 归属 | 形态 |
|:--|:--|:--|
| LLVM IR | LLVM | 文本 `.ll` / 二进制 `.bc`（SSA）|
| GIMPLE/RTL | GCC | 内部 |
| SPIR-V | Khronos | 二进制（便携）|
| PTX | NVIDIA | 文本（虚拟 ISA）|
| MLIR | LLVM 生态 | 多级 dialect |

**关键概念**：SSA、基本块、CFG、Pass、Lowering。
**在 GPU 链中**：源码 → LLVM IR → NVPTX/AMDGPU/SPIR-V → PTX/HSACO/本机码。
**与 HPC-001**：不同 IR/后端优化（FMA/重排/归约顺序）→ CPU/GPU 数值分歧。
**区分**：IR（编译期中间语言）/ 字节码（JVM/IL）/ 虚拟 ISA（PTX）/ 机器码（SASS）。

### Q60 MPI 4.1 的"线程级"详细版（MPI 与线程的关系）

MPI 的并行单位是**进程**（rank），不是线程。标准里的"线程级"是 **MPI 与线程的共存契约**（自 MPI-2.0；4.1 为现行版本）：

| 级别 | 含义 |
|:--|:--|
| `MPI_THREAD_SINGLE` | 单线程调 MPI |
| `MPI_THREAD_FUNNELED` | 只有主线程可调（最常用）|
| `MPI_THREAD_SERIALIZED` | 多线程但需串行化 |
| `MPI_THREAD_MULTIPLE` | 任意线程可随时调 |

```c
int provided;
MPI_Init_thread(&argc,&argv, MPI_THREAD_MULTIPLE, &provided);
```
标准声明的"通信语义/线程级/拓扑"= 它规范的内容，不是"MPI 做线程并行"。纯 MPI 不涉线程；MPI×OpenMP 混合才需它 → **HPC-010**。

### Q61 ASME V&V 20（方法学，非并行专属）详细版

**全称**：*Standard for Verification and Validation in CFD and Heat Transfer*（V&V 20-2009）。

| 块 | 内容 |
|:--|:--|
| Verification | 代码验证（MMS/观察阶）、解的验证（Richardson/GCI）|
| Validation | 与实验（EFD）比对：E、U_V、验证域 |

**为什么"方法学、非并行专属"**：它规定"如何验证数值结果可信"，**不定义并行指标**（扩展/halo/线程安全）。设计依据第一版曾误写"对并行验证提要求"，**P1-2 已修正**为"V&V 方法学；并行验证另循扩展基准 + code-to-code + MPI 工具"。

### Q62 Validation：E / U_V / 验证域 详细版

- **S**（仿真）vs **D**（实验 EFD）；**比较误差 E = S − D**。
- 不确定度：**U_D**（实验）、**U_SN**（仿真数值）、**U_input**（输入）；
  ```
  U_V = √( U_SN² + U_input² + U_D² )
  ```
- **判定**：`|E| ≤ U_V` → 一致（通过）；`|E| > U_V` → 模型可疑。
- **算例**：S=0.32, D=0.30 → E=0.02；U_SN=0.005, U_D=0.01, U_input=0.003 → U_V≈0.0116 → 0.02>0.0116 不通过。
- **验证域**：结论成立的参数范围（如 Re=1e5~1e6、Ma=0.1~0.3）；域外为未验证外推。
- **与并行**：并行不应改变 E/U_V 结论；HPC-001 是 code-to-code（Verification），非对实验的 Validation。

### Q63 Solution Verification（Richardson / GCI）详细版

在代码已验证正确的前提下，估计**本次仿真**的离散/数值不确定度。

- **三类误差**：离散（网格/时间步）、迭代（未收敛）、舍入。
- **网格收敛**：系统加密，加密比 `r`（结构 `h_coarse/h_fine`；非结构 `(N_fine/N_coarse)^(1/d)`）。
- **观察阶**：`p = ln|(f₃−f₂)/(f₂−f₁)| / ln(r)`
- **外推**：`f_exact ≈ f₁ + (f₁−f₂)/(rᵖ−1)`
- **GCI**：`GCI = Fs · |(f₂−f₁)/f₁| / (rᵖ−1) ×100%`（三网格 Fs=1.25；两网格 3.0）
- **时间步**：同理对 Δt。
- **坑**：需单调渐近、p 接近理论阶、迭代先收敛；振荡收敛不可硬套。
- **与 HPC**：并行不应改变 f 与 GCI；异常变大疑 halo/归约/负载问题。

### Q64 U_SN 是否为 Validation 作准备 详细版

**是**——U_SN 是 U_V 的组成项：`U_V = √(U_SN² + U_input² + U_D²)`。顺序：**Code Verification → Solution Verification（得 U_SN）→ Validation**。

**陷阱（U_SN 太大会掩盖模型误差）**：

| 情形 | U_SN | U_D | U_V | 结论 |
|:--|:--:|:--:|:--:|:--|
| 细网格 | 0.005 | 0.010 | 0.0112 | \|E\|=0.02>U_V → 不通过（模型可疑）|
| 粗网格 | 0.025 | 0.010 | 0.0269 | \|E\|=0.02≤U_V → "通过"（无意义）|

U_SN 也独立用于：判断网格是否够细、报告仿真可信度、预测不确定度、并行前后稳定性。

### Q65 MUST / TSan / compute-sanitizer / TAU 详细版

| 工具 | 关注 | 对应缺陷 |
|:--|:--|:--|
| **MUST** | MPI 运行时正确性（死锁/配对/类型/集合）| HPC-005/006/009/010 |
| **TSan** | 数据竞争（多线程）| HPC-011/010 |
| **compute-sanitizer** | CUDA 内存/竞态/同步 | HPC-001~004 |
| **TAU** | 性能剖析/扩展/负载 | HPC-006/007/008/013 |

- **静态 vs 动态**：静态找模式、可门禁；这些工具跑起来确认，开销大、放夜间/专项。
- **与 KNOWN_HOLES**：HPC-013/014 只能靠 TAU。

### Q66 强/弱扩展曲线 详细版

- **强扩展**（固定问题）：`S=T₁/Tₙ`、`E=S/n`；理想线性，受 Amdahl 封顶。
- **弱扩展**（每核固定）：`E_w=T₁/Tₙ`；理想时间恒定，受 Gustafson 支撑。

**算例（强）** T₁=100：n=4→T=28,S=3.6,E=89%；n=16→T=9,S=11.1,E=69%；n=64→T=4,S=25,E=39%。

```
强扩展：S vs n（ideal 线性 / actual 亚线性）
弱扩展：T vs n（ideal 平 / actual 缓慢上升）
```
**偏离原因**：串行段、通信/halo、负载不均、带宽/NUMA（小问题可能超线性）。
**与 HPC**：HPC-013（运行时）；曲线形状指向 HPC-005/006/008。

### Q67 "跨函数/RAII/异步流水 → 记候选" 详细版

**情形**（配对其实存在，但静态看不见）：
```c
// 跨函数
void start(){ MPI_Isend(..., &req); }  void finish(){ MPI_Wait(&req,...); }
// RAII
struct Halo { Halo(){ MPI_Isend(...,&req);} ~Halo(){ MPI_Wait(&req,...);} };
// 异步流水
MPI_Isend(...,&req); compute_interior(); ...; MPI_Wait(&req,...);
```

| 场景 | 处置 |
|:--|:--|
| **同作用域** `Isend` 且确无 `Wait` | 判 WARNING（中低置信）|
| **跨函数/RAII/异步** | **记候选**（不直接 WARNING），交 MUST/人工/LLM 确认 |

**候选 ≠ 已确认**：不封顶、不 BLOCK（§四"已确认"定义）。

### Q68 是否用 LLM 进一步语义分析 详细版

**适合**（候选→精判），但限定：
- **输入**：候选附近（函数体/调用链/类构造析构/循环）。
- **输出**：`{verdict: reject|confirm|uncertain, evidence:[file:line], reason}`。
- **必守**：仅候选；证据 `file:line`、无证据不采信；温度 0 + 固定版本 + 缓存；**confirm 不自动 BLOCK**（候选级证据）；不改变确定性分数；离线运行。

**分工**：静态召回 → LLM 精判（减误报）→ MUST 运行时（金标准）/人工（ERROR/HIGH 最终确认）。

### Q69 HPC-008 候选与 LLM 确认 详细版

HPC-008 三分支：
1. 有加权配置 → 通过；
2. 无加权且**无非均匀迹象** → 合理等分分区；
3. 无加权且**有非均匀迹象**（AMR/多材料/非均匀场/无 load balance）→ **候选 WARNING**。

**为什么候选**："非均匀"≠"一定失衡"，静态看不到各 rank 耗时。
**LLM 能做**：判"非均匀风险是否真实"（须证据）；**不能做**：测实际失衡。
**确认链**：LLM 判风险 → **TAU 实测**（金标准）→ 人工裁定。

### Q70 "均分"是否应为"均匀" 详细版

| 词 | 词性/含义 | 用法 |
|:--|:--|:--|
| 均匀/非均匀 | 形容词，**问题/工作量属性** | 非均匀算例、非均匀迹象 |
| 均分/等分分区 | 动作，**平均划分分区** | 等分划分子域、等分分区合理 |

**结论：不应改成"均匀"**。指南已加术语约定，正文统一用"**等分分区**"指动作，避免混淆。

### Q71 反滥用守卫 详细版（举例）

**目的**：防"大量豁免把评估掏空、分数虚高"。

**机制**：豁免占比 **>30%** 告警；通道分离（`@hpc_benchmark_ok` 仅 HPC-003、`@hpc_gpu_only` 仅 HPC-002、`@hpc_deferred` 仅降级）；reason 必填；降级不改 severity（HIGH 封顶不解除）。

**例子**：
- 200 文件，61 个 `@hpc_deferred` = **30.5%>30%** → abuse_warning。
- 全标 `@hpc_deferred` 静音 HPC-005 → 占比超限告警；且 severity 仍 HIGH → 封顶不解除。
- 业务热路径标 `@hpc_benchmark_ok` 屏蔽其他规则 → 越界且无效（仅作用 HPC-003）。
- 59/200=29.5% → 不告警，但可"压线"规避 → 需人工复核（局限）。

**审计**：`waiver_audit`（各通道 count/ratio/files、invalid_waivers、abuse_limit、abuse_warning）。

---

### Q72 U_SN / U_input / U_D 如何计算 详细版

> Q62 给了 `E/U_V` 公式与算例；Q63 给了 `U_SN` 的 GCI；本问把**三项不确定度各自怎么算**讲透。

| 量 | 含义 | 主要方法 |
|:--|:--|:--|
| **U_D** | 实验（EFD）不确定度 | GUM：A/B 类 → 合成 \(u_c\) → 扩展 \(U=k u_c\) |
| **U_SN** | 仿真数值不确定度 | Solution Verification：网格 GCI + 迭代 + 时间步，RSS |
| **U_input** | 输入不确定度 | 灵敏度传播（GUM）或蒙特卡洛 |
| **U_V** | 验证不确定度 | \(U_V=\sqrt{U_{SN}^2+U_{input}^2+U_D^2}\)（**同覆盖率**）|

> 约定：ASME V&V 20 常把 `U_input` 并入 `U_SN`；本文按 Q62 的公式单列。**不要重复计入**。

---

#### 一、U_D（实验不确定度）

1. **列源**：传感器校准、分辨率、重复性、安装/探针位置、采集/滤波、物性、阻塞/壁面修正、来流品质。
2. **A 类（随机）**：`u_A = s/√n`，`s = √(Σ(x_i−x̄)²/(n−1))`。
3. **B 类（系统）**：矩形 `a/√3`；三角 `a/√6`；正态 `a/k`。
4. **合成**：`u_c = √(Σu_i² + 2Σρ_ij u_i u_j)`；独立时退化为 RSS。
5. **扩展**：`U_D = k·u_c`；V&V 对比统一 **95%（k=2）**。

| 源 | 标准不确定度 |
|---|---:|
| 校准 | 0.003 |
| 重复性 | 0.003 |
| 数据采集 | 0.002 |
| 物性/修正 | 0.001 |
| 合成 \(u_c\) | \(√(9+9+4+1)×10^{-3}=0.0048\) |
| \(U_D=2u_c\) | **0.0096 ≈ 0.01** |

---

#### 二、U_SN（仿真数值不确定度）

`U_SN = √(U_grid² + U_iter² + U_time² + U_roundoff² + …)`

**1) 网格 GCI（Roache）**——三套网格、`r=h_coarse/h_fine ≥ 1.3`、单调收敛：

```
p      = ln((f3−f2)/(f2−f1)) / ln(r)
f_exact≈ f1 + (f1−f2)/(r^p−1)
GCI    = Fs · |(f1−f2)/f1| / (r^p−1)
U_grid = GCI × S
```

- `Fs=1.25`（三网格，约 95%）；`Fs=3`（两网格，保守）。
- 非单调收敛：用稳健 GCI/包络，不可硬套。

**2) 迭代**：`U_iter ≈ |S_loose − S_tight|/2`，或迭代误差估计；要求残差远小于 `U_grid`。

**3) 时间步**：非定常时对 `Δt` 做同样细化，得 `U_time`。

| 分量 | 值 |
|---|---:|
| \(U_grid\)（1.5%×0.32）| 0.0048 |
| \(U_iter\) | 0.0010 |
| \(U_time\) | 0.0005 |
| RSS | **0.0049 ≈ 0.005** |

---

#### 三、U_input（输入不确定度）

**方法 A：一阶 GUM（灵敏度传播）**

```
U_input² = Σ (∂S/∂x_i)² u(x_i)²
         + 2 Σ_{i<j} (∂S/∂x_i)(∂S/∂x_j) cov(x_i,x_j)
```

- 灵敏度 `∂S/∂x_i`：中心差分 `(S(x+Δ)−S(x−Δ))/(2Δ)`、伴随法、或 DOE 回归。
- 输入分布：均匀 `a/√3`；正态 `σ`。

**方法 B：蒙特卡洛 / 拉丁超立方**

- 采样 N 次 → 跑模型 → `u_S = √(Σ(S_k−S̄)²/(N−1))`；昂贵模型用 PCE 代理。

| 输入 | \(u(x_i)\) | 灵敏度 | 贡献 |
|---|---:|---:|---:|
| 入口速度 ±1% | 0.01V | 0.10 | 0.0010 |
| 来流温度 ±2K | 1.15K | 0.0015 | 0.0017 |
| 壁面粗糙度 | — | — | 0.0022 |
| RSS | | | **0.0030** |

---

#### 四、覆盖率必须统一

| 量 | 常见口径 | 统一到 95% |
|:--|:--|:--|
| \(U_D\) | \(k=2\) | 已是 95% |
| GCI | \(F_s=1.25\) | 约 95% |
| \(U_input\) | 标准不确定度 \(u\) | ×1.96（正态）或按分布换算 |

**混用 k=1 / k=2 会让 \(U_V\) 失真**；要么全 k=1，要么全 95%。

---

#### 五、用 Q62 算例走一遍

```
U_V = √(0.005² + 0.003² + 0.01²)
    = √(25+9+100)×10⁻³ = √134×10⁻³ ≈ 0.0116
|E| = |0.32−0.30| = 0.02 > 0.0116 → 不通过
```

- 方差占比：`U_D≈75%`、`U_SN≈19%`、`U_input≈7%`（主导是实验）。
- 若 `U_D` 降到 0.005：`U_V=√(25+9+25)×10⁻³=0.0077`，`0.02>0.0077` **仍不通过**。
- 结论：模型偏差不能靠放大 `U_D` 掩盖（Q64 的"粗网格通过"同理无意义）。

---

#### 六、验证域

- 记录 `U_D/U_SN/U_input` 成立的条件：`Re=1e5~1e6`、`Ma=0.1~0.3`、几何/边界范围。
- **域内**可引用；**域外**属外推，需重新做验证。
- `U_input` 随工况变化 → `U_V` 是**域相关**的，不能一个 `U_V` 套所有工况。

---

#### 七、与并行/HPC

- 并行**不应改变** `E/U_V` 结论；分区/线程/GPU 后端只应影响舍入与收敛路径。
- 但 `U_SN` 必须在**实际并行配置**下重算（分区/线程会改变迭代收敛与舍入）。
- **HPC-001 是 code-to-code（Verification）**：CPU/GPU 双实现一致 ≠ 对实验的 Validation。
- 若并行导致 `E` 或 `U_V` 显著变化 → 先查实现/收敛，而非模型。

---

#### 八、实操清单

1. 定义 QoI（S）与验证域；
2. EFD 侧做完整不确定度分析 → `U_D`（bias + precision）；
3. Solution Verification：网格/时间/迭代 → `U_SN`；
4. 输入不确定度传播 → `U_input`（灵敏度或 MC）；
5. **统一覆盖率**后合成 `U_V`；
6. 判定 `|E| ≤ U_V`，报告 E、U_V、各分量、验证域；
7. 不通过 → 查模型形式/边界/物性，**不要靠放大 U_V 通过**；
8. 并行配置变化 → 重算 `U_SN`，确认结论稳定。

---

#### 九、常见坑

| 坑 | 说明 |
|:--|:--|
| 重复计入 `U_input` | 已并入 `U_SN` 又单列 |
| 覆盖率混用 | k=1 与 k=2 直接 RSS |
| 非单调 GCI | 硬套公式得负 `p`/异常值 |
| 忽略相关性 | 输入相关时未加协方差项 |
| `U_D` 缺 bias | 只算重复性，漏系统误差 |
| 放大 `U_V` 通过 | 掩盖模型偏差（Q64）|
| Verification/Validation 混淆 | GCI/MMS/code-to-code 属 Verification |

---

## N. 指南完善记录（v0.4 → v0.7，工程动作）

| 版本 | 变更 |
|:--|:--|
| 0.4 | 按 GCS 指南结构重构：概述/置信度/子维（设计依据/评分表/置信度说明/行业实践/代码坏味道/算例）/综合分/分级/逐条规则详解/KNOWN_HOLES/可行性分级/实施建议/启用条件/豁免体系 |
| 0.5 | 增 §7.7 LLM 语义精判（候选→精判→MUST/人工；证据锚定/温度0/不自动BLOCK/离线）|
| 0.6 | 细化 HPC-008 非均匀信号 + 风险 vs 事实确认链（LLM 判风险→TAU 判事实→人工）|
| 0.7 | 统一术语：等分分区=动作 / 均匀-非均匀=属性；新增术语约定 |

---

---

## 附：相关文档索引

| 主题 | 文档 |
|:--|:--|
| H3 计划/评审 | `docs/zh/计划/H3全维化执行计划v1.1.md`、`H3专家评审报告.md`、`H3全维化执行计划v2.md` |
| WP-0 / G0 | `H3-WP0基线实测方案.md`、`H3基线实测报告.md`、`H3-G0运行时内核CI方案.md` |
| WP-1 / WP-2 | `H3-WP1归一化实施说明.md`、`H3-WP2权重敏感性分析.md`、`H3-WP2权重定案工作底稿.md` |
| WP-9 | `H3-WP9遗留缺陷修复.md` |
| WP-3 维度⑥ | `docs/zh/并行异构计算架构评估/`（设计依据 v0.3 + 两轮校对）|
| 阶段纪要 | `docs/zh/计划/H3阶段进展与决策记录.md` |
| 方法论速览 | `docs/zh/知识库/HPC评估方法论与知识速览.md` |

---

## 版本历史

| 版本 | 日期 | 变更 |
|:-----|:-----|:-----|
| 1.0 | 2026-10-21 | 首版：汇编今日全部 Q&A（A~I 分组，39 问）|
| 1.1 | 2026-10-21 | 追加 Q40（启发式 vs LLM 详细版）|
| 1.2 | 2026-10-21 | 追加 Q41–Q46（域分解/MPI/OpenMP/target/编译器后端/PTX·AMDGCN·SPIR-V 详细版）|
| 1.3 | 2026-10-21 | 追加 Q47–Q55（halo·halo一层·通信子拓扑·OpenMP举例·假共享·并行域嵌套·非线程安全函数·浮点归约·TBB/Taskflow 详细版）|
| 1.4 | 2026-10-21 | 追加 Q56–Q57（数据常驻 / 执行配置 HPC-003 详细版）|
| 1.5 | 2026-10-21 | 增加「关键词索引（速查）」 |
| 1.6 | 2026-10-21 | 追加 Q58–Q71（Amdahl/Gustafson、编译器IR、MPI线程级、V&V20、Validation、Solution Verification、U_SN、工具生态、扩展曲线、候选、LLM语义、HPC-008+LLM、均分vs均匀、反滥用守卫）+ 指南完善记录 |
| 1.7 | 2026-10-21 | 追加 Q72（U_SN / U_input / U_D 计算方法：GUM·GCI·灵敏度传播·覆盖率统一·验证域·并行关系）+ 关键词索引 |