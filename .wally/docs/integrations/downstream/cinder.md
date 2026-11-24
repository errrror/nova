---
kind: downstream-contract
scope: cinder
status: draft
origin: generated
source_paths: [nova/volume/cinder.py, nova/conf/cinder.py, nova/exception.py]
symbols: [cinderclient, API, attach, detach, initialize_connection, create]
upstream: [integrations/index.md, integrations/topology-and-mapping.md]
downstream: []
---

# 下游出向接口契约：`cinder`

Cinder 提供块存储卷的创建、挂卸载与快照能力。本仓业务封装位于 `nova/volume/cinder.py`，`cinderclient(context)` 负责认证与端点解析，`API`（`:309`）组装业务字典调用；通信用 `cinderclient` v3（自 Ocata 起不支持 v1），错误经装饰器翻译。

## 1. 封装定位与连接契约

| 契约项 | 精确值 / 规则 | 源码锚点（`路径:行号`） |
|---|---|---|
| 本仓业务封装文件 | `nova/volume/cinder.py` (`class API`) | `nova/volume/cinder.py:309` |
| 底层客户端构造 | `cinderclient(context, microversion=None, skip_version_check=False)` | `nova/volume/cinder.py:82` |
| 服务目录配置 | `CONF.cinder.catalog_info` 默认 `'volumev3:cinderv3:publicURL'` | `nova/conf/cinder.py:25` |
| 端点覆盖键 | `CONF.cinder.endpoint_template` | `nova/conf/cinder.py:43` |
| 重试配置 | `CONF.cinder.http_retries` 默认 `3` | `nova/conf/cinder.py:69` |
| 跨 AZ 挂载 | `CONF.cinder.cross_az_attach` 默认 `True` | `nova/conf/cinder.py:82` |
| 公共成功判定 | 客户端方法正常返回；异常经 `@translate_cinder_exception` 装饰器族翻译 | `nova/volume/cinder.py:233-309` |

---

## 2. 本仓上游调用方反查表（Who Calls This Wrapper）

| 本仓封装方法 | 上游调用模块与函数 | 所属业务流 / 接口 | 调用点锚点（`路径:行号`） |
|---|---|---|---|
| `create` / `attach` | `nova/compute/manager.py` BDM 处理 | 建机挂卷 | `nova/volume/cinder.py:450` / `:371` |
| `detach` / `terminate_connection` | 删除/迁移流程 | 删除/迁移 | `nova/volume/cinder.py:376` / `:439` |
| `initialize_connection` | `_build_resources` | 建机 | `nova/volume/cinder.py:407` |
| `create_snapshot` | snapshot API | 打快照 | `nova/volume/cinder.py:497` |

---

## 3. 封装方法总清单

| 序号 | 封装函数签名 | 下游目标 | 读写类型 | 幂等 / 重试 | 定义锚点（`路径:行号`） |
|---|---|---|---|---|---|
| 1 | `get(context, volume_id)` | `volumes.get` | 读 | 重试 `http_retries` | `nova/volume/cinder.py:313` |
| 2 | `reserve_volume(context, volume_id)` | `volumes.reserve` | 写 | 非幂等 | `nova/volume/cinder.py:355` |
| 3 | `attach(context, volume_id, instance_uuid, mountpoint, mode='rw')` | `volumes.attach` | 写 | 非幂等 | `nova/volume/cinder.py:371` |
| 4 | `detach(context, volume_id, instance_uuid=None, ...)` | `volumes.detach` | 写 | `nova/volume/cinder.py:376` |
| 5 | `initialize_connection(context, volume_id, connector)` | `volumes.initialize_connection` | 写 | `nova/volume/cinder.py:407` |
| 6 | `create(context, size, name, description, ...)` | `volumes.create` | 写 | `nova/volume/cinder.py:450` |
| 7 | `attachment_create` / `attachment_update` / `attachment_delete` | multiattach API | 写 | `nova/volume/cinder.py:538`/`:566`/`:593` |

---

## 4. 逐方法请求字典与响应解包契约（Full Dict Schemas）

### 4.1 `attach` → 下游 `volumes.attach`（`nova/volume/cinder.py:371-373`）

#### A. 发往下游的组装字典表（Outbound Payload Dict）

```json
{
  "volume_id": "<uuid>",
  "instance_uuid": "<instance-uuid>",
  "mountpoint": "/dev/vdb",
  "mode": "rw"
}
```

| 下游字典键路径 | 类型 | 必填条件 | 默认值 / 固定值 | 值来源与转换逻辑 | 组装行号 |
|---|---|---|---|---|---|
| `volume_id` | `str` | 必填 | — | 上游 BDM 传入 | `nova/volume/cinder.py:371` |
| `instance_uuid` | `str` | 必填 | — | 建机实例 UUID | `nova/volume/cinder.py:372` |
| `mountpoint` | `str` | 必填 | — | 设备名 | `nova/volume/cinder.py:372` |
| `mode` | `str` | 可选 | `"rw"` | 只读卷传 `"ro"` | `nova/volume/cinder.py:371` |

#### B. 下游返回字典与解包规则表（Response Unpacking）

| 下游返回键路径 | 类型 | 本仓提取、判空兜底与转换规则 | 解包行号 |
|---|---|---|---|
| `volumes.get()` 对象属性 | `object` | 经 `_translate_cinder_exception` 后透传 | `nova/volume/cinder.py:313-314` |
| `connection_info`（dict） | `dict` | `initialize_connection` 返回 `connection['connection_info']` | `nova/volume/cinder.py:407-437` |
| `volume['status']` | `str` | `check_attached`/`check_availability_zone` 校验挂载资格 | `nova/volume/cinder.py:330-352` |

#### C. 下游错误码拦截与翻译

| 下游错误码 / 条件 | 下游语义 | 本仓转换后的异常 / 降级返回值 | 代码行号 |
|---|---|---|---|
| `cinder_exception.NotFound` | 卷不存在 | 翻译为 `VolumeNotFound` / 返回 None | `nova/volume/cinder.py:233-309`（装饰器族） |
| v1 API 检测（`version == '1'`） | 不支持 | 抛 `UnsupportedCinderAPIVersion`（`nova/exception.py:144`） | `nova/volume/cinder.py:123-124` |
| v2 + 请求 microversion | 不兼容 | 抛 `CinderAPIVersionNotAvailable`（`nova/exception.py:148`） | `nova/volume/cinder.py:127-129` |
| 跨 AZ 且 `cross_az_attach=False` | 非法挂载 | 拒绝并抛异常 | `nova/volume/cinder.py:337-344` |

## 5. 共变耦合与修改清单（Co-Change Playbook）

- 给卷方法新增入参：改 `nova/volume/cinder.py` 对应方法 → 核对 `nova/compute/manager.py` BDM 调用点 → 更新 [`topology-and-mapping.md`](../topology-and-mapping.md) → 更新 `nova/tests/unit/volume/` 桩。
- **特殊协议陷阱**：Cinder 自 Ocata（Nova 15.0.0）起仅支持 v2/v3（`nova/conf/cinder.py:53`）；microversion 需 `_check_microversion` 校验（`nova/volume/cinder.py:141`）；`endpoint_template` 覆盖 `catalog_info`（`nova/conf/cinder.py:58`）。
