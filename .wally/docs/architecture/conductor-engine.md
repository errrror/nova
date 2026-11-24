---
kind: component
scope: conductor-engine
status: draft
origin: generated
source_paths: [setup.cfg, nova/conductor/manager.py, nova/conductor/rpcapi.py, nova/compute/api.py]
symbols: [ConductorManager, ComputeTaskManager, build_instances, schedule_and_build_instances, object_action]
upstream: [api-service.md]
downstream: [scheduler-engine.md, compute-worker.md, virt-and-data.md]
---

# `conductor-engine`（核心编排引擎 / DB 代理组件）

Conductor 是 Nova 的无状态编排中枢：它替无 DB 权限的 `nova-compute` 代理对象持久化，并把建机/迁移/重建等长流程拆成跨服务 RPC 编排。核心职责由 `ConductorManager`（对象动作分发）与 `ComputeTaskManager`（计算任务编排）两类承担。

## 1. 引擎核心不变量（Hard Invariants）

1. **DB 访问隔离不变量**：`nova-compute` 启动即 `block_db_access`（`nova/cmd/compute.py:46`），所有对象持久化经 `indirection_api = ConductorAPI()`（`nova/cmd/compute.py:47`）回调 conductor。
2. **对象动作白名单不变量**：对象跨进程调用只允许经 `object_action`/`object_class_action_versions` 分发，锚点 `nova/conductor/manager.py:152` / `nova/conductor/manager.py:127`。
3. **任务失败清理不变量**：建机编排异常时必须 `_cleanup_build_artifacts`（`nova/conductor/manager.py:1072`）并 bury 到 cell0，不留悬挂 reservation。

## 2. 核心类型层次与职责表

| 核心符号（类 / 函数） | 源码锚点（`路径:行号`） | 持有的关键状态 | 职责与生命周期 |
|---|---|---|---|
| `ConductorManager` | `nova/conductor/manager.py:87-183` | 无状态 | RPC 端点，处理对象动作、版本兼容、网络/服务变更 |
| `ComputeTaskManager` | `nova/conductor/manager.py:212` | 任务级内存态 | 建机/迁移/重建/unshelve 长流程编排 |
| `ConductorAPI`（rpcapi） | `nova/conductor/rpcapi.py` | client 版本协商 | 提供 `build_instances`(`:328`)、`schedule_and_build_instances`(`:358`) 等 cast 接口 |
| `_object_dispatch` | `nova/conductor/manager.py:113` | objinst/objmethod | 把对象动作反序列化后定向调用 |

## 3. 核心处理管线与关键阈值（Pipeline & Thresholds）

```text
nova/conductor/manager.py:517 ComputeTaskManager.build_instances(context, instances, image, ...)
  ├─ [Stage 1: 调度] self._schedule_instances(...) -> 选中 (host, node)
  ├─ [Stage 2: cell 路由] _populate_instance_mapping(instance, cell) -> 确定目标 cell
  ├─ [Stage 3: 下发] self.compute_rpcapi.build_and_run_instance(...) (:610) -> RPC cast 到 compute
  └─ [Stage 4: 异常] 失败 -> _bury_in_cell0(...) (:865) + _cleanup_allocated_networks (:357)
```

| 关键机制 / 阈值 | 代码值 / 实现 | 源码位置 | 业务/性能作用（修改影响） |
|---|---|---|---|
| RPC 版本向下兼容 | `build_instances` 按 `can_send_version` 逐级降 `1.10→1.9→1.8→1.7→1.5` | `nova/conductor/rpcapi.py:330-352` | 升级滚动期间新旧 compute 混跑不中断；改字段须补版本分支 |
| 服务入口 | `nova-conductor = nova.cmd.conductor:main` | `setup.cfg:55` | 独立进程，horizontal 扩展 |
| 状态回写 | `_set_vm_state_and_notify` | `nova/conductor/manager.py:351` | 迁移失败时统一落 `vm_state` 并通知 |

## 4. 共变耦合与扩展清单（Agent Co-Change Playbook）

- **新增编排动作**：改 `nova/conductor/manager.py` 的 `ComputeTaskManager` 方法 → 在 `nova/conductor/rpcapi.py` 增加带版本协商的 cast 接口 → 在 `nova/compute/api.py:243 API` 增加调用入口 → 更新 [`topology-and-mapping.md`](../integrations/topology-and-mapping.md) → 跑 conductor 单测。
- **改对象分发**：动 `nova/conductor/manager.py:113 _object_dispatch` 必须同步所有 `nova/objects/` 的 `obj_*` 方法签名与版本兼容测试。
- **RPC 版本纪律**：任何 cast 载荷新增字段必须新增 `can_send_version` 分支（`nova/conductor/rpcapi.py:330`），否则老版本 compute 解析失败。
