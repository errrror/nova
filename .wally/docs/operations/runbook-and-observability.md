---
kind: operations
scope: runbook-and-observability
status: draft
origin: generated
source_paths: [nova/compute/utils.py, nova/compute/manager.py, nova/rpc.py, nova/cmd/status.py, nova/conf/compute.py, nova/exception.py]
symbols: [notify_about_instance_usage, notify_about_instance_create, get_notifier, _sync_power_states, NovaException]
upstream: [contracts/error-codes.md]
downstream: []
---

# 可观测性信号与故障定位决策树（Agent Runbook）

Nova 的可观测性由三类内建信号构成：实例生命周期通知（经 `oslo.messaging` notifier 发到消息总线）、周期任务状态收敛日志、以及 `nova-status upgrade check` 升级就绪检查。本页给出从现象到源码根因的确定性排查路径。

## 1. 诊断信号读取入口表

| 信号类别 | 接口 / 磁盘文件位置 | 核心诊断字段 | 源码锚点（`路径:行号`） |
|---|---|---|---|
| 实例使用通知 | notifier 发 `compute.instance.*` | `event_suffix`、`fault`、`extra_usage_info` | `nova/compute/utils.py:303 notify_about_instance_usage` |
| 实例创建生命周期通知 | START/ERROR phase | `phase`（`NotificationPhase.START/ERROR`）、`exception` | `nova/compute/utils.py:380 notify_about_instance_create` |
| 实例动作通知 | action + phase | `action`、`phase` | `nova/compute/utils.py:352 notify_about_instance_action` |
| 消息通知器 | RPC notifier | `publisher_id`、`priority` | `nova/rpc.py:205 get_notifier` / `:213 get_versioned_notifier` |
| 升级就绪检查 | `nova-status upgrade check` | 退出码 0/1/2（成功/警告/失败） | `nova/cmd/status.py:52-65` / `_upgrade_checks:360` |
| 周期状态巡检 | compute manager 日志 | `sync_power_state_interval`、`image_cache_manager_interval` | `nova/conf/compute.py:680` / `:655` |

## 2. 症状 → 根因定位与修复决策树

### 症状 A：实例状态卡在 `BUILDING`/`SPAWNING`，未变 `ACTIVE`

1. 查生命周期通知 `create.error` 与 `exception` 字段（`nova/compute/utils.py:380`）——若有 `BuildAbortException`（`nova/exception.py:1591`），定位落机中止。
2. 查 claim 阶段：是否抛 `ComputeResourcesUnavailable`（`nova/compute/manager.py:1958`）——若是则被 `RescheduledException`（`:1965`）重调度，检查目标 host 容量。
3. 查资源准备 `_build_resources`（`nova/compute/manager.py:2067`）：卷（Cinder attach `nova/volume/cinder.py:371`）、端口（Neutron `nova/network/neutronv2/api.py:357`）、镜像（Glance `nova/image/glance.py:213`）任一失败都会中止。
4. 查 hypervisor `driver.spawn`（`nova/compute/manager.py:1943` → `nova/virt/libvirt/driver.py:2779`）的底层日志。

### 症状 B：实例 `power_state` 与 hypervisor 实际状态不一致

1. 查周期任务 `_sync_power_states`（`nova/compute/manager.py:6303`，装饰器 `:6301`）与 `_sync_instance_power_state`（`:6379`）——受 `sync_power_state_interval`（`nova/conf/compute.py:680`）控制。
2. 检查宿主 `nova-compute` 服务是否存活：周期任务随 `Service.start`（`nova/service.py:138`）注册。

### 症状 C：调度报 `NoValidHost`

1. 读异常 `nova/exception.py:1362`。
2. 查 `FilterScheduler._schedule`（`nova/scheduler/filter_scheduler.py:111`）过滤阶段（`:295`），逐个核对 filter 条件与 `compute_nodes` 账本（`nova/db/sqlalchemy/models.py:113`）。
3. 查周期 `_discover_hosts_in_cells`（`nova/scheduler/manager.py:90`）是否发现宿主。

### 症状 D：`nova-status upgrade check` 非 0 退出

1. 读退出码语义：`1` 警告、`2` 失败（`nova/cmd/status.py:56-65`）。
2. 逐项核对 `_upgrade_checks`（`nova/cmd/status.py:360`），常见为未升级的 compute 服务（`:106`）。

错误码全表见 [错误码字典](../contracts/error-codes.md)；部署边界见 [部署与运行时](deployment-and-runtime.md)。


## 3. 日志与信号分级速查

| 信号级别 | 典型来源 | 处置优先级 |
|---|---|---|
| 错误通知 | `create.error`（`nova/compute/utils.py:380`）、`instance.action` 异常 phase (`nova/compute/utils.py:352`) | 立即定位，读 `exception` 字段 |
| 周期巡检告警 | power 状态不一致 (`nova/compute/manager.py:6303`)、无可用 host (`nova/exception.py:1362`) | 当班处理 |
| 升级就绪失败 | `nova-status` 退出码 2 (`nova/cmd/status.py:64`) | 升级前必须清零 |

## 4. 共变耦合与修改清单（Agent Co-Change Playbook）

新增诊断信号时：`nova/compute/utils.py` 增通知函数 → 在 `nova/rpc.py:205 get_notifier` 确认 publisher → 更新本页决策树与 [错误码字典](../contracts/error-codes.md) → 补 `nova/tests/unit/compute/test_compute_utils.py` 断言。
