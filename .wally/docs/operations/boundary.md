---
kind: operations
scope: boundary
status: draft
origin: generated
source_paths: [README.rst, setup.cfg, tox.ini, etc/nova/api-paste.ini, .wally/config.json]
symbols: []
upstream: [INDEX.md]
downstream: []
---

# 认知边界与外部黑盒声明（Agent Anti-Hallucination Boundary）

本页界定本套 `.wally/docs/` 已核验的源码快照边界、仓库外不可见的黑盒服务、静态分析局限与生成物可信度，防止 Agent 脑补仓外实现或把弱命中当字面证据。

## 1. 核验基准快照与生成物状态

- **Git 分支与提交**：`chore/wally-init-20261124-c11` @ `ffcc707aa555e7dc76fa14b9353dbb3c8573fea1`
- **生成模式与覆盖目录**：`full`；已完整扫描：全部顶层与二级源码目录（`nova/` 29 个二级目录及顶层模块）、构建与 CI 配置（`setup.cfg`/`tox.ini`/`requirements.txt`）、外部文档目录映射见 [组件总表](../architecture/index.md) Tier 3。
- **生成物可信度声明**：除显式标为 `origin: human` / `status: verified` 的人工精修页外，其余自动生成页均为 `status: draft`；Agent 改动核心逻辑前必须按页内 `path:行号` 回读源码字面核验。

## 2. 仓库外黑盒系统清单（Out-of-Repo Black Boxes）

以下目标仅在本仓库内存在出向调用封装或 CLI 调用，其**服务端内部实现不在本仓库内**（出向契约已按本仓代码记录于 [`integrations/`](../integrations/index.md)，远端内部逻辑严禁猜测）：

| 外部黑盒目标 | 本仓边界文件（`路径:行号`） | 本仓已核实的契约范围 | 不可见的远端黑盒范围 |
|---|---|---|---|
| Glance（镜像） | `nova/image/glance.py:126` | 请求字典键、重试、返回解包键 | 镜像后端存储、真实配额 |
| Cinder（卷） | `nova/volume/cinder.py:82` | 卷 attach/create 字典、版本协商 | 卷后端驱动 |
| Neutron（网络） | `nova/network/neutronv2/api.py:122` | 端口字典、安全组 ID 解析 | SDN 后端实现 |
| Ironic（裸机） | `nova/virt/ironic/client_wrapper.py:36` | JSON Patch 构造、动态方法分发 | 裸机电源/部署状态机 |
| Keystone（认证） | `nova/service_auth.py:25` | 认证插件组装、服务令牌包装 | token/目录响应内部 |
| MySQL（持久化） | `nova/config.py:58` | ORM 表结构、参数化 SQL | DB 集群拓扑 |
| RabbitMQ（RPC） | `nova/rpc.py:231` | cast/call、上下文序列化 | 消息中间件内部 |
| hypervisor（libvirt/Hyper-V/VMware/XenAPI/PowerVM） | `nova/virt/driver.py:93` | 驱动接口、spawn/destroy 契约 | hypervisor 内部实现 |
| OpenStack 部署/文档 | `README.rst:33-39` | 指向外部 `docs.openstack.org` | 部署编排（devstack 外部） |

## 3. 动态分发与运行期注入边界

| 动态机制位置（`路径:行号`） | 机制说明 | Agent 注意事项 |
|---|---|---|
| `setup.cfg:80-88` | stevedore 入口动态加载 host_manager / scheduler.driver / virt driver | 静态图无法穷举所有实现，改动接口须全局搜索所有实现 |
| `nova/api/openstack/wsgi_app.py:73` | 运行期按 `name` 加载 paste 配置段（`etc/nova/api-paste.ini`） | 中间件栈由配置决定，非代码硬编码 |
| `nova/cmd/dhcpbridge.py:104` | 从 `CONFIG_FILE` 环境变量读取 JSON 配置 | 宿主机文件内容不在 Git 仓内，测试时用临时文件模拟 |
| `nova/virt/ironic/client_wrapper.py:48` | `import_module('ironicclient')` 运行时动态导入 | 可选依赖，静态分析无法枚举其方法 |

## 4. 共用 SOP 文档边界（外部引用页）

`.wally/docs/` 中以下目录为 SOP 2.0 专用/外部权威页，**仅作链接引用，未套用 codewiki 模板、不计入 `pageOrder`/`pageCount`**（排除理由：非生成型知识页，属于任务流程与既有权威资料）：

- `apis/`（API/SOP 规格模板）、`sqls/`（SQL 权威说明）、`unittest/`（单测规范）、`integration_test/`（集成测试规范）、`devops/`（环境/部署权威文档，含 config.json 绑定的 `test-env-deploy.md`）。

这些页中可能存在模板占位符（如 `<actual API>`），属于 SOP 模板待办，非 codewiki 生成缺陷；G4 占位符门禁仅对 codewiki 管理页生效。

关键 ADR 与雷区见 [高危雷区与历史陷阱](pitfalls-and-adr.md)，部署缺口见 `.wally/config.json` 的 `readiness: pending` 项。
