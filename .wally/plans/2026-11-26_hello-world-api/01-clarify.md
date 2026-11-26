# 01. Clarify

## 目标与成功判据

- 目标：在 nova 仓库新增最小化的 hello world REST 接口：`GET /hello` 返回 JSON `{"message": "Hello, World!"}`，不调用任何 policy 鉴权。
- 用户原始诉求：“增加一个hello world的接口”，并追加“涉及nova和cinder都要增加这个接口”。
- 成功判据：
  1. nova v2.1 API 注册 `GET /hello`，请求返回 HTTP 200 与 JSON 体 `{"message": "Hello, World!"}`。
  2. 控制器不调用 `context.can(...)` / policy 鉴权，不依赖鉴权信息（无需鉴权）。
  3. 新增单元测试通过，覆盖正向返回、方法限制与返回结构。
- 用户本轮确认：分支新建 `feature/hello-world-api`（基于 `master`）；接口约定 `GET /hello`、无需鉴权、返回 `{"message": "Hello, World!"}`。

## 范围、约束与依赖

- 范围：仅新增 `nova/api/openstack/compute/hello.py`、`nova/tests/unit/api/openstack/compute/test_hello.py`，并修改 `nova/api/openstack/compute/routes.py` 注册路由；不改现有接口、数据结构与配置项。
- 约束：
  - 遵循系统内置默认六阶段 SOP（builtin-generic-v1 / 0ac183662b5491b3）。
  - 在独立分支 `feature/hello-world-api` 实现，不在 `master` 改业务源码。
  - 不修改仓库 `AGENTS.md`，不写入 `.wally/versions/`。
  - 不硬编码内部平台地址，不引入明文密钥。
- 依赖：nova 现有 `wsgi.Controller` 与 `ROUTE_LIST` / `APIRouterV21` 路由框架，无新增第三方依赖。
- 与 cinder 的同名接口是并列任务，各自独立分支与独立 SOP 任务目录。

## 问题与决策

- 分支归属：当前在 `master`，按 SOP 不能直接在基线分支实现 → 用户确认新建 `feature/hello-world-api`。
- 接口挂载：用户未指定版本 → 采用 nova v2.1（`nova/api/openstack/compute`），与现有 REST API 风格一致。
- “无需鉴权”解释：控制器内不调用 policy 检查；框架中间件行为不变，不改变全局鉴权链。
- 返回内容：用户已明确为 `{"message": "Hello, World!"}`，无需再确认。
- 无重大未决业务问题。

## 缺陷 / 性能输入（适用时）

不适用（功能新增，非缺陷/性能任务）。

## 完成结论

目标与验收判据可验证，用户已确认分支与接口约定，无未决业务问题；UT 设计见 02 Plan；Deploy/IT 未配置环境，按规则 SKIPPED。

## 知识库证据

- 读取 `README.rst`：确认项目为 OpenStack Nova（计算服务）。
- 读取 `nova/api/openstack/compute/routes.py`：`ROUTE_LIST` 为有序元组，`APIRouterV21.__init__` 通过 `create_route` 注册；`limits` 路由为同目录邻近示例。
- 读取 `nova/api/openstack/compute/limits.py`：确认 `wsgi.Controller` 控制器模式与 `context.can(...)` 鉴权位置（本任务不调用）。
- 查看 `nova/tests/unit/api/openstack/compute/` 目录：确认单元测试位置。
- 未发现仓库内 `.wally/docs/`；使用系统默认 SOP，已核对现有 README 与源码，不新建文档骨架。
