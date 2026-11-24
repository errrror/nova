---
kind: component
scope: virt-and-data
status: draft
origin: generated
source_paths: [nova/virt/driver.py, nova/virt/libvirt/driver.py, setup.cfg, nova/objects/base.py, nova/objects/instance.py, nova/db/sqlalchemy/api.py, nova/db/sqlalchemy/models.py, nova/rpc.py]
symbols: [ComputeDriver, LibvirtDriver, spawn, NovaObject, NovaPersistentObject, Instance, get_client]
upstream: [compute-worker.md, scheduler-engine.md]
downstream: [integrations/index.md, business/domain-models/index.md]
---

# `virt-and-data`（数据持久化 / 缓存 / 传输底座组件）

> **边界切分铁律**：本页聚焦 hypervisor 驱动抽象、带版本领域对象、SQLAlchemy 持久化与 RPC 底座。各外部下游系统（Glance/Cinder/Neutron/Ironic/Keystone）的**业务封装层字典拼装**一律在 [`integrations/downstream/`](../integrations/index.md) 独立展开，本页不省略带过。

本组件是 Nova 的存储与适配底座：`nova/virt/` 用 `ComputeDriver` 统一屏蔽 libvirt/Hyper-V/VMware/XenAPI/Ironic/PowerVM 差异；`nova/objects/` 提供可跨进程序列化、带版本号的领域对象；`nova/db/sqlalchemy/` 负责 MySQL 持久化；`nova/rpc.py` 提供消息传输底座。

## 1. 本地持久化契约（SQL / 文件存储）

| 表名 / 磁盘文件路径模式 | 主键 / 唯一约束 | 权威读写函数（`路径:行号`） | 事务、锁与安全约束 |
|---|---|---|---|
| `instances` | `id` 主键，`uuid` 唯一索引/约束 | `nova/db/sqlalchemy/models.py:200-225` (`class Instance`, `__tablename__` `:202`) | SQLAlchemy ORM，查询全部参数化 |
| `compute_nodes` | `id` 主键 | `nova/db/sqlalchemy/models.py:110-113` (`class ComputeNode`) | 资源账本，周期由 resource tracker 写回 |
| `nova/db/sqlalchemy/api.py` 全量 CRUD | — | `instance_create`/`instance_get`/`instance_update` 等 | 100% 参数化 SQL，统一 `configure(CONF)` (`nova/config.py:58`) |

## 2. 领域对象版本与序列化机制

| 缓存/版本维度 | 实现细节与常量 | 源码锚点（`路径:行号`） |
|---|---|---|
| 领域对象基类 | `NovaObject` / `NovaPersistentObject` | `nova/objects/base.py:84` / `:154` |
| 对象注册表 | `NovaObjectRegistry.registration_hook` | `nova/objects/base.py:42-45` |
| 跨进程序列化器 | `NovaObjectSerializer.serialize_entity` / `deserialize_entity` | `nova/objects/base.py:184` / `:242` / `:251` |
| 实例对象版本 | `Instance.VERSION = '2.3'`，字段含 `vm_state`/`task_state`/`power_state`/`host` | `nova/objects/instance.py:109-145` |

## 3. 通用外部传输底座（Transport Base）

| 底座类 / 函数 | 统一鉴权 / 序列化注入 | 默认策略 | 源码锚点 |
|---|---|---|---|
| `nova/rpc.py` `get_client`/`get_server` | `RequestContextSerializer` 注入请求上下文 | cast 异步 / call 同步；`ClientRouter` 版本协商 | `nova/rpc.py:175` / `:189` / `:122` / `:397` |
| `ComputeDriver` | 由 stevedore 入口动态选择实现 | 抽象 `spawn`/`destroy`/`live_migration`/`get_host_stats` | `nova/virt/driver.py:93` / `:264` / `:289` / `:822` |
| `LibvirtDriver` | libvirt 连接由 conf 管理 | `spawn` `:2779` → `_create_domain_and_network` `:5196` → `_create_domain` `:5145` | `nova/virt/libvirt/driver.py:295` |

- **继承/调用本底座的所有下游业务封装清单**：详见 [`integrations/index.md`](../integrations/index.md)。

## 4. 共变耦合与修改清单（Agent Co-Change Playbook）

- **新增 hypervisor 驱动**：实现 `nova/virt/driver.py:93 ComputeDriver` 全部抽象方法 → 在 `setup.cfg` / `nova/virt/<driver>/` 注册 → 同步 `VENDOR` 类边界约定（如适用）→ 跑 `nova/tests/unit/virt/` 用例。
- **领域对象字段变更**：改 `nova/objects/instance.py:109` 的 `fields` 必须提升 `VERSION` → 同步 `nova/db/sqlalchemy/models.py:200` 列定义 → 加 backport 兼容 → 更新 [`domain-models/index.md`](../business/domain-models/index.md)。
- **RPC 序列化变更**：动 `nova/objects/base.py:184 NovaObjectSerializer` 影响所有跨进程对象，必须全量跑 conductor/compute 集成测试。
