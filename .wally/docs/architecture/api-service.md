---
kind: component
scope: api-service
status: draft
origin: generated
source_paths: [setup.cfg, nova/api/openstack/wsgi_app.py, nova/api/openstack/compute/wsgi.py, nova/api/openstack/compute/routes.py, nova/api/openstack/compute/servers.py, nova/policy.py]
symbols: [init_application, APIRouterV21, _create_controller, ServersController.create, authorize]
upstream: [contracts/api-reference.md]
downstream: [conductor-engine.md, contracts/error-codes.md]
---

# `api-service`（API / RPC / 协议接入组件）

Nova 的接入层由 pbr 注册的多组服务组成：OpenStack Compute API、EC2 兼容 API、Metadata API、Placement API，全部基于 WSGI + `oslo` 中间件栈，路由通过 v2.1 microversion 分发，统一走策略鉴权。所有 HTTP 服务是无状态的，读写入口只经 compute/conductor API。

## 1. 请求处理洋葱链（Middleware & Dispatch Call Tree）

```text
Incoming HTTP Request
  ├─ [1. wsgi 装配] nova/api/openstack/wsgi_app.py:73 init_application(name) -> deploy.loadapp(paste 配置)
  ├─ [2. microversion] nova/api/openstack/compute/servers.py:460 is_supported(req, '2.19') -> 决定字段生效
  ├─ [3. auth/context] req.environ['nova.context'] (servers.py:455) -> 身份与租户注入
  ├─ [4. acl] nova/policy.py:126 authorize / servers.py:483 context.can(action, target) -> 越权 403
  ├─ [5. validation] nova/api/validation/ 参数校验 -> 非法 400
  ├─ [6. dispatch] nova/api/openstack/compute/routes.py:908 self.map.create_route -> controller.action
  └─ [7. error-map] nova/exception.py:35 ConvertedException -> 标准 HTTP 错误体
```

## 2. 路由分组与并发执行模型表

逐端点字段字典见 [`contracts/api-reference.md`](../contracts/api-reference.md)，本表聚焦架构执行特征。

| 路由组前缀 | 端点数 | 鉴权依赖 | 并发/IO 模型 | 关联动作 | 下游模块 |
|---|---|---|---|---|---|
| `/servers*` | 17 | `context.can` | 同步 WSGI，重动作异步 cast 到 conductor | 建/删/重建/迁移 | [`conductor-engine.md`](conductor-engine.md) |
| `/flavors*`、`/images*` | 12 | `context.can` | 同步读，对象层缓存 | 规格/镜像查询 | `nova/objects/` |
| `/os-*` 扩展组 | 90+ | 各扩展自身策略 | 同步 WSGI | 聚合/可用域/配额/安全组等 | conductor / DB |
| EC2 (`nova/api/ec2/`) | 兼容层 | EC2 签名 | 同步 WSGI | AWS EC2 兼容接口 | compute API |
| `/metadata`、`/placement` | WSGI 独立应用 | 各自策略 | `init_application` 装配 | 元数据/资源放置 | [`virt-and-data.md`](virt-and-data.md) |

路由总数：`nova/api/openstack/compute/routes.py:406 ROUTE_LIST` 定义 129 条 v2.1 路由，`APIRouterV21.__init__`（`routes.py:881`）逐条 `create_route`。

## 3. 核心源码文件与符号表

| 源码文件 | 核心符号（`行号`） | 职责边界 |
|---|---|---|
| `nova/api/openstack/compute/routes.py` | `_create_controller` (`:104`)、`APIRouterV21` (`:876`) | 路由表构造与控制器实例化 |
| `nova/api/openstack/compute/servers.py` | `ServersController` (`:66`)、`create` (`:453`)、`show` (`:437`)、`delete` (`:828`) | 实例主资源控制器 |
| `nova/api/openstack/wsgi_app.py` | `init_application` (`:73`) | WSGI 应用统一装配 |
| `nova/api/openstack/compute/wsgi.py` | `init_application` (`:19`) | compute API WSGI 工厂 |
| `nova/policy.py` | `init` (`:53`)、`authorize` (`:126`)、`check_is_admin` (`:172`) | 策略运行时 |
| `setup.cfg` | `console_scripts` (`:49`)、`wsgi_scripts` (`:71`) | 服务入口注册 |

## 4. 上下游调用关系

- **上游调用方**：OpenStack SDK / `python-novaclient` / Horizon / 租户脚本 / EC2 工具。
- **下游被调模块**：仓内 [`conductor-engine.md`](conductor-engine.md)（经 `ConductorAPI`）、`nova/objects/`；外部封装见 [`integrations/index.md`](../integrations/index.md)。

## 5. 共变耦合与新增接口清单（Agent Co-Change Playbook）

1. 在 `nova/api/openstack/compute/routes.py:406 ROUTE_LIST` 新增路由条目并绑定 controller/action。
2. 实现 controller 方法，补 microversion 判断（参照 `servers.py:460-474`）与 `context.can` 策略校验（`servers.py:483`）。
3. 在 `nova/policies/<group>.py` 注册新动作规则（`setup.cfg:44 list_rules` 会自动聚合并对外提供）。
4. 同步更新 [`contracts/api-reference.md`](../contracts/api-reference.md) 与 [`contracts/error-codes.md`](../contracts/error-codes.md)。
5. 补回归单测 `nova/tests/unit/api/openstack/compute/`（映射见 [`dev-and-test.md`](../operations/dev-and-test.md)）。
