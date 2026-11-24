---
kind: component
scope: cli-and-cmd
status: draft
origin: generated
source_paths: [setup.cfg, nova/cmd/api.py, nova/cmd/compute.py, nova/cmd/scheduler.py, nova/cmd/conductor.py, nova/cmd/manage.py, nova/cmd/status.py]
symbols: [main, _db_error, validate_network_plugin]
upstream: [INDEX.md]
downstream: [conductor-engine.md, compute-worker.md]
---

# `cli-and-cmd`（前端视图 / CLI 交互组件）

Nova 的「UI」是命令行与守护进程入口层：所有服务通过 `setup.cfg:49` 的 `console_scripts` 注册 `nova.cmd.<module>:main`，WSGI 应用通过 `wsgi_scripts`（`setup.cfg:71`）暴露 `init_application`。`nova-manage` 是运维命令树，`nova-status` 做部署健康检查。

## 1. 路由视图 / 子命令分发表

| CLI 命令 / 服务 | 挂载容器或入口函数 | 源码锚点（`路径:行号`） | 核心交互闭环 | 历史兼容/未挂载备注 |
|---|---|---|---|---|
| `nova-api` / `nova-api-os-compute` | `main` | `nova/cmd/api.py:39` | 启动 API WSGI 服务 | 组合服务，兼容旧部署 |
| `nova-compute` | `main` | `nova/cmd/compute.py:42` | 启动计算 Worker + DB guard | 核心执行进程 |
| `nova-scheduler` | `main` | `nova/cmd/scheduler.py:35` | 启动调度服务 | — |
| `nova-conductor` | `main` | `nova/cmd/conductor.py:33` | 启动编排/DB 代理 | 生产必配 |
| `nova-manage` | `main` | `nova/cmd/manage.py:1672` | DB 迁移/细胞/配额等运维子命令 | 子命令由 decorators 注册 |
| `nova-status` | `main` | `nova/cmd/status.py` | 升级前部署健康检查 | — |
| `nova-placement-api` / `nova-api-wsgi` / `nova-metadata-wsgi` | `init_application` | `setup.cfg:71-74` | WSGI 工厂装配 | 由 paste 配置驱动 |

## 2. 状态容器与动作委托机制

- **命令解析底座**：所有 `main` 共用 `config.parse_args(sys.argv)`（如 `nova/cmd/compute.py:43`）加载配置，再 `logging.setup`、`objects.register_all()`。
- **错误码转换**：`nova/cmd/manage.py:217 _db_error` 把 DB 异常包装为 CLI 可读输出；`nova/cmd/manage.py:438 validate_network_plugin` 为子命令参数校验装饰器。
- **安全脱敏**：`nova/cmd/manage.py:127 mask_passwd_in_url` 在输出中遮蔽连接串口令，符合「密钥不明文回显」约束。

## 3. 动作 → 后端 API 绑定矩阵

| CLI 子命令 / 服务入口 | 处理函数（`路径:行号`） | 调用的后端接口 | 异步反馈机制 |
|---|---|---|---|
| `nova-compute` 启动 | `nova/cmd/compute.py:42` | `compute_rpcapi.RPC_TOPIC` 上注册 RPC server | `service.serve`/`wait` 长驻 |
| `nova-manage db` | `nova/cmd/manage.py:1672` 分发的子命令 | `nova/db/sqlalchemy/api.py` | 同步执行 + stdout 结果 |
| `nova-status upgrade check` | `nova/cmd/status.py` | 各服务版本端点 | 同步健康报告 |

## 4. 共变耦合与修改清单（Agent Co-Change Playbook）

1. 新增守护服务：在 `setup.cfg:49 console_scripts` 注册 `nova-xxx = nova.cmd.xxx:main`，并在 `nova/cmd/xxx.py` 实现 `main` 复用标准骨架。
2. 新增运维子命令：在 `nova/cmd/manage.py` 用装饰器注册，注意敏感参数走 `mask_passwd_in_url`（`:127`）。
3. 改服务启动骨架（`config.parse_args` / `block_db_access` / `indirection_api`）必须同步核对 [`system-architecture.md`](../overview/system-architecture.md) 的 Bootstrap Call Tree 与所有 `nova/cmd/*.py`。
