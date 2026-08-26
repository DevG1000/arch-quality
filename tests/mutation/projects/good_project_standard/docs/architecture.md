# Architecture Document

## 目录结构

- `src/service.py` — 业务服务层
- `src/repository.py` — 数据访问层
- `src/util.c` — 通用工具函数
- `tests/` — 单元测试

## 模块职责

- Service：业务逻辑编排，依赖 Repository 抽象
- Repository：数据持久化，实现数据访问接口
- Util：无状态工具函数

## 数据流

```
Controller → Service → Repository → Database
```

## 依赖关系

- Service 依赖 Repository（通过构造注入）
- Util 无外部依赖

## 设计决策

- 采用分层架构，Service/Repository 分离
- 构造注入实现依赖倒置（DIP）