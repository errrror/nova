---
kind: operations
scope: dev-and-test
status: draft
origin: generated
source_paths: [tox.ini, .testr.conf, setup.cfg, nova/tests/unit/conf_fixture.py, test-requirements.txt]
symbols: [ConfFixture, parse_args, ostestr]
upstream: [INDEX.md]
downstream: []
---

# 构建启动与单测验证手册（Agent Verification Playbook）

Nova 是 Python 项目，使用 `tox` 作为统一测试/构建入口、`ostestr`/`testrepository` 做测试发现与并发调度、`oslo.config` 管理配置。所有命令核实自 `tox.ini` 与 `.testr.conf`。支持 Python 2.7 与 3.5（`setup.cfg:17-19`）。

## 1. 环境前置与可执行命令速查

| 动作 | 精确执行命令 | 配置来源（`路径:行号`） | 备注 / 前置环境变量 |
|---|---|---|---|
| 安装依赖 | `pip install -c{UPPER_CONSTRAINTS_FILE} -r test-requirements.txt -r requirements.txt` | `tox.ini:12` / `test-requirements.txt` | tox `usedevelop=True`（`tox.ini:7`） |
| 全量单测（py2.7） | `tox -e py27` | `tox.ini:26` | `OS_TEST_PATH=./nova/tests/unit`（`tox.ini:16`） |
| 全量单测（py3.5） | `tox -e py35` | `tox.ini:32` | `bash tools/pretty_tox3.sh` |
| 功能测试 | `tox -e functional` | `tox.ini:57` | `OS_TEST_PATH=./nova/tests/functional`（`tox.ini:61`） |
| 单文件/单用例 | `tox -e py27 -- nova.tests.unit.compute.test_compute` | `tox.ini:27 ostestr '{posargs}'` | 精准用例优先 |
| 代码风格 Lint | `tox -e pep8` | `tox.ini:38` | `bash tools/flake8wrap.sh`（`tox.ini:41`） |
| 增量 Lint | `tox -e fast8` | `tox.ini:48` | 仅 HEAD-1 变更文件 |
| 配置样例生成 | `tox -e genconfig` | `tox.ini:92` | `oslo-config-generator --config-file=etc/nova/nova-config-generator.conf` |
| 策略样例生成 | `tox -e genpolicy` | `tox.ini:95` | `oslopolicy-sample-generator` |
| 覆盖率 | `tox -e cover` | `tox.ini:98` | — |

## 2. 源码模块 → 必跑回归测试映射表（Module-to-Test Map）

> Agent 改代码后必查此表，精准运行受影响模块的回归套件。

| 被修改的源码文件 / 目录 | 必跑测试文件 | 关键测试函数 / 覆盖契约点 | 精确运行命令 |
|---|---|---|---|
| `nova/compute/manager.py`、`nova/compute/api.py` | `nova/tests/unit/compute/test_compute.py`、`test_compute_mgr.py`、`test_compute_api.py` | 建机调用树、claim、状态迁移 | `tox -e py27 -- nova.tests.unit.compute.test_compute` |
| `nova/compute/resource_tracker.py` | `nova/tests/unit/compute/test_resource_tracker.py` | 资源 claim/账本一致性 | `tox -e py27 -- nova.tests.unit.compute.test_resource_tracker` |
| `nova/conductor/` | `nova/tests/unit/conductor/` | 对象动作分发、编排 RPC | `tox -e py27 -- nova.tests.unit.conductor` |
| `nova/scheduler/` | `nova/tests/unit/scheduler/` | 过滤/权重、_schedule | `tox -e py27 -- nova.tests.unit.scheduler` |
| `nova/virt/` | `nova/tests/unit/virt/` | 驱动 spawn/destroy 契约 | `tox -e py27 -- nova.tests.unit.virt` |
| `nova/image/glance.py` | `nova/tests/unit/image/` | 字典键拼装、异常翻译 | `tox -e py27 -- nova.tests.unit.image` |
| `nova/volume/cinder.py` | `nova/tests/unit/volume/` | Cinder 字典/版本协商 | `tox -e py27 -- nova.tests.unit.volume` |
| `nova/network/neutronv2/` | `nova/tests/unit/network/` | 端口字典、安全组 | `tox -e py27 -- nova.tests.unit.network` |
| `nova/db/sqlalchemy/` | `nova/tests/unit/db/` | 参数化 SQL、CRUD | `tox -e py27 -- nova.tests.unit.db` |
| `nova/objects/` | `nova/tests/unit/objects/` | 对象版本兼容/序列化 | `tox -e py27 -- nova.tests.unit.objects` |
| `nova/api/openstack/compute/` | `nova/tests/unit/api/openstack/compute/` | 路由/microversion/策略 | `tox -e py27 -- nova.tests.unit.api.openstack.compute` |

## 3. 测试环境隔离与 Mock / Fixture 编写规范

1. **配置隔离**：统一用 `nova/tests/unit/conf_fixture.py:30 ConfFixture`（继承 `config_fixture.Config`）覆盖配置，禁止污染全局 `CONF`。
2. **测试发现**：`.testr.conf:3` 用 `subunit.run discover`，默认 `OS_TEST_TIMEOUT=160`（`.testr.conf:5`），可通过 `OS_TEST_PATH` 限定范围。
3. **分组约束**：`.testr.conf:18 group_regex` 保证同一 placement API YAML 的 gabbi 测试在同一进程顺序执行（HTTP 请求有序）。
4. **Fake 对象体系**：`nova/tests/unit/fake_instance.py`、`fake_flavor.py`、`fake_network.py`、`fake_volume.py` 等提供标准桩，优先复用而非自创。
5. **提交禁令**：禁止提交 `.testrepository/`、`.pyc`、`*.sqlite`（`.gitignore:5-16`）或任何测试生成的数据库/日志。


## 4. 共变耦合与测试补全清单（Agent Co-Change Playbook）

- 修改某模块后须回到第 2 节映射表确认「必跑测试文件」并逐项执行，禁止只跑部分用例声称通过。
- 新增模块须同步在 `nova/tests/unit/` 建同构目录并在本页映射表登记。
- 新增 oslo.config 选项后须跑 `tox -e genconfig`（`tox.ini:92`）验证样例配置可生成；新增策略须跑 `tox -e genpolicy`（`tox.ini:95`）。
- 禁止提交测试产物（`.testrepository/`、`.pyc`、`*.sqlite`，见 `.gitignore:5-16`）与任何日志/向量/会话记录。
