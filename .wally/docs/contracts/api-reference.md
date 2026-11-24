---
kind: api-contract
scope: inbound-api
status: draft
origin: generated
source_paths: [setup.cfg, nova/api/openstack/compute/routes.py, nova/api/openstack/compute/servers.py, nova/policy.py, nova/api/openstack/wsgi_app.py]
symbols: [APIRouterV21, ROUTE_LIST, ServersController.create, authorize, init_application]
upstream: [INDEX.md]
downstream: [integrations/topology-and-mapping.md, contracts/error-codes.md]
---

# 入向接口契约全集（Inbound API / RPC / MCP / CLI Reference）

Nova 对外暴露四类入向接口：OpenStack Compute API（v2.1，129 条路由）、EC2 兼容 API、Metadata API、Placement API，以及 CLI/WSGI 入口。Compute API 通过 `nova/api/openstack/compute/routes.py:406 ROUTE_LIST` 声明式注册，`APIRouterV21`（`routes.py:876`）逐条 `create_route`。接口总数 `> 20`，本页保留公共协议约定 + 全量路由总表，逐接口字段字典拆至 [`api/compute-v21.md`](api/compute-v21.md)。

## 1. 公共协议、鉴权与响应包络规范

| 维度 | 精确实现规则 | 源码锚点（`路径:行号`） |
|---|---|---|
| 应用装配 | `init_application(name)` → `deploy.loadapp`，name 取 `compute`/`metadata`/`placement` | `nova/api/openstack/wsgi_app.py:73` / `setup.cfg:71-74` |
| 认证凭据提取 | `req.environ['nova.context']`，由 keystone 中间件注入 | `nova/api/openstack/compute/servers.py:455` |
| 租户/资源归属校验 | `context.can(action, target)`，target 含 `project_id`/`user_id`/`availability_zone` | `nova/api/openstack/compute/servers.py:479-483` / `nova/policy.py:126` |
| microversion 协商 | `api_version_request.is_supported(req, min_version='2.19')` 决定字段生效 | `nova/api/openstack/compute/servers.py:460` / `:473` |
| 标准成功/错误包络 | JSON 资源对象；异常经 `nova/exception.py:35 ConvertedException` 映射 HTTP 状态 | `nova/exception.py:35` |
| 响应构造 | `wsgi.Controller` 序列化领域对象为 JSON | `nova/api/openstack/compute/servers.py:66` |

---

## 2. 全量入向接口路由总表（Master Inbound Inventory）

> 完整 129 条 v2.1 路由定义于 `nova/api/openstack/compute/routes.py:406-873 ROUTE_LIST`，`APIRouterV21.__init__`（`routes.py:881`）逐条绑定 `controller`/`action`。下表按资源分组归档全部路由前缀（含 EC2/Metadata/Placement/CLI 独立入口）。

