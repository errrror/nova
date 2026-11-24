---
kind: mapping
scope: inbound-to-outbound-mapping
status: draft
origin: generated
source_paths: [nova/api/openstack/compute/servers.py, nova/compute/manager.py, nova/image/glance.py, nova/volume/cinder.py, nova/network/neutronv2/api.py]
symbols: [ServersController.create, API.create, _build_resources, _create_v2, attach, _create_port_minimal]
upstream: [contracts/api-reference.md, integrations/index.md]
downstream: [integrations/downstream/glance.md, integrations/downstream/cinder.md, integrations/downstream/neutron.md]
---

# 上下游参数组装与字段映射矩阵

本页追踪「上游建机请求 → conductor/compute 编排 → 各下游请求字典」的字段变形规则。核心场景是 `POST /servers`：入向 DTO 经多层转换，扇出到 Cinder（卷）、Neutron（端口）、Glance（镜像）三个下游。

## 1. 上游入口 → 下游扇出编排顺序表（Fan-Out Sequence）

| 上游入口（Action / 路由 / 任务） | 主编排函数（`路径:行号`） | 按序调用的下游封装方法链（含条件分支） | 短路 / 聚合规则 |
|---|---|---|---|
| `POST /servers` | `ServersController.create` (`nova/api/openstack/compute/servers.py:453`) | `1. context.can(:483)` → `2. API.create(:1584)` → `3. conductor.build_instances` → `4. build_and_run_instance(:1702)` → `_build_resources(:2067)` | 鉴权/配额失败立即抛错；claim 失败重调度 |
| 建机资源准备 | `_build_resources` (`nova/compute/manager.py:2067`) | `1. _allocate_network` → `2. _create_block_device_mapping` → `3. image` | 任一失败进入资源回滚 |

## 2. 核心场景入向 → 出向字段级映射矩阵（Field-Level Mapping）

### 场景：创建实例（`POST /servers`）

#### A. 上游入参字段 → 下游请求字典键映射

| 上游入参字段路径（类型） | 转换/校验/默认值注入逻辑 | 目标下游与封装方法 | 下游请求字典精确 Key 路径（类型） | 组装源码锚点（`路径:行号`） |
|---|---|---|---|---|
| `server.name` (`str`) | `common.normalize_name` 规范化（`servers.py:458`）→ `description`（2.19+） | conductor 编排 | `instances[].display_name` | `nova/api/openstack/compute/servers.py:458` |
| `server.imageRef` (`str`) | 解析为 image meta → `objects.ImageMeta.from_dict` (`manager.py:1927`) | glance `show` | `image_id`（path 参数） | `nova/image/glance.py:213` |
| `server.block_device_mapping` (`list`) | 转换 BDM → 卷挂卸载 | cinder `attach` | `volume_id`, `instance_uuid`, `mountpoint`, `mode`（默认 `'rw'`） | `nova/volume/cinder.py:371` |
| `server.networks` (`list`) | 解析 requested_networks → 端口分配 | neutron `_create_port_minimal` | `port['device_id']`, `port['network_id']` | `nova/network/neutronv2/api.py:375-380` |
| `server.tags` (`list`) | 仅 microversion ≥ 2.52 注入 create_kwargs | conductor 编排 | `tags` | `nova/api/openstack/compute/servers.py:473-474` |
| *(上下文隐式注入)* | 从 `req.environ['nova.context']` 提取租户身份 | 全部下游公共字段 | `project_id` / `user_id`（来自 context） | `nova/api/openstack/compute/servers.py:455` / `:479-482` |

#### B. 下游返回字典 → 本仓对象 / 上游出参回填映射

| 下游返回键路径（类型） | 判空 / 兜底 / 格式转换逻辑 | 回填目标字段路径（类型） | 解包源码锚点（`路径:行号`） |
|---|---|---|---|
| glance `image['id']` (`str`) | `_translate_from_glance` 翻译属性 | `ImageMeta.id` / 响应 `imageRef` | `nova/image/glance.py:468` / `:678` |
| glance `visibility`（`str`） | `is_public` ↔ `visibility`（`public`/`private`）双向转换 | `image_meta.is_public` | `nova/image/glance.py:661` / `:765` |
| cinder `connection_info` (`dict`) | `initialize_connection` 返回后写入 BDM | `block_device_info` → hypervisor | `nova/volume/cinder.py:407` |
| neutron `create_port` 响应 `port['id']` | `port_req_body` 回写 device_id | `VirtualInterface` / `network_info` | `nova/network/neutronv2/api.py:386` |

## 3. 通用字典拼装模式与共变修改清单（Co-Change Checklist）

- **公共信封构造器**：glance `_create_v2`（`nova/image/glance.py:451`）以 `**sent_service_image_meta` 展开字典；neutron `_create_port_minimal`（`nova/network/neutronv2/api.py:357`）构造 `{'port': {...}}`（`:375`）。
- **重试汇聚器**：`GlanceClientWrapper.call`（`nova/image/glance.py:151`）按 `1 + CONF.glance.num_retries` 次尝试，生成器结果转 list 以便捕获延迟异常（`:164-166`）。
- **新增透传字段标准改动链（Agent Checklist）**：
  1. 入向 Schema 解析新增字段：`nova/api/openstack/compute/servers.py:453`
  2. conductor 载荷透传（版本协商）：`nova/conductor/rpcapi.py:328`
  3. 下游封装方法写入请求 dict：对应 `downstream/*.md`
  4. 如需回显，更新响应序列化：`nova/api/openstack/compute/servers.py`
  5. 更新 Mock 夹具并运行回归单测：`nova/tests/unit/`

各下游完整字典契约见 [Glance](downstream/glance.md) · [Cinder](downstream/cinder.md) · [Neutron](downstream/neutron.md)。


## 4. 字段映射校验清单（Agent Checklist）

- 每个新增透传字段须满足三向闭合：入向 DTO 解析（`servers.py:453`）→ conductor 载荷版本兼容（`nova/conductor/rpcapi.py:328`）→ 下游请求字典写入（各 `downstream/*.md`）→ 出参回填（`nova/image/glance.py:678 _translate_from_glance`）。
- **弱命中纪律**：字典键名必须从源码 `Read` 原文核验原词字面出现，禁止凭近邻词推测；找不到的字段如实标注「未找到字面实现」。
- 完整字典契约见 [Glance](downstream/glance.md)、[Cinder](downstream/cinder.md)、[Neutron](downstream/neutron.md)。
