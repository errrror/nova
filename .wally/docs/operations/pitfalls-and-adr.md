---
kind: operations
scope: pitfalls-and-adr
status: draft
origin: generated
source_paths: [nova/cmd/compute.py, nova/conductor/rpcapi.py, nova/conf/scheduler.py, nova/api/openstack/compute/routes.py, nova/cells/manager.py]
symbols: [block_db_access, indirection_api, build_instances, CellsManager, ComputeDriver]
upstream: [INDEX.md, overview/system-architecture.md]
downstream: []
---

# 关键架构决策（ADR）、修改高危雷区与存量死路径警示

本页汇总决定 Nova 代码结构的硬性设计权衡，以及 Agent 修改时极易误踩的隐式耦合雷区与存量未挂载历史代码，防止搜索到同名函数后改错地方导致修改在运行态不生效。

## 1. 核心架构决策与不可违背的工程约束（Key ADRs）

| 编号 | 决策主题 | 核心实现机制与源码锚点 | Agent 修改时必须遵守的硬约束 |
|---|---|---|---|
| `ADR-01` | compute 无 DB 访问，对象持久化经 conductor 反转 | `nova/cmd/compute.py:46 block_db_access` + `:47 indirection_api = ConductorAPI()` | 禁止在 `nova-compute` 进程内直接 `db.sqlalchemy.api.*`；对象 `save` 已由 indirection 回调 conductor |
| `ADR-02` | RPC 载荷版本协商与滚动升级兼容 | `nova/conductor/rpcapi.py:330-352` 多级 `can_send_version` | 任何 cast 新增字段必须新增版本分支，否则老版本节点解析失败 |
| `ADR-03` | 声明式路由表 + microversion 字段门禁 | `nova/api/openstack/compute/routes.py:406 ROUTE_LIST`、`:876 APIRouterV21`；`servers.py:460/473` | 新接口走 ROUTE_LIST 注册；字段按 microversion 注入，禁止无版本判断 |
| `ADR-04` | 驱动/调度器 stevedore 动态加载 | `setup.cfg:80-88` 的 host_manager/scheduler.driver 入口 | 新增实现须保持 driver 接口一致，静态图无法穷举动态实现 |
| `ADR-05` | 带版本领域对象 + 乐观锁状态迁移 | `nova/objects/base.py:84 NovaObject`；`nova/compute/manager.py:1936 save(expected_task_state=...)` | 改对象字段必须提 `VERSION` 并做 backport；状态迁移用 `expected_task_state` 防竞态 |

## 2. 修改高危雷区与隐式耦合表（Danger Zones & Hidden Couplings）

| 高危源码位置（`路径:行号`） | 涉及符号 | 隐蔽陷阱机制（为什么直接改会出 Bug） | 安全修改标准动作 |
|---|---|---|---|
| `nova/conductor/rpcapi.py:330-352` | `build_instances` | 载荷字段随目标版本降级（如 `requested_networks.as_tuples()`、BDM primitive 化），漏改版本分支会让滚动升级中的老 compute 崩溃 | 新增字段必须追加 `can_send_version` 分支并补兼容测试 |
| `nova/compute/manager.py:1922-1926` | `_build_and_run_instance` | 实例组策略校验必须在 `instance_claim` **之后**（注释明确 host 此时才确定），提前校验会因 host 未设而失败 | 保持 claim → validate 顺序 |
| `nova/api/openstack/compute/routes.py:891-908` | `APIRouterV21.__init__` | 每条路由都新建 controller 实例（源码注释提出未来优化方向），改 controller 构造参数会影响全部路由 | 改 `_create_controller` 需跑全量 API 路由测试 |
| `nova/conf/scheduler.py:26-38` | `host_manager` / `driver` | 选项含 `deprecated_name`/`deprecated_group`（`scheduler_*` 旧名），改名会破坏旧配置加载 | 保留 deprecated 别名 |
| `nova/objects/base.py:242` | `NovaObjectSerializer.serialize_entity` | 序列化影响所有跨进程对象，单点改动波及 conductor/compute/scheduler 全部 RPC | 改序列化须全量跑 conductor/compute 集成测试 |

## 3. 存量死路径与历史兼容保留代码警示（Legacy / Unmounted Code Traps）

> 极其重要：以下源码仍存在（`Grep` 可搜到），但当前主链路已不挂载或仅作历史兼容/废弃选项。防止改错地方导致修改不生效。

| 存量代码位置（`路径:行号`） | 符号 / 页签 / 配置名 | 当前真实状态 | 当前真正生效的主入口位置 |
|---|---|---|---|
| `nova/conf/scheduler.py:49-50` | `chance_scheduler` / `caching_scheduler` 文档 | 标记为 `[DEPRECATED]`，非默认驱动 | 默认 `filter_scheduler`（`setup.cfg:85`） |
| `nova/conf/scheduler.py:37-38` | `scheduler_driver`（旧名） | [DEPRECATED] 别名，映射到 `[scheduler] driver` | `nova/conf/scheduler.py:35 cfg.StrOpt("driver")` |
| `nova/cells/manager.py:48 CellsManager` | Cells v1 编排 | Cells v1 历史分层编排，新部署多用 cells v2 放置 | 调度/放置见 `nova/scheduler/`、`nova/api/openstack/placement/` |
| `nova/api/openstack/compute/routes.py:555-666` | `/os-networks*`、`/os-floating-ips*` 等 | Nova-network 旧网络 API 兼容前缀，新部署由 Neutron 承担 | `nova/network/neutronv2/api.py:231 API` |
| `setup.cfg:64-65` | `nova-rootwrap`/`nova-rootwrap-daemon` | 委托外部 `oslo_rootwrap.cmd`，本仓仅配置白名单 | `etc/nova/rootwrap.conf` |

开发纪律与风格约束见 `HACKING.rst` 与 `CONTRIBUTING.rst`；异常层级见 [错误码字典](../contracts/error-codes.md)。


## 4. 共变耦合与修改清单（Agent Co-Change Playbook）

- 改动任一第 1 节 ADR 涉及的机制（DB 隔离、RPC 版本、路由注册、驱动加载、对象版本）前，必须先在 [模块依赖矩阵](../architecture/module-dep-matrix.md) 评估爆炸半径并跑全量相关单测。
- 命中第 3 节存量死路径时，先确认当前生效主入口再动手，避免改到未挂载代码。
- 误踩隐式耦合的典型信号：修改后运行态完全不生效（多半改到了 deprecated 别名或历史函数），排障见 [Runbook](runbook-and-observability.md)。
