# nova · Agent 知识库总路由表（INDEX）

> **Agent 读取规程（必读）**：
> 1. **禁止一次性全量读取 `.wally/docs/`**。先查下方「任务意图路由表」或「源码路径反向索引」，只打开命中的 1–3 篇目标文档（可用 `Read(limit=15)` 先看顶部 YAML 头确认 `source_paths`、`symbols` 与 `status`）。
> 2. **弱命中与草稿核验纪律**：标记 `status: draft` 的文档为源码提取草稿；从文档拿到 `路径:行号`（`符号名`）、上下游字典结构与「共变耦合清单」后，执行修改前必须调用 `Read(path, offset, limit)` 复核源码字面实现（近邻词线索不等于原词覆盖）。
> 3. **人工精修保护**：标记 `origin: human` 或 `status: verified` 的页面为人工确认权威结论，后续重跑知识库严禁覆盖。基准提交：`chore/wally-init-20261124-c11` @ `ffcc707aa555e7dc76fa14b9353dbb3c8573fea1`。

Nova 是 OpenStack 的云计算结构控制器（Python 2.7/3.5，多进程守护服务），核心是围绕有状态 `Instance` 的生命周期编排：无状态 API/conductor 经 RPC 驱动每台宿主机的 `nova-compute` 调用 hypervisor 落机。核心入向契约为 129 条 v2.1 HTTP 路由，出向经 Glance/Cinder/Neutron/Ironic/Keystone/MySQL/RabbitMQ 封装层完成。

---

## 1. 任务意图最短路由表（Agent Intent Router）

| Agent 当前待办任务类型 | 按序必读文档（1 → 2 → 3） |
|---|---|
| **上游加字段透传/组装给下游**（高频编排需求） | [参数组装与字段映射](integrations/topology-and-mapping.md) → [Glance 下游契约](integrations/downstream/glance.md) → [入向接口参考](contracts/api-reference.md) |
| **新增/修改本仓对外接口或命令** | [入向接口参考](contracts/api-reference.md) → [API 接入组件](architecture/api-service.md) → [错误码字典](contracts/error-codes.md) |
| **对接新下游接口 / 修改下游返回解析** | [上下游集成总览](integrations/index.md) → [Cinder 下游契约](integrations/downstream/cinder.md) → [错误码字典](contracts/error-codes.md) |
| **修改业务校验规则 / 状态流转逻辑** | [业务能力总表](business/index.md) → [建机流程](business/wf-instance-boot.md) → [核心数据模型](business/domain-models/index.md) |
| **新增/修改后台异步/周期任务** | [Compute Worker](architecture/compute-worker.md) → [配置与开关手册](contracts/configuration.md) → [排障 Runbook](operations/runbook-and-observability.md) |
| **定位报错 / 异常码 / 降级原因** | [错误码字典](contracts/error-codes.md) → [主干调用链全景](overview/callchain-panorama.md) → [排障 Runbook](operations/runbook-and-observability.md) |
| **跨模块重构 / 评估联动修改与跑单测** | [模块依赖矩阵](architecture/module-dep-matrix.md) → [高危雷区与历史陷阱](operations/pitfalls-and-adr.md) → [构建与单测映射](operations/dev-and-test.md) |

---

## 2. 源码目录/核心文件 → 文档反向索引（Source-to-Doc Reverse Index）

> 当用户直接指定修改某个源码目录或文件时，由此表 O(1) 反查对应知识文档：

