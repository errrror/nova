---
kind: error-dict
scope: error-codes
status: draft
origin: generated
source_paths: [nova/exception.py, nova/api/openstack/compute/servers.py, nova/volume/cinder.py, nova/image/glance.py, nova/policy.py]
symbols: [NovaException, ConvertedException, InstanceNotFound, NoValidHost, BuildAbortException, authorize]
upstream: [contracts/api-reference.md, integrations/index.md]
downstream: [operations/runbook-and-observability.md]
---

# 错误码、异常传播与降级标识字典

Nova 全仓异常统一继承 `NovaException`（`nova/exception.py:58`，共 2182 行定义），Web 层经 `ConvertedException`（`nova/exception.py:35 webob.exc.WSGIHTTPException`）映射为 HTTP 状态。本页只记录源码真实存在的异常类型与字面量，严禁虚构编号。

## 1. 异常捕获与协议状态映射规则

| 边界位置（`路径:行号`） | 捕获的内部异常类型 | 映射后的对外状态码 / 错误结构 | 是否阻断写盘或重试 |
|---|---|---|---|
| `nova/api/openstack/compute/servers.py:491-492` | `exception.InvalidInput` | `HTTP 400`（`exc.HTTPBadRequest`） | 阻断写入 |
| `nova/api/openstack/compute/servers.py:483` | 策略拒绝 | `HTTP 403` | 阻断访问 |
| `nova/policy.py:126 authorize` | `Forbidden`（`nova/exception.py:155`） | `HTTP 403` | 阻断访问 |
| `nova/exception.py:35 ConvertedException` | 通用业务异常 | `code`/`title`/`explanation` → 状态行 | 由具体异常决定 |

## 2. 对外接口与领域层错误全表

| 错误码 / 异常类型 / 关键错误前缀 | 状态码 | 产出函数与精确源码行（`路径:行号`） | 精确触发条件 | 调用方或排障处置动作 |
|---|---|---|---|---|
| `NovaException` | 基类 | `nova/exception.py:58` | 所有业务异常根 | — |
| `ConvertedException` | 动态 `code` | `nova/exception.py:35` | Web 错误转换 | 读 `title`/`explanation` |
| `Forbidden` | 403 | `nova/exception.py:155` | 策略拒绝 | 检查策略规则 |
| `InvalidInput` | 400 | `nova/exception.py:295` | 参数非法（如 AZ 解析失败 `servers.py:491`） | 修正请求参数 |
| `InstanceNotFound` | 404 | `nova/exception.py:1452`（继承 `NotFound` `:578`） | 实例 UUID 不存在 | 核对实例 ID |
| `ImageNotFound` | 404 | `nova/exception.py:651` | 镜像不存在 | 核对 imageRef |
| `FlavorNotFound` | 404 | `nova/exception.py:1165` | 规格不存在 | 核对 flavorRef |
| `NoValidHost` | 500/编排失败 | `nova/exception.py:1362` | 调度无可用 host | 检查容量/filter |
| `ComputeResourcesUnavailable` | 服务不可用 | `nova/exception.py:460`（继承 `ServiceUnavailable` `:452`） | claim 失败 | 触发重调度 |
| `BuildAbortException` | 建机失败 | `nova/exception.py:1591` | 落机中止 | 查 compute 日志 |
| `RescheduledException` | 重调度 | `nova/exception.py:1595` | claim 失败后（`manager.py:1965`） | 自动换 host 重试 |
| `DBDuplicateEntry` | 冲突 | DB 层 | 唯一约束（如 `instances.uuid` `models.py:224`） | 检查重复请求 |

## 3. 下游错误码 → 本仓错误翻译矩阵（Downstream Error Translation）

| 下游系统 | 下游原始错误码 / HTTP 状态 | 本仓拦截位置（`路径:行号`） | 翻译后的本仓错误码 / 降级返回值 |
|---|---|---|---|
| [Glance](../integrations/downstream/glance.md) | `exc.Forbidden`/`Unauthorized` | `nova/image/glance.py:831-832` | `ImageNotAuthorized` (`:174`) |
| Glance | `exc.NotFound` | `nova/image/glance.py:834` | `ImageNotFound` |
| Glance | `exc.BadRequest` | `nova/image/glance.py:836` | `Invalid` |
| Glance | `ServiceUnavailable`/`CommunicationError` | `nova/image/glance.py:155-186` | 重试后 `GlanceConnectionFailed` (`nova/exception.py:135`) |
| [Cinder](../integrations/downstream/cinder.md) | `cinder_exception.NotFound` | `nova/volume/cinder.py:233-309` 装饰器族 | `VolumeNotFound` (`nova/exception.py:596`) |
| Cinder | v1 API / microversion 不兼容 | `nova/volume/cinder.py:123-129` | `UnsupportedCinderAPIVersion` / `CinderAPIVersionNotAvailable` |
| [Neutron](../integrations/downstream/neutron.md) | `neutron_client_exc.BadRequest` | `nova/network/neutronv2/api.py:21` | Nova 异常 |
| Neutron | 安全组名多匹配 | `nova/network/neutronv2/api.py:600` | `NoUniqueMatch` (`nova/exception.py:1089`) |

## 4. 后台异步任务失败与降级标识表

| 标识字符串字面量 | 产出位置（`路径:行号`） | 触发条件 | 系统自动兜底行为 |
|---|---|---|---|
| `ComputeResourcesUnavailable` | `nova/exception.py:460` / `manager.py:1958` | 资源 claim 失败 | 抛 `RescheduledException` 重调度 |
| `create.error` 通知 | `nova/compute/manager.py:1953` / `:1970` | 建机异常各分支 | 发 usage 通知，置实例 ERROR |
| `RescheduledException` | `nova/compute/manager.py:1965` | 建机失败可重调度 | 换 host 重试 |

故障定位决策树见 [排障 Runbook](../operations/runbook-and-observability.md)。
