---
kind: panorama
scope: glossary
status: draft
origin: generated
source_paths: [nova/compute/vm_states.py, nova/compute/task_states.py, nova/objects/instance.py, nova/objects/base.py, setup.cfg]
symbols: [vm_states, task_states, Instance, NovaObject, NovaObjectSerializer]
upstream: [INDEX.md]
downstream: [business/domain-models/index.md, overview/system-architecture.md]
---

# 领域术语与代码符号精确映射表

本表消除 OpenStack 运维话术、Nova CLI 文案与底层类名/字段名之间的命名鸿沟，供 Agent 把「开机、调度、迁移、宿主机」等自然语言需求精准翻译成代码符号。Nova 是云计算结构控制器，核心抽象是「实例（instance）在多计算节点上的生命周期」。

## 1. 自然语言术语 ↔ 源码符号映射字典

| 需求/业务常见叫法（含别名/缩写） | 精确技术与业务定义 | 源码对应类 / 表 / 字段 / 枚举 | 权威定义位置（`路径:行号`） |
|---|---|---|---|
| 云服务器 / 虚机 / 实例 / VM | 一次可启动的计算资源分配，数据库实体 + ORM 对象 | `nova.objects.instance.Instance` / `instances` 表 | `nova/objects/instance.py:109` (`class Instance`, VERSION `'2.3'`) |
| 开机 / 创建云主机 / boot | 从 API `create` 到 hypervisor `spawn` 的端到端编排 | `ServersController.create` → `API.create` → `build_and_run_instance` | `nova/api/openstack/compute/servers.py:453` |
| 调度 / 选宿主机 / scheduling | 依据过滤与权重选出目标计算节点 | `FilterScheduler._schedule` → `get_filtered_hosts` / `get_weighed_hosts` | `nova/scheduler/filter_scheduler.py:111` |
| 宿主机 / 计算节点 / compute node | 运行虚机的物理机资源账本 | `nova.objects.ComputeNode` / `compute_nodes` 表 | `nova/db/sqlalchemy/models.py:110` |
| 计算服务 / nova-compute | 每台宿主机上的执行守护进程 | `main` → `service.Service.create(binary='nova-compute')` | `nova/cmd/compute.py:42` |
| 纯净编排层 / conductor | 代理数据库访问、无状态任务编排服务 | `ConductorManager` / `ComputeTaskManager` | `nova/conductor/manager.py:87` / `nova/conductor/manager.py:212` |
| 镜像 / image | 来自 Glance 的磁盘镜像元数据 | `GlanceImageServiceV2` / `objects.ImageMeta` | `nova/image/glance.py:189` |
| 云硬盘 / 卷 / volume | 来自 Cinder 的块设备 | `nova.volume.cinder.API` | `nova/volume/cinder.py:309` |
| 网络 / 端口 / port | 来自 Neutron 的虚机网卡挂载点 | `_create_port_minimal` → `create_port` | `nova/network/neutronv2/api.py:357` |
| 裸金属 / baremetal | 由 Ironic 管理的物理机驱动 | `IronicClientWrapper` | `nova/virt/ironic/client_wrapper.py:36` |
| 配额 / quota | 项目级资源上限预定与回滚机制 | `QuotaEngine` / `DbQuotaDriver` | `nova/quota.py:1419` |
| 虚拟化驱动 / virt driver | 屏蔽 hypervisor 差异的统一接口层 | `ComputeDriver` / `LibvirtDriver` | `nova/virt/driver.py:93` / `nova/virt/libvirt/driver.py:295` |
| 命令行入口 | pbr 注册的控制台脚本 | `console_scripts` / `wsgi_scripts` | `setup.cfg:49` |

## 2. 易混概念严格辨析（Disambiguation）

