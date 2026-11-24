---
kind: component
scope: architecture-index
status: draft
origin: generated
source_paths: [setup.cfg, nova/api/openstack/compute/routes.py, nova/conductor/manager.py, nova/scheduler/filter_scheduler.py, nova/compute/manager.py, nova/virt/driver.py, nova/objects/base.py, nova/cmd/manage.py]
symbols: [APIRouterV21, ConductorManager, FilterScheduler, ComputeManager, ComputeDriver, NovaObject, NovaObjectSerializer]
upstream: [INDEX.md, overview/system-architecture.md]
downstream: [architecture/module-dep-matrix.md]
---

# 组件技术架构总表

本表按运行时框架模型（Archetype）汇总 Nova 全部技术模块，并把不单独成篇的辅助模块与文档/配置目录完整归档，确保全仓顶层与二级源码目录 100% 纳入路由索引。组件 Archetype 分五类：`API Service`、`Core Engine`、`Async/Cron Worker`、`Data & Adapter`、`UI/CLI`。

## 1. 全量核心组件矩阵（Tier 1 & Tier 2）

| 组件标识 | 框架模型（Archetype） | 源码路径 | 核心入口符号（`路径:行号`） | 技术能力与业务边界 | 直接上游 | 直接下游 | 详情文档 |
|---|---|---|---|---|---|---|---|
| `api-service` | `API Service` | `nova/api/`（`openstack/`、`ec2/`、`metadata/`、`validation/`） | `APIRouterV21` (`nova/api/openstack/compute/routes.py:876`) | 129 条 v2.1 路由、microversion 协商、策略鉴权 | 租户/CLI/OS SDK | conductor、scheduler | [`api-service.md`](api-service.md) |
| `conductor-engine` | `Core Engine` | `nova/conductor/` | `ConductorManager` (`nova/conductor/manager.py:87`) / `ComputeTaskManager` (`nova/conductor/manager.py:212`) | 无状态编排、DB 代理、对象动作分发 | api-service | scheduler、compute、DB | [`conductor-engine.md`](conductor-engine.md) |
| `scheduler-engine` | `Core Engine` | `nova/scheduler/` | `FilterScheduler._schedule` (`nova/scheduler/filter_scheduler.py:111`) | 过滤+权重选节点、cells 宿主发现 | conductor (RPC) | DB / host state | [`scheduler-engine.md`](scheduler-engine.md) |
| `compute-worker` | `Async/Cron Worker` | `nova/compute/` | `ComputeManager.build_and_run_instance` (`nova/compute/manager.py:1702`) | 实例状态机、资源 claim、16+ 周期任务 | conductor (RPC) | virt-driver、DB | [`compute-worker.md`](compute-worker.md) |
| `virt-and-data` | `Data & Adapter` | `nova/virt/`、`nova/objects/`、`nova/db/`、`nova/rpc.py` | `ComputeDriver` (`nova/virt/driver.py:93`) / `NovaObject` (`nova/objects/base.py:84`) | hypervisor 抽象、带版本对象、SQLAlchemy 持久化、RPC 底座 | compute-worker | 外部 hypervisor / DB / MQ | [`virt-and-data.md`](virt-and-data.md) |
| `cli-and-cmd` | `UI/CLI` | `nova/cmd/` | `main` (`nova/cmd/manage.py:1672`)、各服务 `main` (`setup.cfg:49`) | 守护服务入口、运维命令行、WSGI 工厂 | 运维/系统 | 各服务 Manager | [`cli-and-cmd.md`](cli-and-cmd.md) |

## 2. 轻量辅助模块归档表（Tier 3 Utilities — 零遗漏兜底）

以下目录/文件不单独成篇，集中登记供 Agent 快速定位，避免重复造轮子。覆盖全部未在上表出现的顶层与二级源码目录：

