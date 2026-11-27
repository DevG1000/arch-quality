# 科学内核 A 类样本（H3 WP-8 E1）

> 版本：1.0
> 日期：2026-11-25
> 说明：A 类 = 可复现开源项目，固定 `fetch.ref`。

| 样本 | 仓库 | 固定 ref | 关键信号 | 预期 ACL 关注点 |
|:--|:--|:--|:--|:--|
| PETSc | https://gitlab.com/petsc/petsc.git | c8d5ad6b37827809d4a5f144342c9f99b804723e | `Petsc*`、`KSP*`、`SNES*`、`TS*`、`VecCreate`、`MatSetValues` | 直接访问、错误码 `CHKERRQ/PetscCall`、KSP/SNES wrapper 覆盖 |
| deal.II | https://github.com/dealii/dealii.git | cd748a2c7a170acf863620453572ae2a90040ef9 | `dealii::`、`Triangulation<`、`DoFHandler<`、`FEValues<` | 直接访问、异常 `AssertThrow/ExcMessage`、wrapper 覆盖 |
| VTK | https://gitlab.kitware.com/vtk/vtk.git | 1f261ff9006ad5886e40a103d7f6c97f7854fa59 | `vtk[A-Z]*`、`vtkSmartPointer`、`vtkPolyData`、`vtkUnstructuredGrid` | 直接访问、类型泄漏、wrapper 覆盖 |

## 规则映射

- ACL-001 直连内核：科学内核符号在 wrapper 目录外引用；
- ACL-002 wrapper 覆盖：KSP/SNES/TS、Triangulation/DoFHandler、vtkPolyData/vtkSmartPointer 等核心符号；
- ACL-003 版本守卫：`PETSC_VERSION*`、`DEAL_II_VERSION*`、`VTK_VERSION*`；
- ACL-004 类型泄漏：wrapper 公开头文件暴露科学内核类型；
- ACL-005 错误处理：PETSc `CHKERRQ/PetscCall`、deal.II `AssertThrow/ExcMessage`。

## 合成测试样本

| 项目 | 用途 |
|:--|:--|
| `tests/mutation/projects/sci_kernel_direct` | PETSc + VTK 无 wrapper，应触发 ACL-001/002 |
| `tests/mutation/projects/sci_kernel_wrapped` | PETSc + VTK wrapper，带版本守卫/错误检查，应高分 |

## 说明

- 科学内核信号仅在项目为“科学内核主导”时计入 ACL 计数，避免几何项目中的少量 VTK 引用改变既有基线；
- 当前 A 类样本为固定 ref 的可复现开源清单，实际评分需下载到本地后执行。
