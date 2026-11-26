# 02. Plan

## 方案与改动范围

关联需求：`GET /hello` 返回 `{"message": "Hello, World!"}`，无需鉴权（nova v2.1）。

最小改动文件清单：
1. 新增 `nova/api/openstack/compute/hello.py`：定义 `HelloController(wsgi.Controller)`，`index(self, req)` 直接返回 `{"message": "Hello, World!"}`，不调用 `context.can(...)`。
2. 修改 `nova/api/openstack/compute/routes.py`：新增 `from nova.api.openstack.compute import hello`；定义 `hello_controller = functools.partial(_create_controller, hello.HelloController, [], [])`；在 `ROUTE_LIST` 中增加 `('/hello', {'GET': [hello_controller, 'index']})`。
3. 新增 `nova/tests/unit/api/openstack/compute/test_hello.py`：UT 覆盖正向返回、方法限制、返回结构。

无新增依赖。风险等级：低（局部新增、可逆、不改现有接口与数据结构）。

## 调用链与兼容性

- 调用链：HTTP `GET /v2.1/{project_id}/hello` → `APIRouterV21.__init__` 遍历 `ROUTE_LIST` 建立路由 → `wsgi.ResourceV21(HelloController())` 分发到 `index` → 返回 dict，由 wsgi 层序列化为 JSON。
- 兼容性：仅新增路由与控制器，不影响现有资源；不引入 microversion 变更。
- 无需鉴权：控制器内不调用 policy；框架中间件行为不变。
- 副作用：无数据库、无 RPC、无外部调用。
- 回滚：删除新增控制器文件，撤销 `routes.py` 的导入、partial 定义与 `ROUTE_LIST` 条目即恢复原行为。

## UT 设计

- H1 正向：构造 GET 请求调用 `index`，断言返回 `{"message": "Hello, World!"}`，HTTP 200。
- H2 方法限制：对 `/hello` 发起 POST，断言路由不匹配（404/405），仅 GET 生效。
- H3 返回结构：断言返回值为 dict，仅含 `message` 键且值为 `Hello, World!`（ASCII 场景，无中文数据）。
- H4 无鉴权：在不提供鉴权 context 的情况下调用仍返回预期结果，证明控制器未触发 policy 检查。

测试位置：`nova/tests/unit/api/openstack/compute/test_hello.py`。执行入口：项目现有 pytest/tox 单测入口（实现阶段以实际可用命令为准）。

## IT 设计（六步适用）

`execution.json` 中 deploy/it 均未配置，按规则自动 SKIPPED，不声称端到端验证；仅保留代码层 UT。

## 风险与完成结论

- 关键决定：挂在 nova v2.1、不启用 policy、返回固定 JSON。
- 未覆盖边界：真实 WSGI 服务部署下的端到端请求（未配置环境）。
- 无额外授权需求；回滚方案明确；UT 已先于实现设计。

## 知识库证据

- 源码核验：`nova/api/openstack/compute/routes.py`、`nova/api/openstack/compute/limits.py`、`README.rst`。
- 预计受影响知识页：无（未发现 `.wally/docs/`，现有 README 描述项目整体，不因新增一个 API 接口而失真）。
- 无 API/SQL 契约文档需要同步；无缺口需补建文档骨架。
