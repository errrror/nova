---
kind: operations
scope: deployment-and-runtime
status: draft
origin: generated
source_paths: [setup.py, setup.cfg, tox.ini, etc/nova/api-paste.ini, etc/nova/nova-config-generator.conf, etc/nova/rootwrap.conf, bindep.txt, gate/post_test_hook.sh]
symbols: [setup, console_scripts, wsgi_scripts, init_application]
upstream: [INDEX.md, contracts/configuration.md]
downstream: [operations/runbook-and-observability.md]
---

# 部署产物、进程拓扑与持久化目录契约

Nova 是纯 Python 分发包（无 Docker 镜像构建资产）：`setup.py:27 setuptools.setup(pbr=True)` 经 `pbr` 打包，产物为 Python 包 + `setup.cfg:49-74` 注册的守护服务/WSGI 入口脚本。运行期拓扑由多个独立进程 + 外部 MySQL/RabbitMQ 组成；本仓不含容器编排文件，部署依赖外部 devstack。

## 1. 构建资产清单

| 构建文件（`路径`） | 构建产物 | 注入的关键目录与运行用户约束 |
|---|---|---|
| `setup.py:27` + `setup.cfg:25-28` | Python 包 `nova`（`packages = nova`） | pbr 从 `setup.cfg`/`requirements.txt` 生成元数据 |
| `setup.cfg:49-70 console_scripts` | `nova-api`/`nova-compute`/`nova-scheduler`/`nova-conductor`/`nova-manage` 等命令 | 各指向 `nova.cmd.<m>:main` |
| `setup.cfg:71-74 wsgi_scripts` | `nova-api-wsgi`/`nova-metadata-wsgi`/`nova-placement-api` | 各指向 `init_application` |
| `bindep.txt` | 系统级依赖清单（mysql/postgresql/libffi 等） | 由 CI/部署平台安装 |
| `etc/nova/api-paste.ini` | WSGI paste 配置（中间件栈） | `init_application(name)` 按段名加载 |
| `etc/nova/nova-config-generator.conf` | 配置样例生成输入 | `tox -e genconfig` (`tox.ini:92`) |
| `etc/nova/rootwrap.conf` | rootwrap 提权白名单配置 | `nova/cmd/compute.py:44 priv_context.init` |

## 2. 运行期进程拓扑与配置目录契约

```text
<部署环境>/
├── etc/nova/                          # 配置文件：nova.conf / api-paste.ini / rootwrap.conf
│   ├── api-paste.ini                  # WSGI 应用段 (compute/metadata/placement)
│   └── nova-config-generator.conf     # 配置样例生成
├── <state_path>/                      # CFG.state_path (nova/conf/base.py:26 附近)
│   ├── instances/                     # 实例磁盘文件（libvirt 默认）
│   └── images/                        # 镜像缓存 (image_cache_subdirectory_name, conf/compute.py:287)
├── MySQL (外部)                       # instances / compute_nodes 等表 (db/sqlalchemy/models.py)
└── RabbitMQ (外部)                    # oslo.messaging RPC transport (nova/rpc.py:231)
```

Agent 编写涉及文件读写的逻辑前，必须对齐以下边界：磁盘位置由 `state_path`/`instances_path` 等配置项决定（禁硬编码路径）；DB/MQ 地址由 `CONF.database`/`CONF.rabbit` 由外部注入。

## 3. 进程、子进程与外部网络边界

| 边界类型 | 方向与端口/协议 | 调用模块（`路径:行号`） | 安全与超时约束 |
|---|---|---|---|
| 入向监听 | HTTP（API/WSGI，端口由 paste 配置） | `nova/api/openstack/wsgi_app.py:73 init_application` | keystone 中间件鉴权 |
| RPC 消息总线 | AMQP（RabbitMQ） | `nova/rpc.py:231 create_transport` / `:175 get_client` | `oslo.messaging` 传输，上下文序列化 (`nova/rpc.py:122`) |
| 本地提权子进程 | `nova-rootwrap`（固定 argv） | `nova/cmd/compute.py:44 priv_context.init(root_helper=...)` | rootwrap 白名单 `etc/nova/rootwrap.conf` |
| hypervisor 调用 | libvirt socket / driver SDK | `nova/virt/driver.py:93 ComputeDriver` | 驱动隔离，禁 shell=True 拼接 |
| CI 部署钩子 | `gate/post_test_hook.sh` | `gate/post_test_hook.sh` | OpenStack infra job，仅 db archive |

**部署说明**：`README.rst:33-39` 明确部署指南指向外部 `https://docs.openstack.org/nova/`；仓库内 `devstack/` 仅含外部 tempest CI job 的测试选择脚本，`gate/` 为 infra hook，二者均非可执行的部署入口——`[外部黑盒：本仓未包含部署编排实现]`。

配置加载与脱敏规则见 [配置手册](../contracts/configuration.md)；外部黑盒范围见 [认知边界声明](boundary.md)。


## 4. 共变耦合与修改清单（Agent Co-Change Playbook）

- 新增服务入口：改 `setup.cfg:49 console_scripts` 或 `:71 wsgi_scripts` → 实现 `nova/cmd/<m>.py:main` 或 `init_application` → 在 `etc/nova/api-paste.ini` 增加 WSGI 段 → 更新 [系统技术架构](../overview/system-architecture.md) 的 Bootstrap Call Tree。
- 改配置注入：动 `nova/config.py:33` 必须同步 `nova/conf/` 选项组与 [配置手册](../contracts/configuration.md)。
- 改磁盘布局：涉及 `state_path`/`instances_path` 的读写须回读源码字面，禁止硬编码路径。
