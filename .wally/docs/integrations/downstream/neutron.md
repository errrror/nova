---
kind: downstream-contract
scope: neutron
status: draft
origin: generated
source_paths: [nova/network/neutronv2/api.py]
symbols: [get_client, API, _create_port_minimal, allocate_for_instance, deallocate_for_instance]
upstream: [integrations/index.md, integrations/topology-and-mapping.md]
downstream: []
---

# 下游出向接口契约：`neutron`

Neutron 提供网络、端口与安全组能力。本仓业务封装位于 `nova/network/neutronv2/api.py`：`get_client(context, admin=False)` 构造 `neutronclient.v2_0.client.Client`，`API`（`:231`）组装端口请求字典；成功判定为客户端正常返回，错误由 neutronclient 异常翻译。

## 1. 封装定位与连接契约

| 契约项 | 精确值 / 规则 | 源码锚点（`路径:行号`） |
|---|---|---|
| 本仓业务封装文件 | `nova/network/neutronv2/api.py` (`class API`) | `nova/network/neutronv2/api.py:231` |
| 底层客户端构造 | `get_client(context, admin=False)` → `clientv20.Client(session=_SESSION, ...)` | `nova/network/neutronv2/api.py:122` / `:150` |
| 端点配置键 | `CONF.neutron.url`（endpoint_override）、`CONF.neutron.region_name` | `nova/network/neutronv2/api.py:152-153` |
| 认证插件 | `_load_auth_plugin(conf)` | `nova/network/neutronv2/api.py:66` |
| 公共请求形式 | `port_client.create_port(port_req_body)`，`port_req_body = {'port': {...}}` | `nova/network/neutronv2/api.py:375-386` |

---

## 2. 本仓上游调用方反查表（Who Calls This Wrapper）

| 本仓封装方法 | 上游调用模块与函数 | 所属业务流 / 接口 | 调用点锚点（`路径:行号`） |
|---|---|---|---|
| `allocate_for_instance` | compute `_allocate_network` | 建机 | `nova/network/neutronv2/api.py:801` |
| `deallocate_for_instance` | 删除流程 | 删机 | `nova/network/neutronv2/api.py:1167` |
| `_create_port_minimal` | `allocate_for_instance` | 建机端口分配 | `nova/network/neutronv2/api.py:357` |
| `_process_security_groups` | 端口分配前置校验 | 建机 | `nova/network/neutronv2/api.py:600` |

---

## 3. 封装方法总清单

| 序号 | 封装函数签名 | 下游目标 | 读写类型 | 定义锚点（`路径:行号`） |
|---|---|---|---|---|
| 1 | `get_client(context, admin=False)` | Client 构造 | — | `nova/network/neutronv2/api.py:122` |
| 2 | `allocate_for_instance(context, instance, vpn, ...)` | `create_port` 批 | 写 | `nova/network/neutronv2/api.py:801` |
| 3 | `deallocate_for_instance(context, instance, ...)` | `delete_port` 批 | 写 | `nova/network/neutronv2/api.py:1167` |
| 4 | `_create_port_minimal(port_client, instance, network_id, ...)` | `create_port` | 写 | `nova/network/neutronv2/api.py:357` |
| 5 | `_process_security_groups(instance, neutron, security_groups)` | `list_security_groups` | 读 | `nova/network/neutronv2/api.py:600` |

---

## 4. 逐方法请求字典与响应解包契约（Full Dict Schemas）

### 4.1 `_create_port_minimal` → 下游 `create_port`（`nova/network/neutronv2/api.py:357-446`）

#### A. 发往下游的组装字典表（Outbound Payload Dict）

```json
{
  "port": {
    "device_id": "<instance-uuid>",
    "network_id": "<network-uuid>"
  }
}
```

| 下游字典键路径 | 类型 | 必填条件 | 默认值 / 固定值 | 值来源与转换逻辑 | 组装行号 |
|---|---|---|---|---|---|
| `port.device_id` | `str` | 必填 | — | `instance.uuid` | `nova/network/neutronv2/api.py:375` |
| `port.network_id` | `str` | 有条件写入 | 不传该键 | 若 `network_id` 非空则写入 | `nova/network/neutronv2/api.py:380` |
| `port` (解绑时) | `dict` | 解绑场景 | `{'device_id': '', 'device_owner': ''}` | 清空端口绑定 | `nova/network/neutronv2/api.py:498` |
| `port.security_groups` | `list` | 有安全组时 | — | `_process_security_groups` 校验后的 ID 列表 | `nova/network/neutronv2/api.py:600` |

#### B. 下游返回字典与解包规则表（Response Unpacking）

| 下游返回键路径 | 类型 | 本仓提取、判空兜底与转换规则 | 解包行号 |
|---|---|---|---|
| `port_response['port']['id']` | `str` | 端口 ID 写入 `VirtualInterface` | `nova/network/neutronv2/api.py:386` |
| `port['network_id']` | `str` | 回写 network_id 供后续处理 | `nova/network/neutronv2/api.py:438`/`:445` |
| `port['device_id']` | `str` | 判断是否已绑定 | `nova/network/neutronv2/api.py:559` |
| `list_ports` 结果 | `list` | 按 `device_id`/`network_id` 查询过滤 | `nova/network/neutronv2/api.py:1171`/`:1253` |

#### C. 下游错误码拦截与翻译

| 下游错误码 / 条件 | 下游语义 | 本仓转换后的异常 / 降级返回值 | 代码行号 |
|---|---|---|---|
| `neutron_client_exc.BadRequest` | 非法请求 | 翻译为 Nova 异常 | `nova/network/neutronv2/api.py:21` |
| port binding 失败 | 绑定异常 | `_ensure_no_port_binding_failure` 检查 | `nova/network/neutronv2/api.py:175` |
| 安全组名重复 | 多匹配 | 抛 `NoUniqueMatch` | `nova/network/neutronv2/api.py:600+` |

## 5. 共变耦合与修改清单（Co-Change Playbook）

- 给端口请求新增键：改 `nova/network/neutronv2/api.py:375 port_req_body` 拼装 → 核对 `allocate_for_instance` 调用链 → 更新 [`topology-and-mapping.md`](../topology-and-mapping.md) → 更新 `nova/tests/unit/network/` 桩。
- **特殊协议陷阱**：admin 与非 admin 客户端分离（`get_client(context, admin=True)`，如 `:308`/`:869`）；安全组名需先解析为 ID 且拒重复名（`:600`）；解绑通过清空 `device_id`/`device_owner` 实现（`:498`）。
