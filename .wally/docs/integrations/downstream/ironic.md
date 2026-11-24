---
kind: downstream-contract
scope: ironic
status: draft
origin: generated
source_paths: [nova/virt/ironic/client_wrapper.py, nova/virt/ironic/driver.py, nova/virt/ironic/patcher.py]
symbols: [IronicClientWrapper, _get_client, call, _get_auth_plugin, get_deploy_patch]
upstream: [integrations/index.md, architecture/virt-and-data.md]
downstream: []
---

# 下游出向接口契约：`ironic`

Ironic 提供裸金属节点管理能力。本仓通过 `nova/virt/ironic/` 子包封装：`IronicClientWrapper`（`client_wrapper.py:36`）动态导入 `ironicclient` 并处理认证/重试，`driver.py` 实现 `ComputeDriver` 接口把裸机纳入 Nova 调度。Ironic 是可选依赖（运行时动态导入，不强制安装）。

## 1. 封装定位与连接契约

| 契约项 | 精确值 / 规则 | 源码锚点（`路径:行号`） |
|---|---|---|
| 本仓业务封装文件 | `nova/virt/ironic/client_wrapper.py` | `nova/virt/ironic/client_wrapper.py:36` |
| 动态导入机制 | `importutils.import_module('ironicclient')`（缺依赖时延迟失败） | `nova/virt/ironic/client_wrapper.py:48` |
| 认证插件 | `_get_auth_plugin()` | `nova/virt/ironic/client_wrapper.py:61` |
| 客户端构造 | `_get_client(retry_on_conflict=True)` | `nova/virt/ironic/client_wrapper.py:70` |
| 统一调用入口 | `call(method, *args, **kwargs)` | `nova/virt/ironic/client_wrapper.py:126` |
| 驱动实现 | `nova/virt/ironic/driver.py`（`IronicDriver`） | `nova/virt/ironic/driver.py` |

---

## 2. 本仓上游调用方反查表（Who Calls This Wrapper）

| 本仓封装方法 | 上游调用模块与函数 | 所属业务流 / 接口 | 调用点锚点（`路径:行号`） |
|---|---|---|---|
| `call` | `IronicDriver` 各生命周期方法 | 裸机建/删/开机 | `nova/virt/ironic/driver.py` |
| `_get_client` | `call` 内部 | 每次调用获取 client | `nova/virt/ironic/client_wrapper.py:126` |

---

## 3. 封装方法总清单

| 序号 | 封装函数签名 | 下游目标 | 读写类型 | 幂等 / 重试 | 定义锚点（`路径:行号`） |
|---|---|---|---|---|---|
| 1 | `_get_client(retry_on_conflict=True)` | client 构造 | — | 冲突重试 | `nova/virt/ironic/client_wrapper.py:70` |
| 2 | `call(method, *args, **kwargs)` | 动态方法分发 | 读写 | 冲突时重试 | `nova/virt/ironic/client_wrapper.py:126` |
| 3 | `_multi_getattr(obj, attr)` | 属性链取值 | — | — | `nova/virt/ironic/client_wrapper.py:113` |
| 4 | `get_deploy_patch(instance, image_meta, flavor, ...)` | 构造部署 JSON Patch | — | — | `nova/virt/ironic/patcher.py:43` |

---

## 4. 逐方法请求字典与响应解包契约（Full Dict Schemas）

### 4.1 `call` → 动态分发到 ironicclient（`nova/virt/ironic/client_wrapper.py:126-141`）

#### A. 发往下游的组装字典表（Outbound Payload Dict）

Ironic 的调用采用「方法名字符串 + 可变参数」动态分发（`client_wrapper.py:126`），节点部署的请求字典由 `get_deploy_patch`（`nova/virt/ironic/patcher.py:43`）构造为 JSON Patch 列表：

```json
[
  {"path": "/instance_info/image_source", "op": "add", "value": "<glance-id>"},
  {"path": "/instance_info/root_gb", "op": "add", "value": 10},
  {"path": "/instance_info/vcpus", "op": "add", "value": 2}
]
```

| 下游字典键路径 | 类型 | 必填条件 | 默认值 / 固定值 | 值来源与转换逻辑 | 组装行号 |
|---|---|---|---|---|---|
| `patch[].path` | `str` | 必填 | — | JSON Patch 路径（`/instance_info/image_source` 等） | `nova/virt/ironic/patcher.py:59` |
| `patch[].op` | `str` | 必填 | `"add"` | 操作类型 | `nova/virt/ironic/patcher.py:59` |
| `patch[].value` | `any` | 依 path | — | `instance.display_name`/`vcpus`/`memory_mb` 等 | `nova/virt/ironic/patcher.py:59-109` |

#### B. 下游返回字典与解包规则表（Response Unpacking）

| 下游返回键路径 | 类型 | 本仓提取、判空兜底与转换规则 | 解包行号 |
|---|---|---|---|
| `node.uuid` | `str` | 节点唯一标识，写入实例映射 | `nova/virt/ironic/driver.py` |
| `node.provision_state` | `str` | 映射为 Nova `vm_state`/`task_state` | `nova/virt/ironic/driver.py` |
| `call` 返回值 | `any` | `_multi_getattr` 取嵌套响应字段 | `nova/virt/ironic/client_wrapper.py:113` |

#### C. 下游错误码拦截与翻译

| 下游错误码 / 条件 | 下游语义 | 本仓转换后的异常 / 降级返回值 | 代码行号 |
|---|---|---|---|
| `ironic.exc.Conflict` | 并发冲突 | `retry_on_conflict=True` 时重试 | `nova/virt/ironic/client_wrapper.py:70` |
| `ironicclient` 缺失 | 可选依赖未装 | ImportError 延迟到 `import_module` 处 | `nova/virt/ironic/client_wrapper.py:48` |

## 5. 共变耦合与修改清单（Co-Change Playbook）

- 新增裸机节点字段：改 `nova/virt/ironic/patcher.py` patch 构造 → 核对 `driver.py` 读写 → 更新单测。
- **特殊协议陷阱**：`ironicclient` 运行时动态导入，静态图无法穷举其方法；`call` 为字符串动态分发（`nova/virt/ironic/client_wrapper.py:126`），改方法名须同步全部调用点。外部黑盒边界详见 [`boundary.md`](../../operations/boundary.md)。
