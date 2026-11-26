# 02. Plan

## 方案与改动范围

风险等级：中（跨组件 HTTP 相互调用、潜在循环），新增接口不改既有契约、可回滚。

`nova` 最小改动文件：
- `nova/nova/api/openstack/compute/welcome.py`（新增）：`WelcomeController(wsgi.Controller)`，`index(req)` 打印 `LOG.info('welcome from nova')`；无转发头时 `requests.get(peer_welcome_url, headers={'X-Welcome-Forwarded': '1'}, timeout=...)`，捕获 `requests.RequestException` 记 warning；返回 `{'welcome': 'welcome', 'service': 'nova'}`。`create_resource()` 返回 `wsgi.Resource`。
- 对端地址配置项：在 welcome 模块内以 `cfg.OptGroup('welcome')` + `CONF.register_group/register_opts` 注册 `peer_welcome_url`（默认回环地址）与 `request_timeout`，自包含、不改全局 conf 汇总。
- `nova/nova/api/openstack/compute/routes.py`（改）：import welcome、注册路由到 `GET /welcome`。
- `nova/nova/tests/unit/api/openstack/compute/test_welcome.py`（新增）：UT。

## 调用链与兼容性

- 外部 `GET /welcome` → 打印 welcome → 回呼对端（带 `X-Welcome-Forwarded: 1`）→ 对端打印 welcome 并因看到该头不再回呼 → 对端返回 → 本地返回。
- 反向同理。一次外部请求最多一跳对端调用，杜绝无限递归。
- 新增路由，不改既有 REST 契约/数据结构。对端地址与超时走配置项，默认回环地址，无内部地址硬编码。
- 异常：超时/连接失败记 warning 并降级；配置为空则跳过回呼。

回滚：删除新增 controller 与 UT，移除路由新增行，分支重置即可，无数据迁移。

## UT 设计

- U01 正向：无转发头 → 200、打印 welcome、回呼对端一次（URL/超时来自配置项）。
- U02 边界：带 `X-Welcome-Forwarded: 1` → 打印但不回呼。
- U03 异常：对端抛 `RequestException` → 降级返回成功、记 warning。
- U04 Unicode：带中文 query 的请求 → 响应可正常 JSON 序列化。
测试位置：`nova/nova/tests/unit/api/openstack/compute/test_welcome.py`。

## IT 设计（六步适用）

04 Deploy / 05 IT 未配置，SKIPPED；不执行环境级部署/集成验证。未验证边界：真实跨组件 HTTP 联通与日志落盘，具备环境时另验，不声称端到端已验证。

## 风险与完成结论

关键决定：转发头防递归、对端地址配置项、故障降级（用户已确认方案）。未覆盖：真实环境联通（04/05 SKIPPED）。Commit/Push/MR 需单独授权。UT 先于实现设计，待实现后执行并记录真实结果。

## 知识库证据

使用系统内置默认 SOP，无仓库内 `.wally/docs/`；依据实际读取的路由/controller/日志/依赖/UT 样例，未凭对话推测。最终 Review 对照完整 diff 复查。
