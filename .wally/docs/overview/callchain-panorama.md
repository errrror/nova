---
kind: panorama
scope: callchain-panorama
status: draft
origin: generated
source_paths: [nova/api/openstack/compute/servers.py, nova/compute/api.py, nova/conductor/rpcapi.py, nova/conductor/manager.py, nova/compute/manager.py, nova/virt/libvirt/driver.py, nova/rpc.py]
symbols: [ServersController.create, API.create, build_instances, build_and_run_instance, spawn, get_client]
upstream: [INDEX.md]
downstream: [integrations/topology-and-mapping.md, contracts/error-codes.md]
---

# 主干调用链全景

本页提炼贯穿全仓的三条主干执行链：同步 HTTP 建机链、异步落机执行链、周期状态收敛链。链上所有跨进程跳转均经 `oslo.messaging` RPC（`nova/rpc.py:175 get_client`），静态搜索会在 cast/call 处断链，需按本页桥接表追踪。

## 1. 主干链路索引

| 链路 ID | 链路名称 | 模式 | 起点符号（`路径:行号`） | 终点落点（存储 / 下游 / 产物） | 对应业务页 |
|---|---|---|---|---|---|
| `CC-01` | HTTP 建机请求入向 | 同步请求 | `ServersController.create` (`nova/api/openstack/compute/servers.py:453`) | `conductor.build_instances` 投 RPC | [`business/wf-instance-boot.md`](../business/wf-instance-boot.md) |
| `CC-02` | 实例落机执行 | 异步 cast + 本地执行 | `ComputeManager.build_and_run_instance` (`nova/compute/manager.py:1702`) | hypervisor `spawn` (`nova/virt/libvirt/driver.py:2779`) | [`business/wf-instance-boot.md`](../business/wf-instance-boot.md) |
| `CC-03` | 周期状态收敛 | 守护周期任务 | `Manager.periodic_tasks` (`nova/manager.py:104`) | 资源账本 `update_available_resource` (`nova/compute/resource_tracker.py:624`) | [`operations/runbook-and-observability.md`](../operations/runbook-and-observability.md) |

---

## 2. 符号级条件调用树（Hop-by-Hop Symbolic Traces）

### `CC-01`：HTTP 建机请求入向

```text
POST /servers -> nova/api/openstack/compute/servers.py:453 ServersController.create(body)
  ├─ [parse] servers.py:457-477 解析密码/名称/microversion 字段 -> create_kwargs
  ├─ [guard: 策略] servers.py:483 context.can("compute:create", target) -> 越权 raise
  ├─ [guard: 配额] nova/compute/api.py:1584 API.create(...) -> QuotaEngine.reserve
  └─ [outbound: RPC cast] nova/conductor/rpcapi.py:328 build_instances(...) -> cctxt.cast("build_instances")
       └─ 经 nova/rpc.py:175 get_client 投递到 conductor topic
```

### `CC-02`：实例落机执行

```text
[RPC 接收] nova/conductor/manager.py:517 ComputeTaskManager.build_instances(...)
  ├─ [schedule] nova/scheduler/filter_scheduler.py:111 _schedule() -> 选中 (host, node)
  ├─ [outbound cast] nova/conductor/manager.py:610 compute_rpcapi.build_and_run_instance(...)
  ├─ [claim] nova/compute/manager.py:1921 rt.instance_claim(...) -> 资源预留，失败抛 ComputeResourcesUnavailable
  ├─ [resources] nova/compute/manager.py:2067 _build_resources(...) -> 卷/网络/镜像就绪
  ├─ [spawn] nova/compute/manager.py:1943 self.driver.spawn(...) -> nova/virt/libvirt/driver.py:2779
  └─ [error] nova/compute/manager.py:1958 ComputeResourcesUnavailable -> raise RescheduledException 重调度
```

### `CC-03`：周期状态收敛

```text
nova/manager.py:104 Manager.periodic_tasks(context)
  └─ nova/compute/manager.py:6303 _sync_power_states(context)
       ├─ [read] hypervisor 实际 power_state -> nova/compute/manager.py:6379 _sync_instance_power_state
       └─ [reconcile] 对齐 DB 中 Instance.vm_state/power_state
  └─ nova/compute/resource_tracker.py:624 update_available_resource -> 刷新 compute_nodes 账本
```

---

## 3. 跨线程 / 队列 / 子进程 / 协议桥接表（Static-Jump Bridges）

静态搜索在 RPC cast/call、周期注册、驱动动态选择处会断链；下表显式连接投递点与消费入口：

| 投递方符号（`路径:行号`） | 桥接机制（RPC cast / 动态分发 / 周期注册） | 实际接收执行入口（`路径:行号`） | 载荷结构 |
|---|---|---|---|
| `nova/conductor/rpcapi.py:328 build_instances` | `cctxt.cast(context, 'build_instances', **kw)` | `nova/conductor/manager.py:517 build_instances` | `instances[], image_p, filter_properties, admin_password, requested_networks, security_groups` |
| `nova/conductor/manager.py:610 build_and_run_instance` | `compute_rpcapi` 按 host 路由 | `nova/compute/manager.py:1702 build_and_run_instance` | `instance, image, request_spec, filter_properties` |
| `nova/rpc.py:189 get_server` | `oslo.messaging` 监听 topic | 各服务 `*Manager` 的 RPC 端点方法 | `RequestContextSerializer` 反序列化上下文（`nova/rpc.py:140`） |
| `nova/manager.py:104 periodic_tasks` | `oslo_service.periodic_task` 装饰器注册 | `nova/compute/manager.py:1325` 等 16+ `periodic_task` 方法 | `context` |
| `setup.cfg:84` scheduler.driver 入口 | stevedore 动态加载 | `FilterScheduler` / `CachingScheduler` / `ChanceScheduler` (`setup.cfg:85-88`) | driver 名字符串 |

调用链上的异常翻译见 [错误码字典](../contracts/error-codes.md)，入向→出向字段变形见 [参数组装映射](../integrations/topology-and-mapping.md)。


## 4. 共变耦合与排查清单（Agent Co-Change Playbook）

- 跨进程链路改动须同时更新第 3 节桥接表（cast 投递点 ↔ 消费入口），否则静态分析会在 RPC 处断链。
- 修改主干调用树任一环节后，按 [dev-and-test.md](../operations/dev-and-test.md) 的模块→测试映射跑对应回归用例。
- 排查时从符号调用树定位 `path:line` 后，必须回读源码字面（草稿 `status: draft` 仅作线索）。