| 概念 A（`源码符号`） | 概念 B（`源码符号`） | 关键差异（粒度 / 读写时机 / 存储位置 / 混用后果） | 对照源码锚点 |
|---|---|---|---|
| 虚拟机状态 `vm_state`（`vm_states.ACTIVE`） | 任务状态 `task_state`（`task_states.SPAWNING`） | 前者是稳定结果态（`ACTIVE`/`ERROR`/`SHELVED`），后者是进行中的瞬时态（调度/联网/生成镜像）。改写 `vm_state` 表示业务结果落定，改 `task_state` 表示流程推进；混淆会让前端进度与资源账本错乱 | `nova/compute/vm_states.py:34` vs `nova/compute/task_states.py:29` |
| 电源状态 `power_state`（`Instance.power_state`） | `vm_state` | 前者来自 hypervisor 的真实供电情况（整数枚举），后者的 OPENSTACK 业务语义状态；`_sync_power_states` 周期对齐两者 | `nova/objects/instance.py:133` (`power_state`) vs `nova/compute/vm_states.py:34` |
| 数据库对象 `Instance`（`nova.objects.instance.Instance`） | ORM 模型 `models.Instance` | 前者是带版本、可跨 conductor RPC 传输并支持 `obj_to_primitive` 序列化的领域对象；后者是 SQLAlchemy 表映射。业务代码只操作领域对象，禁止直接读写 ORM | `nova/objects/instance.py:109` vs `nova/db/sqlalchemy/models.py:200` |
| `nova-api` 服务 | `nova-compute` 服务 | 前者是无状态 HTTP 入口（`api-os-compute`/`api-metadata`/`placement`），后者是有状态执行体并直连 hypervisor；`block_db_access` 在 compute 侧禁用直连 DB | `setup.cfg:50` / `nova/cmd/compute.py:42` |
| 调度器 `SchedulerManager.select_destinations` | 调度驱动 `FilterScheduler._schedule` | 前者是 RPC 端点与定时任务壳，后者才是过滤+权重算法；改算法动后者，改 RPC/周期任务动前者 | `nova/scheduler/manager.py:105` vs `nova/scheduler/filter_scheduler.py:111` |

## 3. 代码命名与枚举惯例

- **状态字面量集中在两个模块**：`vm_states` 定义 `ACTIVE`、`BUILDING`、`ERROR`、`SHELVED`、`SHELVED_OFFLOADED` 等稳定态，并给出 `ALLOW_SOFT_REBOOT`、`ALLOW_HARD_REBOOT`、`ALLOW_RESOURCE_REMOVAL` 等白名单位于 `nova/compute/vm_states.py:34`；`task_states` 定义 `SCHEDULING`、`BLOCK_DEVICE_MAPPING`、`NETWORKING`、`SPAWNING` 等瞬时态，位于 `nova/compute/task_states.py:29`。
- **领域对象统一继承 `NovaObject`**：注册表 `NovaObjectRegistry` 与带版本序列化器 `NovaObjectSerializer` 定义在 `nova/objects/base.py:42` 与 `nova/objects/base.py:184`，所有跨 RPC 对象字段必须能被 `serialize_entity` 处理（`nova/objects/base.py:242`）。
- **命令命名遵循「二进制名 = 模块」**：`console_scripts` 中 `nova-api`、`nova-compute`、`nova-scheduler`、`nova-conductor`、`nova-manage` 分别落到 `nova.cmd.<name>:main`（`setup.cfg:49`），新增命令优先复用该约定。
- **WSGI 应用名与配置段同名**：`compute`/`metadata`/`placement` 三个应用通过 `init_application` 由 `wsgi_app.init_application(name)` 装配（如 `nova/api/metadata/wsgi.py:19`），名称即 paste 配置段名。
- **优雅退避字面量**：重试/降级常以配置默认值表达，例如 Glance 上传/下载重试 `num_retries` 默认 `0`（`nova/conf/glance.py:39`）、Cinder HTTP 重试 `http_retries` 默认 `3`（`nova/conf/cinder.py:69`）。

状态机与实体字段的完整定义见 [核心领域与数据模型总览](../business/domain-models/index.md)。运行时装配顺序见 [系统技术架构](system-architecture.md)。
