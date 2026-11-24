---
kind: downstream-contract
scope: glance
status: draft
origin: generated
source_paths: [nova/image/glance.py, nova/conf/glance.py, nova/exception.py]
symbols: [GlanceClientWrapper, GlanceImageServiceV2, _create_v2, _translate_to_glance, _translate_from_glance, call]
upstream: [integrations/index.md, integrations/topology-and-mapping.md]
downstream: []
---

# 下游出向接口契约：`glance`

Glance 提供镜像元数据与镜像数据存取能力。本仓业务封装位于 `nova/image/glance.py`，核心是 `GlanceClientWrapper`（连接/重试底座）与 `GlanceImageServiceV2`（业务字典组装/解包层）；通信用 `glanceclient` v2，成功判定为 HTTP 非异常返回，错误经 `_reraise_translated_image_exception` 翻译。

## 1. 封装定位与连接契约

| 契约项 | 精确值 / 规则 | 源码锚点（`路径:行号`） |
|---|---|---|
| 本仓业务封装文件 | `nova/image/glance.py`（`GlanceImageServiceV2`） | `nova/image/glance.py:189` |
| 底层传输类 | `GlanceClientWrapper.call` | `nova/image/glance.py:126` / `:151` |
| 端点配置键 | `CONF.glance.api_servers`（列表，无默认值需配置） | `nova/conf/glance.py:28` |
| 重试配置 | `CONF.glance.num_retries` 默认 `0` | `nova/conf/glance.py:39` |
| 公共请求形式 | `client.call(context, version=2, method, **kwargs)` → `getattr(controller, method)(*args, **kwargs)` | `nova/image/glance.py:151-167` |
| 客户端构造 | `glanceclient.Client(version, session=_SESSION, auth=auth, ...)` | `nova/image/glance.py:56-67` |

---

## 2. 本仓上游调用方反查表（Who Calls This Wrapper）

| 本仓封装方法 | 上游调用模块与函数 | 所属业务流 / 接口 | 调用点锚点（`路径:行号`） |
|---|---|---|---|
| `show` | compute `_build_resources` / 镜像元数据读取 | 建机 | `nova/image/glance.py:213` |
| `create` / `_create_v2` | 镜像快照上传 | snapshot 流程 | `nova/image/glance.py:377` / `:451` |
| `delete` | 镜像删除 | 清理 | `nova/image/glance.py:524` |
| `download` | 镜像下载（含签名校验） | 建机拉镜像 | `nova/image/glance.py:275` |

---

## 3. 封装方法总清单

| 序号 | 封装函数签名 | 下游目标 | 读写类型 | 幂等 / 重试 | 定义锚点（`路径:行号`） |
|---|---|---|---|---|---|
| 1 | `show(context, image_id, include_locations=False)` | `images.get` | 读 | 重试 `num_retries` | `nova/image/glance.py:213` |
| 2 | `detail(context, **kwargs)` | `images.list` | 读 | 同上 | `nova/image/glance.py:260` |
| 3 | `create(context, image_meta, data=None)` | `images.create` | 写 | 同重试；非幂等 | `nova/image/glance.py:377` |
| 4 | `update(context, image_id, image_meta, data=None, purge_props=True)` | `images.update` | 写 | `nova/image/glance.py:481` |
| 5 | `delete(context, image_id)` | `images.delete` | 写 | 吞 `NotFound`/`Forbidden` | `nova/image/glance.py:524` |

---

## 4. 逐方法请求字典与响应解包契约（Full Dict Schemas）

### 4.1 `create` → 下游 `images.create`（`nova/image/glance.py:377`、`:451-479`）

#### A. 发往下游的组装字典表（Outbound Payload Dict）

```json
{
  "name": "ubuntu-22.04",
  "disk_format": "qcow2",
  "container_format": "bare",
  "visibility": "private",
  "min_ram": 0,
  "min_disk": 10,
  "properties": {"kernel_id": null, "ramdisk_id": null}
}
```

| 下游字典键路径 | 类型 | 必填条件 | 默认值 / 固定值 | 值来源与转换逻辑 | 组装行号 |
|---|---|---|---|---|---|
| `disk_format` | `str` | `force_activate` 时必填 | `_get_image_create_disk_format_default` | 缺失时补默认值 | `nova/image/glance.py:458-461` |
| `container_format` | `str` | `force_activate` 时必填 | `"bare"` | 缺失时固定填 `"bare"` | `nova/image/glance.py:462-463` |
| `visibility` | `str` | 由 `is_public` 映射 | `"public"`/`"private"` | `is_public` → `visibility`（`_convert_to_v2`） | `nova/image/glance.py:663` |
| `min_ram` / `min_disk` | `int` | 可选 | — | `int(value)` 强转 | `nova/image/glance.py:659` |
| `properties.*` | `str/None` | 可选 | — | 非字符串值 `str()` 化；`kernel_id`/`ramdisk_id` 为 `'none'`/`''` 时跳过 | `nova/image/glance.py:649-658` |
| `location` | `str` | 可选 | 不传 | 先 `pop` 出来，另发 `_add_location` | `nova/image/glance.py:465-472` |

#### B. 下游返回字典与解包规则表（Response Unpacking）

| 下游返回键路径 | 类型 | 本仓提取、判空兜底与转换规则 | 解包行号 |
|---|---|---|---|
| `image['id']` | `str` | `image = call(...); image_id = image['id']` | `nova/image/glance.py:466-468` |
| `visibility` | `str` | `_translate_from_glance`：`is_public = value == 'public'` | `nova/image/glance.py:765` |
| `size` | `int` | `getattr(image, 'size', 0) or 0` | `nova/image/glance.py:762` |
| `properties` | `dict` | `getattr(image, 'properties', {})` | `nova/image/glance.py:777` |
| `direct_url` / `locations` | `str/list` | 仅 `include_locations=True` 时纳入 | `nova/image/glance.py:784` |

#### C. 下游错误码拦截与翻译

| 下游错误码 / 条件 | 下游语义 | 本仓转换后的异常 / 兜底 | 代码行号 |
|---|---|---|---|
| `glanceclient.exc.Forbidden` / `Unauthorized` | 无权限 | 翻译为 `ImageNotAuthorized` | `nova/image/glance.py:831-832` |
| `glanceclient.exc.NotFound` | 镜像不存在 | 翻译为 `ImageNotFound` | `nova/image/glance.py:834` |
| `glanceclient.exc.BadRequest` | 非法请求 | 翻译为 `Invalid` | `nova/image/glance.py:836` |
| `ServiceUnavailable`/`InvalidEndpoint`/`CommunicationError` | 连接问题 | 重试 `num_retries` 次后抛 `GlanceConnectionFailed`（`nova/exception.py:135`） | `nova/image/glance.py:155-186` |

## 5. 共变耦合与修改清单（Co-Change Playbook）

- 给镜像 `create` 新增入参键：改 `nova/image/glance.py:451 _create_v2` 字典拼装 → 核对上游 `nova/compute/manager.py` 传参 → 更新 [`topology-and-mapping.md`](../topology-and-mapping.md) → 更新 `nova/tests/unit/image/` Mock 夹具。
- **特殊协议陷阱**：glance v2 只接受字符串/None 属性值，其他类型必须 `str()` 化（`nova/image/glance.py:652-655`）；`is_public` 与 `visibility` 双向映射（`:663`/`:765`）；`location` 必须分两次请求发送（`:465-472`）。