| 分组 | 协议 / 方法 | 精确路径 / Action / 命令 | 鉴权级别 | 执行模式 | Handler 符号与源码锚点 | 说明 |
|---|---|---|---|---|---|---|
| 版本/扩展 | GET | `/`、`/versions/{id}`、`/extensions`、`/extensions/{id}` | 低 | 同步 | `version_controller`/`extensions_controller` (`routes.py:410-421`) | 版本发现 |
| 规格 Flavors | GET/POST/DELETE | `/flavors`、`/flavors/detail`、`/flavors/{id}`、`/flavors/{id}/action`、`/flavors/{flavor_id}/os-extra_specs*`、`/os-flavor-access` | `context.can` | 同步 | `flavor_controller` 等 (`routes.py:423-448`) | 规格管理 |
| 镜像 Images | GET/POST/DELETE | `/images`、`/images/detail`、`/images/{id}`、`/images/{image_id}/metadata*` (`routes.py:449-468`) | `context.can` | 同步 | `images.ImagesController` | 镜像查询/元数据 |
| 配额/限制 | GET/PUT | `/limits`、`/os-quota-class-sets/{id}`、`/os-quota-sets/{id}*` (`routes.py:469`、`670-680`) | `context.can` | 同步 | quota controller | 配额管理 |
| Agents/Aggregates | CRUD | `/os-agents*`、`/os-aggregates*` (`routes.py:472-491`) | `context.can` | 同步 | agents/aggregates controller | 代理/聚合 |
| Cells | CRUD | `/os-cells*`（capacities/detail/info/sync_instances）(`routes.py:515-537`) | admin | 同步 | cells controller | Cells v1 管理 |
| 安全组 | CRUD | `/os-security-groups*`、`/os-security-group-rules*`、`/os-security-group-default-rules*` (`routes.py:681-703`) | `context.can` | 同步 | security_group controller | 安全组 |
| 服务器 Servers | GET/POST/DELETE | `/servers`、`/servers/detail`、`/servers/{id}`、`/servers/{id}/action` (`routes.py:775-789`) | `context.can` | 同步入口+异步 cast | `ServersController.create` (`servers.py:453`) | 核心实例资源 |
| 服务器子资源 | CRUD | `/servers/{server_id}/metadata*`、`/os-volume_attachments*`、`/os-interface*`、`/tags*`、`/ips*`、`/remote-consoles` 等 (`routes.py:790-871`) | `context.can` | 同步 | 各 extension controller | 挂在实例下的子资源 |
| 网络（Nova-network 兼容） | CRUD | `/os-networks*`、`/os-floating-ips*`、`/os-fixed-ips*`、`/os-security-groups*` (`routes.py:555-666`) | `context.can` | 同步 | network controller | 旧网络 API 兼容 |
| 宿主/虚拟化 | GET | `/os-hosts*`、`/os-hypervisors*`、`/os-services*` (`routes.py:598-720`) | admin | 同步 | hosts/hypervisors controller | 运维查询 |
| 其他扩展 | 各异 | `/os-keypairs*`、`/os-server-groups*`、`/os-migrations*`、`/os-snapshots*`、`/os-volumes*` 等 (`routes.py:492-871`) | 各异 | 同步 | 各 extension controller | 扩展 API |
| EC2 兼容 | SOAP/Query | `nova/api/ec2/` (`setup.cfg` ec2 入口) | EC2 签名 | 同步 | EC2 API 路由 | AWS EC2 兼容 |
| Metadata | HTTP GET | `nova/api/metadata/wsgi.py:19 init_application` | 元数据可信 | 同步 | metadata controller | 实例元数据 |
| Placement | REST | `nova/api/openstack/placement/wsgi.py:50 init_application` | `context.can` | 同步 | placement controller | 资源放置/清单 |
| CLI | 命令行 | `nova-* = nova.cmd.<m>:main` (`setup.cfg:49-70`) | OS 权限 | 同步 | 各 `main` | 守护服务/运维命令 |

> 逐接口字段字典（入参/出参 Schema）见 [`api/compute-v21.md`](api/compute-v21.md)；错误分支见 [`error-codes.md`](error-codes.md)。

## 3. 逐接口入参/出参精确契约（Endpoint Schemas）

以核心 `POST /servers` 为例（完整字段字典见分组子页）：

- **入口与编排链**：`nova/api/openstack/compute/servers.py:453 ServersController.create` → `nova/compute/api.py:1584 API.create`（关联流程 [`wf-instance-boot.md`](../business/wf-instance-boot.md)）。
- **入参字典**：`body['server']`（`servers.py:456`），关键字段 `name`（`:458`）、`imageRef`/`block_device_mapping`/`networks`、`description`（≥2.19，`:461`）、`tags`（≥2.52，`:474`）。
- **出参结构**：`HTTP 200/202` 返回实例 JSON 对象（由 `wsgi.Controller` 序列化）。
- **错误分支**：`400`（参数非法，`servers.py:491-492`）、`403`（策略拒绝，`servers.py:483`）、配额超限异常。


## 4. 共变耦合与新增接口清单（Agent Co-Change Playbook）

1. 在 `nova/api/openstack/compute/routes.py:406 ROUTE_LIST` 增加路由条目并绑定 `controller`/`action`。
2. 实现 controller 方法并补 microversion 判断（参照 `servers.py:460-474`）与 `context.can` 策略 (`servers.py:483`)。
3. 在 `nova/policies/` 注册动作规则（`setup.cfg:44 list_rules` 自动聚合）。
4. 同步更新 [`error-codes.md`](error-codes.md) 与 [`api/compute-v21.md`](api/compute-v21.md)。
5. 补回归单测 `nova/tests/unit/api/openstack/compute/`（映射见 [`dev-and-test.md`](../operations/dev-and-test.md)）。
