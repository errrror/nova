---
kind: downstream-contract
scope: keystone
status: draft
origin: generated
source_paths: [nova/service_auth.py, nova/conf/service_token.py]
symbols: [get_auth_plugin, ServiceTokenAuthWrapper, get_auth_plugin]
upstream: [integrations/index.md, architecture/api-service.md]
downstream: []
---

# 下游出向接口契约：`keystone`

Keystone 提供身份认证与服务目录能力。本仓并不直接拼装 Keystone HTTP 请求，而是统一通过 `keystoneauth1` 的会话/认证插件间接调用；封装位于 `nova/service_auth.py:25 get_auth_plugin(context)`。本页如实记录本仓可见的认证插件组装边界，Keystone 服务端内部实现为仓外黑盒。

## 1. 封装定位与连接契约

| 契约项 | 精确值 / 规则 | 源码锚点（`路径:行号`） |
|---|---|---|
| 本仓业务封装文件 | `nova/service_auth.py` | `nova/service_auth.py:25` |
| 认证插件库 | `from keystoneauth1 import loading as ks_loading` | `nova/service_auth.py:14` |
| 服务令牌包装 | `service_token.ServiceTokenAuthWrapper` | `nova/service_auth.py:17` / `:35` |
| 服务用户开关 | `CONF.service_user.send_service_user_token` | `nova/service_auth.py:28` |
| 服务用户 group | `nova.conf.service_token.SERVICE_USER_GROUP` | `nova/service_auth.py:32` |
| 上下文认证源 | `context.get_auth_plugin()` | `nova/service_auth.py:26` |

---

## 2. 本仓上游调用方反查表（Who Calls This Wrapper）

| 本仓封装方法 | 上游调用模块与函数 | 所属业务流 / 接口 | 调用点锚点（`路径:行号`） |
|---|---|---|---|
| `get_auth_plugin` | `cinderclient()` 认证 | 卷操作 | `nova/volume/cinder.py:104` |
| `get_auth_plugin` | Glance client 构造 | 镜像操作 | `nova/image/glance.py` 的 session 认证 |
| `get_auth_plugin` | Neutron `_load_auth_plugin` | 网络操作 | `nova/network/neutronv2/api.py:66` |
| `get_auth_plugin` | Ironic `_get_auth_plugin` | 裸机操作 | `nova/virt/ironic/client_wrapper.py:61` |

---

## 3. 封装方法总清单

| 序号 | 封装函数签名 | 下游目标 | 读写类型 | 定义锚点（`路径:行号`） |
|---|---|---|---|---|
| 1 | `get_auth_plugin(context)` | 认证插件 | — | `nova/service_auth.py:25` |

---

## 4. 逐方法请求字典与响应解包契约（Full Dict Schemas）

### 4.1 `get_auth_plugin` → Keystone 认证插件（黑盒）

#### A. 发往下游的组装"字典表"（Auth Payload Dict）

本仓不直接构造 Keystone HTTP 字典，而是把认证参数交给 `keystoneauth1` 插件加载器；可识别的配置输入如下：

| 配置项 / 来源 | 类型 | 必填条件 | 值来源与转换逻辑 | 组装行号 |
|---|---|---|---|---|
| `user_auth` | auth plugin | 必填 | `context.get_auth_plugin()` 从请求上下文提取 | `nova/service_auth.py:26` |
| `service_auth` | auth plugin | `send_service_user_token=True` 时 | `ks_loading.load_auth_from_conf_options(CONF, SERVICE_USER_GROUP)` 懒加载单例 `_SERVICE_AUTH` | `nova/service_auth.py:28-33` |
| 包装结果 | `ServiceTokenAuthWrapper` | 启用服务令牌时 | `ServiceTokenAuthWrapper(user_auth=..., service_auth=...)` | `nova/service_auth.py:35-37` |

#### B. 下游返回字典与解包规则表（Response Unpacking）

Keystone 的 token/目录响应由 `keystoneauth1` 内部解包，本仓只消费认证后的 session 与 endpoint（如 Cinder `_SESSION.get_endpoint(auth, **service_parameters)`，`nova/volume/cinder.py:116`）。本仓不解析 Keystone 原始响应字段——`[外部黑盒：本仓未包含服务端实现]`。

#### C. 下游错误码拦截与翻译

认证失败由 `keystoneauth1` 抛出，经各 SDK client 的异常链上浮，本仓无独立翻译字典。

## 5. 共变耦合与修改清单（Co-Change Playbook）

- 修改服务用户认证：动 `nova/service_auth.py:25 get_auth_plugin` 必须同步 `nova/conf/service_token.py` 选项与 Cinder/Glance/Neutron/Ironic 四处调用点。
- **安全纪律**：服务用户凭据只从配置项加载（`SERVICE_USER_GROUP`），禁止写入日志或回显；密钥不明文落库（见 [`boundary.md`](../../operations/boundary.md)）。
