# 03. Implement + UT + Docs

## 项目规则

已检查 `nova/.wally/`，无 `.wally/rules/` 目录，无额外项目规则。按 Core `core/gates.md` 与工作区 `AGENTS.md` 执行：不修改目标仓库 `AGENTS.md`、不写入 `.wally/versions/`、不硬编码内部平台地址、密钥不落库、SQL 参数化（本次改动不涉及 SQL/密钥/内部地址）。

## 实际改动与 Plan 差异

- 按 Plan 完成：新增 `nova/api/openstack/compute/hello.py`（`HelloController.index` 返回固定 JSON，不调用 policy）；修改 `nova/api/openstack/compute/routes.py`（导入、`hello_controller` partial、`ROUTE_LIST` 的 `GET /hello` 条目）；新增 `nova/tests/unit/api/openstack/compute/test_hello.py`。
- 差异 1：测试用 `importlib.util.spec_from_file_location` 直接加载 `hello.py` 并注入 `sys.path`。原因：遗留代码在 Python 3.11 下无法按包导入（`nova/compute/api.py` 将 `async` 用作参数名，语法错误）。标准 `python -m unittest ...` 入口未能执行。
- 差异 2：测试使用标准 `unittest.TestCase` 而非 `nova.test.TestCase`，避开旧测试基类的配置初始化。
- 无范围扩大；回滚方案与 Plan 一致。

## Red → Green → Refactor

- **Red（实现前）**：命令 `cd nova && /data/workspace/wally-open-8892/.venv/bin/python3 nova/tests/unit/api/openstack/compute/test_hello.py`，退出码 `1`，`Ran 4 tests ... FAILED (failures=4)`；失败均为 `AssertionError: unexpectedly None : hello 模块缺失`，属预期断言失败（非环境/语法失败）。
- **Green（实现后）**：同命令，退出码 `0`，`Ran 4 tests ... OK`（4/4）。
- **Refactor**：无需重构；控制器为最小实现，无重复或可抽取逻辑。

## UT 与增量覆盖率

- 环境：专用 venv `/data/workspace/wally-open-8892/.venv/bin/python3`；为兼容老代码调整本地测试依赖（`SQLAlchemy` 1.3.24、`keystonemiddleware` 5.2.0、`oslo.db` 5.1.0、`oslotest<4` 等），未改动项目 requirements 文件。
- 增量覆盖率命令：`python3 -m coverage run --branch --include='*hello.py' nova/tests/unit/api/openstack/compute/test_hello.py`，随后 `python3 -m coverage report -m --include='*hello.py'`。
- 结果：`nova/api/openstack/compute/hello.py` 4 stmts / 0 miss / 0 branch / **100%** 覆盖。
- 未覆盖边界：`routes.py` 新增 `ROUTE_LIST` 条目仅静态 diff 复核（包导入受 Python 3.11 语法限制），未计入覆盖率通过结论。项目未配置增量门槛，按实际增量结果记录。

## 缺陷回归（适用时）

不适用（功能新增，非缺陷/性能任务）。

## Docs

按 `core/knowledge.md` 读取 `README.rst` 与源码核实；项目无 `.wally/docs/`。新增 v2.1 hello 接口不影响现有 API 契约/SQL 文档，README 为项目整体介绍、不因示例接口失真 → 无需更新。无过期页、无补建骨架需求。

## 增量 CR

- 规则：无 `.wally/rules/`；按 Core gates 与工作区 `AGENTS.md`。
- 最终 diff 范围：`nova/api/openstack/compute/routes.py`（导入 + partial + 路由条目共 8 行）、新增 `hello.py` 与 `test_hello.py`、`.wally/plans/2026-11-26_hello-world-api/` 产物。
- 发现并修复：测试 `_REPO_ROOT` 层级少算一级、`sys.path` 未注入导致 `No module named 'nova'`，均已修复；无业务缺陷。
- 未解决风险：真实 WSGI 端到端未验证；标准包导入与运行时路由表未验证。无阻断性缺陷。

## 完成结论

TDD 通过（Red 为断言失败、Green 4/4）、增量覆盖率通过（100%）、Docs 通过（无需更新）、增量 CR 通过（无阻断缺陷）；Deploy/IT 自动 SKIPPED，端到端行为未验证。

## 知识库证据

实际读取：`README.rst`、`nova/api/openstack/compute/routes.py`、`nova/api/openstack/compute/limits.py`、`nova/tests/unit/api/openstack/compute/test_availability_zone.py`。未发现 `.wally/docs/`；使用系统默认 SOP，已核对现有文档与源码。
