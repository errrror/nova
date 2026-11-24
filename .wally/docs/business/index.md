---
kind: workflow
scope: business-index
status: draft
origin: generated
source_paths: [nova/api/openstack/compute/routes.py, nova/api/openstack/compute/servers.py, nova/compute/api.py, nova/scheduler/manager.py, nova/quota.py]
symbols: [ServersController, API, ComputeTaskManager, SchedulerManager, QuotaEngine]
upstream: [INDEX.md, overview/business-architecture.md]
downstream: [business/domain-models/index.md, contracts/api-reference.md]
---

# 业务能力与核心流程总清单

本页全量归档 Nova 的对外业务用例与后台自动化闭环流程（`WF-*`），建立「业务场景 ↔ 触发入口 ↔ 下游扇出 ↔ 数据模型」结构化索引。业务核心围绕实例生命周期展开，所有流程入口收敛于 `nova/api/openstack/compute/routes.py:406` 的 129 条 v2.1 路由与各服务的周期任务。

## 1. 全量业务流程路由总表（Complete Workflow Inventory）

| 流程 ID | 业务域 | 流程名称 | 触发入口（路由 / 定时器 / 命令 + `路径:行号`） | 串联模块与外部下游链 | 变更的核心实体/状态 | 专页路径 |
|---|---|---|---|---|---|---|
| `WF-01` | 实例生命周期 | 创建并落机实例 | `POST /servers` (`nova/api/openstack/compute/servers.py:453`) | `API → Conductor → Scheduler → Compute → Virt` | `Instance (BUILDING→ACTIVE)` | [`wf-instance-boot.md`](wf-instance-boot.md) |
| `WF-02` | 实例生命周期 | 删除/重建/迁移/快照动作 | `POST /servers/{id}/action` (`nova/api/openstack/compute/routes.py:787`)、`nova/compute/api.py:2907` | `API → Conductor.ComputeTaskManager → Compute → Virt` | `Instance (ACTIVE→...→ACTIVE)` | [`wf-instance-actions.md`](wf-instance-actions.md) |
| `WF-03` | 调度与资源 | 选目标计算节点 | RPC `select_destinations` (`nova/scheduler/manager.py:105`) | `SchedulerManager → FilterScheduler → filters/weights` | 无持久状态 | [`wf-scheduling.md`](wf-scheduling.md) |
| `WF-04` | 资源治理 | 配额预留/提交/回滚 | `nova/quota.py:1640` / `:764` / `:787` | `QuotaEngine → DbQuotaDriver → DB` | `quotas`/`reservations` | [`contracts/configuration.md`](../contracts/configuration.md) |
| `WF-05` | 状态收敛 | 周期电源/资源/删除巡检 | `nova/manager.py:104 periodic_tasks` | `ComputeManager 周期任务 → ResourceTracker → Virt` | `Instance`/`compute_nodes` | [`runbook-and-observability.md`](../operations/runbook-and-observability.md) |

## 2. 业务域 ↔ 接口组 ↔ 错误码 ↔ 配置键交叉速查

| 业务域 | 入向接口前缀（见 [`api-reference.md`](../contracts/api-reference.md)） | 调用的外部下游封装 | 专属错误码 / 降级标识前缀（见 [`error-codes.md`](../contracts/error-codes.md)） | 核心控制配置键（见 [`configuration.md`](../contracts/configuration.md)） |
|---|---|---|---|---|
| 实例生命周期 | `/servers*`、`/os-server-groups*` | [Glance](../integrations/downstream/glance.md)、[Cinder](../integrations/downstream/cinder.md)、[Neutron](../integrations/downstream/neutron.md) | `InstanceNotFound`、`BuildAbortException`、`RescheduledException` | `sync_power_state_interval`、`image_cache_manager_interval` |
| 调度与资源 | `/os-aggregates*`、`/os-hypervisors*` | [MySQL](../integrations/downstream/mysql.md) | `NoValidHost`、`ComputeResourcesUnavailable` | `scheduler_driver`、`*interval` |
| 存储/网络扩展 | `/os-volumes*`、`/os-security-groups*` | Cinder、Neutron | `VolumeNotFound`、`NoUniqueMatch` | `cross_az_attach`、`neutron.url` |

核心流程的精确调用树、规则阈值与状态机见各专页；数据实体字段字典见 [核心领域与数据模型总览](domain-models/index.md)。


## 3. 后台自动化闭环流程补充

除 `WF-01`~`WF-05` 外，实例删除排队由 `_reclaim_queued_deletes`（`nova/compute/manager.py:6539`）与 `_run_pending_deletes`（`nova/compute/manager.py:6984`）周期回收；镜像缓存清理由 `_run_image_cache_manager_pass`（`nova/compute/manager.py:6921`）承担。这些闭环由 `nova/manager.py:104 periodic_tasks` 统一驱动，不经 HTTP 入向，排障见 [排障 Runbook](../operations/runbook-and-observability.md)。

## 4. 共变耦合与修改清单（Agent Co-Change Playbook）

新增业务流程时：在 [业务架构全景](../overview/business-architecture.md) 的 `WF-*` 总表登记 → 写流程专页并附符号调用树 → 更新 [`api-reference.md`](../contracts/api-reference.md) 路由交叉索引 → 在 [dev-and-test.md](../operations/dev-and-test.md) 映射必跑单测。
