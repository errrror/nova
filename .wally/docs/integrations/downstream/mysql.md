---
kind: downstream-contract
scope: mysql
status: draft
origin: generated
source_paths: [nova/config.py, nova/db/sqlalchemy/api.py, nova/db/sqlalchemy/models.py, nova/conf/database.py]
symbols: [configure, instance_create, instance_get, Instance, ComputeNode]
upstream: [integrations/index.md, architecture/virt-and-data.md]
downstream: []
---

# 下游出向接口契约：`mysql`

MySQL（经 SQLAlchemy ORM）承载 Nova 全部结构化数据持久化。本仓通过 `nova/db/sqlalchemy/api.py` 暴露 CRUD 函数，`nova/config.py:58 sqlalchemy_api.configure(CONF)` 注入连接配置；`nova-compute` 侧禁直连 DB，统一由 conductor 代理。所有查询 100% 参数化，遵守「SQL 一律参数化」约束。

## 1. 封装定位与连接契约

| 契约项 | 精确值 / 规则 | 源码锚点（`路径:行号`） |
|---|---|---|
| 本仓业务封装文件 | `nova/db/sqlalchemy/api.py` | `nova/config.py:58` 调 `configure` |
| ORM 模型定义 | `nova/db/sqlalchemy/models.py` | `nova/db/sqlalchemy/models.py:200` (`Instance`) |
| 连接配置组 | `CONF.database`（`nova/conf/database.py`） | `nova/conf/database.py` |
| 连接读取 | `_get_db_conf(conf_group, connection=None)` | `nova/db/sqlalchemy/api.py:82` |
| 成功判定 | ORM session commit 成功；异常经 DBAPI 上浮 | `nova/db/sqlalchemy/api.py` |

---

## 2. 本仓上游调用方反查表（Who Calls This Wrapper）

| 本仓封装方法 | 上游调用模块与函数 | 所属业务流 / 接口 | 调用点锚点（`路径:行号`） |
|---|---|---|---|
| `instance_create`/`instance_update` | conductor 对象持久化 | 建机/状态更新 | `nova/conductor/manager.py` |
| `service_create` | 服务注册 | 服务启动 | `nova/db/sqlalchemy/api.py:584` |
| `compute_node` CRUD | resource tracker 账本 | 周期资源同步 | `nova/compute/resource_tracker.py:624` |

---

## 3. 封装方法总清单

| 序号 | 封装函数签名 | 下游目标 | 读写类型 | 定义锚点（`路径:行号`） |
|---|---|---|---|---|
| 1 | `service_create(context, values)` | `services` 表 | 写 | `nova/db/sqlalchemy/api.py:584` |
| 2 | `instance_*` 系列 | `instances` 表 | 读写 | `nova/db/sqlalchemy/api.py` |
| 3 | `compute_node_*` 系列 | `compute_nodes` 表 | 读写 | `nova/db/sqlalchemy/api.py:625-659` |

---

## 4. 逐方法请求字典与响应解包契约（Full Dict Schemas）

### 4.1 `instance_create` → `instances` 表（`nova/db/sqlalchemy/api.py`）

#### A. 发往下游的组装字典表（Outbound Payload Dict）

```json
{
  "uuid": "<instance-uuid>",
  "project_id": "<tenant>",
  "user_id": "<user>",
  "display_name": "vm1",
  "vm_state": "building",
  "task_state": "scheduling",
  "host": "<compute-host>"
}
```

| 下游字典键路径 | 类型 | 必填条件 | 默认值 / 固定值 | 值来源与转换逻辑 | 组装行号 |
|---|---|---|---|---|---|
| `uuid` | `str(36)` | 必填 | — | `uuidutils.generate_uuid()` | `nova/db/sqlalchemy/models.py:202` 附近 |
| `vm_state` / `task_state` | `str` | 可选 | — | 来自 `nova/compute/vm_states.py` / `task_states.py` 字面量 | `nova/objects/instance.py:133-134` |
| `host` | `str` | 调度后 | — | 由 `instance_claim` 回填 | `nova/compute/manager.py:1921` |

#### B. 下游返回字典与解包规则表（Response Unpacking）

| 下游返回键路径 | 类型 | 本仓提取、判空兜底与转换规则 | 解包行号 |
|---|---|---|---|
| `instance` ORM 行 | `Instance` 对象 | 经 `nova/objects/base.py:184 NovaObjectSerializer` 转领域对象 | `nova/db/sqlalchemy/models.py:200` |
| `instance.uuid` | `str` | 唯一约束 `uniq_instances0uuid`，重复抛 `DBDuplicateEntry` | `nova/db/sqlalchemy/models.py:224` |

#### C. 下游错误码拦截与翻译

| 下游错误码 / 条件 | 下游语义 | 本仓转换后的异常 / 降级返回值 | 代码行号 |
|---|---|---|---|
| `DBDuplicateEntry` | 唯一约束冲突 | 上浮为 Nova 异常 | `nova/db/sqlalchemy/api.py` |
| 连接失败 | DB 不可达 | 服务启动/请求失败（无本地 Fixture 降级） | `nova/config.py:58` |

## 5. 共变耦合与修改清单（Co-Change Playbook）

- 改表结构：同步 `nova/db/sqlalchemy/models.py` 列定义 → `nova/db/sqlalchemy/api_migrations/` 迁移 → `nova/objects/instance.py:109` 字段与 `VERSION` → [`domain-models/index.md`](../../business/domain-models/index.md)。
- **安全纪律**：所有查询必须参数化（禁字符串拼接）；DB 连接串口令不得回显（参照 `nova/cmd/manage.py:127 mask_passwd_in_url`）。