| 源码文件/目录路径 | 核心导出函数 / 类 / 常量 | 调用方模块 | 具体职责说明 |
|---|---|---|---|
| `nova/conf/`（50+ 文件，`nova/conf/opts.py:43 list_opts`） | 各 `[group]_opts` 列表 | 全仓 | oslo.config 选项集中注册，pbr 入口 `nova.conf.opts:list_opts`（`setup.cfg:30`） |
| `nova/policies/`（75 文件） | `list_rules` / `*_policies` 常量 | api-service | 策略规则集合，入口 `nova.policies:list_rules`（`setup.cfg:44`） |
| `nova/network/`（`nova/network/api.py`、`neutronv2/api.py:122 get_client`） | `API` / `get_client` | compute-worker | Neutron 网络适配，`neutronv2/` 实现云网端口分配 |
| `nova/image/`（`nova/image/glance.py:189 GlanceImageServiceV2`） | `GlanceImageServiceV2` / `GlanceClientWrapper` | compute-worker | Glance 镜像封装，详见 [`downstream/glance.md`](../integrations/downstream/glance.md) |
| `nova/volume/`（`nova/volume/cinder.py:82 cinderclient`） | `API` / `cinderclient` | compute-worker | Cinder 卷封装，详见 [`downstream/cinder.md`](../integrations/downstream/cinder.md) |
| `nova/cells/`（`nova/cells/manager.py:48 CellsManager`） | `CellsManager.build_instances` | conductor | Cells v1 分层编排，跨 cell 任务路由 |
| `nova/notifications/` | notification 对象 | 全仓 | oslo.versionednotification 通知载荷定义 |
| `nova/console/`、`nova/consoleauth/`、`nova/vnc/` | console proxy 入口 | cli-and-cmd | 控制台/VNC/SPICE 代理服务 |
| `nova/pci/`、`nova/servicegroup/`、`nova/ipv6/`、`nova/keymgr/`、`nova/hacking/` | PCI 直通、服务组、IPv6、密钥、dev 检查 | compute-worker / 构建 | 专业子域工具集 |
| `nova/CA/` | 证书颁发工具 | 测试/部署 | 历史 CA 证书工具归档 |
| `nova/common/` | `config.py` 中间件默认值 | 构建 | `setup.cfg:34` 的 opts.defaults 入口 |
| `nova/locale/` | `.pot`/`.po` 翻译目录 | 构建 | babel 编目（`setup.cfg:106-118`） |
| `nova/tests/`（1178 文件，`functional/`、`unit/`、`live_migration/`） | 各 `test_*` | 验证 | 单测/功能测试，映射见 [`dev-and-test.md`](../operations/dev-and-test.md) |
| `nova/*.py` 顶层模块（`nova/quota.py:1419 QuotaEngine`、`nova/policy.py:126 authorize`、`nova/context.py`、`nova/utils.py`、`nova/exception.py:58 NovaException`） | 配额/策略/上下文/工具/异常 | 全仓 | 横切基础模块 |
| 顶层文档与配置目录 `api-ref/`、`api-guide/`、`placement-api-ref/`、`doc/`、`releasenotes/`、`etc/`、`tools/`、`devstack/`、`gate/`、`contrib/`、`plugins/` | 构建/CI/部署资产 | 构建运维 | 非运行时源码，边界声明见 [`boundary.md`](../operations/boundary.md) |

模块间真实调用边、高扇入底座与环检测见 [模块依赖矩阵](module-dep-matrix.md)。


## 3. 源码目录零遗漏对账

本总表的 Tier 1/2 组件矩阵覆盖 `nova/api/`、`nova/conductor/`、`nova/scheduler/`、`nova/compute/`、`nova/virt/`、`nova/objects/`、`nova/db/`、`nova/cmd/` 全部核心运行时目录；Tier 3 归档表兜底 `nova/conf/`、`nova/policies/`、`nova/network/`、`nova/image/`、`nova/volume/`、`nova/cells/`、`nova/notifications/`、`nova/console*`、`nova/pci/`、`nova/servicegroup/`、`nova/ipv6/`、`nova/keymgr/`、`nova/CA/`、`nova/common/`、`nova/locale/`、`nova/tests/` 与顶层 `nova/*.py`。顶层文档/构建目录（`api-ref/`、`api-guide/`、`placement-api-ref/`、`doc/`、`releasenotes/`、`etc/`、`tools/`、`devstack/`、`gate/`、`contrib/`、`plugins/`）在 [认知边界声明](../operations/boundary.md) 登记。未映射源码目录为 0。

## 4. 共变耦合与修改清单（Agent Co-Change Playbook）

新增顶层模块时：先在 Tier 1/2 或 Tier 3 表登记并写 `path:line` 锚点 → 在 [模块依赖矩阵](module-dep-matrix.md) 补调用边 → 更新根 [INDEX.md](../INDEX.md) 的反向索引 → 按 [dev-and-test.md](../operations/dev-and-test.md) 跑对应单测。
