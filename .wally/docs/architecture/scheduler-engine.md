---
kind: component
scope: scheduler-engine
status: draft
origin: generated
source_paths: [setup.cfg, nova/scheduler/manager.py, nova/scheduler/filter_scheduler.py, nova/scheduler/host_manager.py, nova/scheduler/rpcapi.py]
symbols: [SchedulerManager, select_destinations, FilterScheduler, _schedule, HostManager]
upstream: [conductor-engine.md]
downstream: [virt-and-data.md, business/wf-scheduling.md]
---

# `scheduler-engine`（核心调度引擎组件）

Scheduler 是 Nova 的选节点决策引擎：它不执行实例操作，只依据「过滤（filters）+ 权重（weights）」从候选宿主机中选出目标，RPC 入口由 `SchedulerManager` 暴露，算法核心是 `FilterScheduler`。驱动通过 stevedore 入口动态选择。

## 1. 引擎核心不变量（Hard Invariants）

1. **只读决策不变量**：调度只产出 `(host, node, limits)` 候选，不直接写实例或调 hypervisor；状态迁移在 compute 侧完成（`nova/compute/manager.py:1702`）。
2. **驱动可替换不变量**：调度器实现经 `setup.cfg:84-88` 的 `nova.scheduler.driver` 入口动态加载，`FilterScheduler`/`CachingScheduler`/`ChanceScheduler` 必须实现统一 driver 接口。

## 2. 核心类型层次与职责表

| 核心符号（类 / 函数） | 源码锚点（`路径:行号`） | 职责与生命周期 |
|---|---|---|
| `SchedulerManager` | `nova/scheduler/manager.py:64` | RPC 端点 + 周期任务壳，启动驱动 |
| `select_destinations` | `nova/scheduler/manager.py:105` | conductor 调用的 RPC 入口，返回目标列表 |
| `FilterScheduler` | `nova/scheduler/filter_scheduler.py` | 默认调度驱动，过滤+权重算法 |
| `_schedule` | `nova/scheduler/filter_scheduler.py:111` | 核心算法：过滤 → 权重 → 选 host |
| `HostManager` | `nova/scheduler/host_manager.py` | 宿主状态与 aggregates 管理，执行 `get_filtered_hosts`/`get_weighed_hosts` |

## 3. 核心处理管线与关键阈值（Pipeline & Thresholds）

```text
nova/scheduler/manager.py:105 select_destinations(ctxt, request_spec, filter_properties, ...)
  -> nova/scheduler/filter_scheduler.py:111 FilterScheduler._schedule(...)
     ├─ [Stage 1: 取候选] self.host_manager.get_all_host_states(...) -> HostState 列表
     ├─ [Stage 2: 过滤] get_filtered_hosts(host_states, ...) (:295) -> 通过所有 filter 的 host
     ├─ [Stage 3: 权重] get_weighed_hosts(filtered_hosts, ...) (:303) -> 按 weigher 排序
     └─ [Stage 4: 选择] 取 top N -> [(host, node, limits)]
```

| 关键机制 / 常量 | 代码值 / 实现 | 源码位置 | 业务/性能作用（修改影响） |
|---|---|---|---|
| 调度驱动集合 | `filter_scheduler` / `caching_scheduler` / `chance` / `fake` | `setup.cfg:84-88` | 改驱动实现须保持接口兼容 |
| 周期 host 发现 | `_discover_hosts_in_cells` | `nova/scheduler/manager.py:90` | 定期发现各 cell 宿主，影响候选集新鲜度 |
| 预留过期 | `_expire_reservations` | `nova/scheduler/manager.py:84` | 清理过期资源预留，防止容量虚占 |

## 4. 共变耦合与扩展清单（Agent Co-Change Playbook）

- **新增 filter/weigher**：在 `nova/scheduler/filters/` 或 `weights/` 新增类 → 在 driver 配置中启用 → 更新 [`business/wf-scheduling.md`](../business/wf-scheduling.md) → 跑 `nova/tests/unit/scheduler/` 用例。
- **改 `_schedule` 选择逻辑**：必须同步 `nova/tests/unit/scheduler/test_filter_scheduler.py` 的候选断言与 `HostManager` 状态字段。
- **RPC 载荷变更**：`select_destinations` 参数变更须与 `nova/scheduler/rpcapi.py` 的 call 端版本一致。

调度流程的精确条件与状态见 [调度流程专页](../business/wf-scheduling.md)；宿主资源账本来源见 [`virt-and-data.md`](virt-and-data.md)。
