---
kind: api-contract
scope: compute-v21-endpoint-schemas
status: draft
origin: generated
source_paths: [nova/api/openstack/compute/routes.py, nova/api/openstack/compute/servers.py, nova/api/openstack/compute/flavors.py, nova/api/openstack/compute/images.py, nova/api/openstack/compute/keypairs.py, nova/api/openstack/compute/aggregates.py]
symbols: [ServersController.create, ServersController.show, ServersController.delete, flavors, images, keypairs]
upstream: [contracts/api-reference.md]
downstream: [contracts/error-codes.md]
---

# Compute API v2.1 逐接口字段字典（分组子页）

本页是 [`api-reference.md`](../api-reference.md) 的分组展开，覆盖 v2.1 路由中高频接口组（servers/flavors/images/keypairs/aggregates）的精确入参/出参。全部路由前缀来自 `nova/api/openstack/compute/routes.py:406 ROUTE_LIST`（共 129 条），microversion 决定字段是否生效。

## 1. `/servers` 服务器资源接口组

### `[POST] /servers` — 创建实例

- **入口**：`nova/api/openstack/compute/servers.py:453 ServersController.create(req, body)` → `nova/compute/api.py:1584 API.create`（关联 [`wf-instance-boot.md`](../../business/wf-instance-boot.md)）。
- **控制器构造**：`server_controller = functools.partial(_create_controller, ...)` (`routes.py:277`)。
- **入参字典**：

| 位置 | 字段名 | 类型 | 必填 | 默认值 / 校验约束 | 含义与透传去向 |
|---|---|---|---|---|---|
| `body` | `server.name` | `str` | 是 | `common.normalize_name` 规范化 (`servers.py:458`) | 实例显示名 |
| `body` | `server.imageRef` | `str` | 条件 | 与 BDM 二选一 | 镜像引用 → Glance |
| `body` | `server.flavorRef` | `str` | 是 | 规格 ID | → `objects.Flavor` |
| `body` | `server.description` | `str` | 否 | 仅 ≥2.19 生效 (`servers.py:460`) | 描述 |
| `body` | `server.tags` | `list[str]` | 否 | 仅 ≥2.52 生效 (`servers.py:473`) | 标签 |
| `body` | `server.block_device_mapping` | `list` | 否 | 卷设备映射 | → Cinder attach |
| `body` | `server.networks` | `list` | 否 | 网络指定 | → Neutron port |
| `body` | `server.adminPass` | `str` | 否 | `_get_server_admin_password` (`servers.py:457`) | 管理员密码 |

- **出参结构**（`HTTP 202`）：实例 JSON 对象；`vm_state=BUILDING`。
- **错误分支**：`400` (`servers.py:491-492` InvalidInput)、`403` (`servers.py:483`)、配额异常。

### `[GET] /servers/{id}` — 查询实例

- **入口**：`servers.py:437 ServersController.show`；路由 `routes.py:782`。
- **入参**：`path.id`（实例 UUID，非空的可见性校验）；`query`（部分扩展）。
- **出参**：实例完整 JSON（含 `vm_state`/`task_state`/`power_state`/`addresses` 等字段，定义于 `nova/objects/instance.py:117`）。
- **错误**：`404`（`nova/exception.py:1452 InstanceNotFound`）。

### `[DELETE] /servers/{id}` — 删除实例

- **入口**：`servers.py:828 ServersController.delete` → `nova/compute/api.py:2124 API.delete`；路由 `routes.py:785`。
- **出参**：`HTTP 204`。
- **错误**：`404`（不存在）、`403`（越权）。

### `[POST] /servers/{id}/action` — 实例动作

- **路由**：`routes.py:787`；动作名映射到 controller 方法（rebuild/resize/migrate/live-migrate/snapshot 等）。
- **关键动作**：rebuild (`nova/compute/api.py:2907`)、resize (`:3110`)、delete。详见 [`wf-instance-actions.md`](../../business/wf-instance-actions.md)。

## 2. `/flavors` 规格接口组

| 方法 / 路径 | 功能 | Handler | 出参 |
|---|---|---|---|
| `GET /flavors` | 规格列表 | `nova/api/openstack/compute/flavors.py` | flavor 对象数组 |
| `GET /flavors/detail` | 规格详情列表 | 同上 | 含 `vcpus`/`memory_mb`/`root_gb` (`nova/objects/flavor.py:219`) |
| `GET /flavors/{id}` | 单规格 | 同上 | flavor 对象 |
| `POST /flavors/{id}/action` | 规格动作 | `routes.py:434` | — |

## 3. `/images` 镜像接口组

| 方法 / 路径 | 功能 | Handler |
|---|---|---|
| `GET /images`、`/images/detail` | 镜像列表/详情 | `nova/api/openstack/compute/images.py` |
| `GET /images/{id}` | 单镜像 | 同上 |
| `GET/POST/DELETE /images/{image_id}/metadata*` | 镜像元数据 | `routes.py:459-467` |

## 4. `/os-keypairs` 与 `/os-aggregates` 接口组

| 方法 / 路径 | 功能 | Handler / 锚点 |
|---|---|---|
| `GET/POST/DELETE /os-keypairs*` | 密钥对管理 | `nova/api/openstack/compute/keypairs.py` (`routes.py:641-647`) |
| `GET/POST /os-aggregates*` | 主机聚合管理 | `nova/api/openstack/compute/aggregates.py` (`routes.py:480-491`) |

错误码与异常映射全表见 [`error-codes.md`](../error-codes.md)；其余 90+ 扩展路由按同一模式由各 extension controller 实现，详见 [`api-reference.md`](../api-reference.md) 的总表。