| 仓库源码路径（前缀或关键文件） | 架构模型 / 角色 | 首选关联文档 | 关联上下游/业务文档 |
|---|---|---|---|
| `nova/api/`、`nova/api/openstack/compute/routes.py` | `API Service` | [`architecture/api-service.md`](architecture/api-service.md) | [`contracts/api-reference.md`](contracts/api-reference.md) |
| `nova/conductor/` | `Core Engine` | [`architecture/conductor-engine.md`](architecture/conductor-engine.md) | [`business/wf-instance-boot.md`](business/wf-instance-boot.md) |
| `nova/scheduler/` | `Core Engine` | [`architecture/scheduler-engine.md`](architecture/scheduler-engine.md) | [`business/wf-scheduling.md`](business/wf-scheduling.md) |
| `nova/compute/` | `Async/Cron Worker` | [`architecture/compute-worker.md`](architecture/compute-worker.md) | [`business/wf-instance-actions.md`](business/wf-instance-actions.md) |
| `nova/virt/`、`nova/objects/`、`nova/db/`、`nova/rpc.py` | `Data & Adapter` | [`architecture/virt-and-data.md`](architecture/virt-and-data.md) | [`business/domain-models/index.md`](business/domain-models/index.md) |
| `nova/cmd/` | `UI/CLI` | [`architecture/cli-and-cmd.md`](architecture/cli-and-cmd.md) | [`overview/system-architecture.md`](overview/system-architecture.md) |
| `nova/image/glance.py` | `Downstream Wrapper` | [`integrations/downstream/glance.md`](integrations/downstream/glance.md) | [`integrations/topology-and-mapping.md`](integrations/topology-and-mapping.md) |
| `nova/volume/cinder.py` | `Downstream Wrapper` | [`integrations/downstream/cinder.md`](integrations/downstream/cinder.md) | [`contracts/error-codes.md`](contracts/error-codes.md) |
| `nova/network/neutronv2/` | `Downstream Wrapper` | [`integrations/downstream/neutron.md`](integrations/downstream/neutron.md) | [`integrations/index.md`](integrations/index.md) |
| `nova/exception.py`、`nova/quota.py`、`nova/conf/` | 横切基础/配置 | [`contracts/error-codes.md`](contracts/error-codes.md) | [`contracts/configuration.md`](contracts/configuration.md) |

---

## 3. 模块技术能力清单（Component Registry）

| 组件标识 | 框架模型（Archetype） | 核心源码路径 | 核心入口符号（`路径:行号`） | 上游调用方 | 下游依赖 | 文档 |
|---|---|---|---|---|---|---|
| `api-service` | `API Service` | `nova/api/` | `APIRouterV21` (`nova/api/openstack/compute/routes.py:876`) | 租户/SDK | conductor | [查看](architecture/api-service.md) |
| `conductor-engine` | `Core Engine` | `nova/conductor/` | `ConductorManager` (`nova/conductor/manager.py:87`) | api-service | scheduler/compute/DB | [查看](architecture/conductor-engine.md) |
| `scheduler-engine` | `Core Engine` | `nova/scheduler/` | `FilterScheduler._schedule` (`nova/scheduler/filter_scheduler.py:111`) | conductor | host state | [查看](architecture/scheduler-engine.md) |
| `compute-worker` | `Async/Cron Worker` | `nova/compute/` | `build_and_run_instance` (`nova/compute/manager.py:1702`) | conductor | virt/DB | [查看](architecture/compute-worker.md) |
| `virt-and-data` | `Data & Adapter` | `nova/virt/`、`nova/objects/`、`nova/db/` | `ComputeDriver` (`nova/virt/driver.py:93`) | compute-worker | hypervisor/DB/MQ | [查看](architecture/virt-and-data.md) |
| `cli-and-cmd` | `UI/CLI` | `nova/cmd/` | `main` (`nova/cmd/manage.py:1672`) | 运维 | 各 Manager | [查看](architecture/cli-and-cmd.md) |

---

## 4. 业务流程与下游依赖速查

- **全景认知**：[系统技术架构](overview/system-architecture.md) · [业务架构全景](overview/business-architecture.md) · [主干调用链全景](overview/callchain-panorama.md) · [领域术语与符号映射](overview/glossary.md)
- **上下游与契约**：[上下游集成总览](integrations/index.md) · [参数组装映射](integrations/topology-and-mapping.md) · [入向接口参考](contracts/api-reference.md) · [错误码字典](contracts/error-codes.md) · [配置手册](contracts/configuration.md)
- **业务与数据**：[业务流程总表](business/index.md) · [核心领域与数据模型](business/domain-models/index.md)
- **验证、雷区与边界**：[构建与单测映射](operations/dev-and-test.md) · [部署与运行时](operations/deployment-and-runtime.md) · [排障 Runbook](operations/runbook-and-observability.md) · [高危雷区与历史陷阱](operations/pitfalls-and-adr.md) · [认知边界声明](operations/boundary.md)

---

## 5. 外部 SOP / 权威文档引用页（非 codewiki 管理页）

以下为 SOP 2.0 专用/现有权威资料，仅作链接引用，不套用 codewiki 模板、不计入 `.wiki-meta.json` 的 `pageOrder`/`pageCount`：

- [apis/](apis/index.md) · [sqls/](sqls/README.md) · [unittest/](unittest/unittest.md) · [integration_test/](integration_test/integration_test.md) · [devops/](devops/env.md)（含部署指南 [test-env-deploy.md](devops/test-env-deploy.md)）
