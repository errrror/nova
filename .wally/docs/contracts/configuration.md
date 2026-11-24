---
kind: config-dict
scope: configuration
status: draft
origin: generated
source_paths: [nova/config.py, nova/conf/opts.py, nova/conf/compute.py, nova/conf/glance.py, nova/conf/cinder.py, nova/conf/scheduler.py, nova/conf/base.py, nova/__init__.py, nova/cmd/dhcpbridge.py, nova/cmd/policy_check.py]
symbols: [parse_args, list_opts, compute_opts, glance_opts, cinder_opts, scheduler_opts]
upstream: [INDEX.md, overview/system-architecture.md]
downstream: [operations/deployment-and-runtime.md]
---

# 配置项、环境变量与动态开关全集

Nova 的配置基于 `oslo.config`：所有选项按 group 定义在 `nova/conf/*.py`（共 51 个文件），由 `nova/conf/opts.py:43 list_opts` 聚合，pbr 入口 `nova.conf = nova.conf.opts:list_opts`（`setup.cfg:30`）和 `nova.conf.opts.defaults`（`setup.cfg:34`）对外暴露。启动时 `nova/config.py:33 parse_args` 统一加载。

## 1. 配置覆盖优先级链

`命令行显式参数 (argv)` > `配置文件 (oslo.config.ini，由 default_config_files 指定)` > `进程环境变量`（少量直接 `os.getenv`，见第 2 节）> `代码硬编码默认值`（各 `cfg.*Opt(default=...)`）。解析入口：`nova/config.py:33-51 parse_args`。

## 2. 进程环境变量全集（100% 扫描 `getenv` / `environ`）

源码中直接读取的环境变量（非 oslo.config 管理），全部如下：

| 环境变量名 | 类型 | 代码默认值 | 必填 | 控制行为与边界影响 | 读取锚点（`路径:行号`） |
|---|---|---|---|---|---|
| `EVENTLET_NO_GREENDNS` | `str` | 硬编码 `'yes'` | 否 | 禁用 eventlet green DNS，启动时设置 | `nova/__init__.py:28` |
| `CONFIG_FILE` | `str`（JSON） | 无 | dhcpbridge 必填 | 加载默认配置文件列表 | `nova/cmd/dhcpbridge.py:104` |
| `NETWORK_ID` | `str` | 无 | 否 | dhcpbridge 网络 ID | `nova/cmd/dhcpbridge.py:130` |
| `OS_ROLES` | `str` | 无 | 否 | policy-check 角色默认值 | `nova/cmd/policy_check.py:43` |
| `OS_USER_ID` | `str` | 无 | 否 | policy-check 用户 ID 默认值 | `nova/cmd/policy_check.py:48` |
| `OS_TENANT_ID` | `str` | 无 | 否 | policy-check 租户 ID 默认值 | `nova/cmd/policy_check.py:53` |
| `OS_TEST_TIMEOUT` | `int` | `0` | 否 | 测试超时（测试环境） | `nova/test.py:217` |

> 其余运行参数均通过 oslo.config 选项（INI 配置）管理，而非直接环境变量。

## 3. 关键 oslo.config 选项组与默认值

| 配置域（模块） | 配置键（Key） | 类型 | 默认值 | 生效时机与副作用 | 读写校验锚点（`路径:行号`） |
|---|---|---|---|---|---|
| `[DEFAULT]`（`nova/conf/base.py`） | `host` / `state_path` | `StrOpt` | 平台相关 | 主机身份与状态目录 | `nova/conf/base.py:26` 等 |
| `[compute]`（`nova/conf/compute.py`） | `compute_driver` | `StrOpt` | 由 virt 决定 | 选择 hypervisor 驱动 | `nova/conf/compute.py:33` |
| `[compute]` | `allow_resize_to_same_host` | `BoolOpt` | — | 允许同宿主 resize | `nova/conf/compute.py:46` |
| `[compute]` | `vif_plugging_is_fatal` | `BoolOpt` | — | VIF 挂载失败是否致命 | `nova/conf/compute.py:157` |
| `[compute]` | `vif_plugging_timeout` | `IntOpt` | — | VIF 挂载超时 | `nova/conf/compute.py:178` |
| `[glance]`（`nova/conf/glance.py`） | `api_servers` | `ListOpt` | 空（需配置） | Glance 端点列表 | `nova/conf/glance.py:28` |
| `[glance]` | `num_retries` | `IntOpt` | `0` | 镜像上传/下载重试次数 | `nova/conf/glance.py:39` |
| `[glance]` | `verify_glance_signatures` | `BoolOpt` | `False` | 镜像签名校验开关 | `nova/conf/glance.py:63` |
| `[cinder]`（`nova/conf/cinder.py`） | `catalog_info` | `StrOpt` | `'volumev3:cinderv3:publicURL'` | Cinder 服务目录匹配 | `nova/conf/cinder.py:25` |
| `[cinder]` | `http_retries` | `IntOpt` | `3` | Cinder HTTP 重试 | `nova/conf/cinder.py:69` |
| `[cinder]` | `cross_az_attach` | `BoolOpt` | `True` | 跨可用域挂载 | `nova/conf/cinder.py:82` |
| `[scheduler]`（`nova/conf/scheduler.py`） | `driver`（deprecated `scheduler_driver`） | `StrOpt` | filter_scheduler | 调度驱动选择 | `nova/conf/scheduler.py:35-37` |
| `[scheduler]` | `host_manager` | `StrOpt` | host_manager | 宿主状态管理实现 | `nova/conf/scheduler.py:23` |

## 4. 下游服务端点与凭据安全规则

| 下游目标 | 地址/模型配置来源 | 凭据存储与脱敏规则 | 未配置时的默认回退行为 | 源码锚点 |
|---|---|---|---|---|
| [Glance](../integrations/downstream/glance.md) | `CONF.glance.api_servers` | 会话由 keystoneauth 管理 | 无端点则调用失败 | `nova/conf/glance.py:28` |
| [Cinder](../integrations/downstream/cinder.md) | `catalog_info` / `endpoint_template` | 服务用户凭据从 group 加载，不明文回显 | 无端点则发现失败 | `nova/conf/cinder.py:25`/`:43` |
| [Neutron](../integrations/downstream/neutron.md) | `CONF.neutron.url` / `region_name` | keystoneauth 会话 | 走服务目录发现 | `nova/conf/neutron.py` |
| [Keystone](../integrations/downstream/keystone.md) | `SERVICE_USER_GROUP` | `mask_passwd_in_url` 脱敏（`nova/cmd/manage.py:127`），不进日志 | 使用请求上下文用户认证 | `nova/service_auth.py:28-33` |
| [MySQL](../integrations/downstream/mysql.md) | `CONF.database` 连接串 | 口令脱敏 | 无本地 Fixture 降级 | `nova/config.py:58` |

配置样例生成见 [`dev-and-test.md`](../operations/dev-and-test.md) 的 `tox -e genconfig`；运行期目录布局见 [`deployment-and-runtime.md`](../operations/deployment-and-runtime.md)。
