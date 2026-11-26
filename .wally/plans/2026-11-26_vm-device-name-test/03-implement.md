# 03. Implement + UT + Docs

## 项目规则

- 读取 `nova/AGENTS.md`（仓库根共享规则）：按授权范围改动、SQL 参数化、密钥不落库、不硬编码内部地址、测试放 `tests/`、kbengine 维护来源约束。本任务改动不涉及 SQL/密钥/内部地址/kbengine。
- `.wally/rules/` 目录不存在（无额外项目规则），按 builtin 默认 SOP 执行。

## 实际改动与 Plan 差异

- 改动文件：
  - `nova/virt/libvirt/config.py`：新增常量 `DEVICE_NAME_TEST_SUFFIX='-test'` 与幂等函数 `_with_device_test_suffix()`；在三处 `format_dom()` 的 `<target dev=...>` 输出点调用该函数：
    - `LibvirtConfigGuestDisk.format_dom()`（磁盘）
    - `LibvirtConfigGuestSnapshotDisk.format_dom()`（快照磁盘）
    - `LibvirtConfigGuestInterface.format_dom()`（网卡）
  - `nova/tests/unit/virt/libvirt/test_config.py`：同步更新 25 行 `assertXmlEqual` 期望值（22 个 `to_xml()` 测试），将 `<target dev=X>` 改为 `<target dev=X-test>`；`parse_str()` 输入 XML 未改。
- 与 Plan 差异：
  - Plan 中把 `<target dev>` 输出点写为 `LibvirtConfigGuestHostdev(config.py:1335)`，经实测修正为 `LibvirtConfigGuestSnapshotDisk`(1030) 与 `LibvirtConfigGuestInterface`(1350)；`LibvirtConfigGuestHostdev` 不输出 `<target dev>`。已在 01/02 文档以代码事实为准。
  - 测试入口未按 `tox -e py3` 运行：老版 Nova 依赖链在 Python 3.11 上不兼容（如 `oslo.db.concurrency` 已移除、eventlet<0.21 无法安装），改用隔离加载器真实执行 `config.py` 与 `test_config.py`（见下）。此为环境限制，已如实记录，未伪造通过。

## Red → Green → Refactor

环境：Python 3.11.6；venv `/data/workspace/wally-open-8892/.venv`；依赖 lxml 6.1.3 / fixtures 4.3.2 / stestr 4.2.1 / oslo.config 10.8.1（均来自项目 requirements 声明，属环境补齐）。

- 测试产物：
  - `cases/test_device_name_suffix.py`：7 个专项用例（U1/U2/U3 正向、U5 幂等、U6 空值、U7 Unicode、U8 路径形式）。
  - `cases/run_real_config_tests.py`：隔离加载真实 `config.py` + `test_config.py`，stub `nova.test`/`matchers`，用 lxml C14N2 做 XML 等价比较；支持 `CONFIG_PATH`/`TEST_PATH` 环境变量以便 A/B 对比。
- Red（实现前）：`test_device_name_suffix.py` 运行 → 7 例中 5 例断言失败（U1/U2/U3/U7/U8，均为 `X != X-test`），退出码 1。属预期断言失败，非环境/语法错误。
- Green（实现后）：同命令 → 7 例全部 OK，退出码 0。
- 真实回归 A/B：
  - 基线（git show master 的原始 config.py）+ 原始 test_config.py：170 例，0 fail / 22 error（22 error 为隔离 matcher 的 C14N2 误判，与改动无关，作为基线常量）。
  - 修改后 config.py + 原始 test_config.py：170 例，22 fail / 22 error → 新增 22 fail 均为 `<target dev>` 期望未同步。
  - 修改后 config.py + 更新期望后的 test_config.py：170 例，0 fail / 22 error → 回到基线水平，行为变更的回归已消除。
- Refactor：`_with_device_test_suffix()` 集中处理后缀，无重复逻辑；无需进一步重构。

## UT 与增量覆盖率

- 专项用例 7/7 通过；真实 `test_config.py` 170 例 0 失败（22 error 为基线 matcher 误判，非代码缺陷）。
- 增量行覆盖：新增生产代码 3 行分支（`_with_device_test_suffix` 的 3 条 return 路径），被 U1（追加）、U5（幂等）、U6（空值）分别覆盖；三处调用点被 U1/U2/U3 覆盖。Unicode/路径形式由 U7/U8 覆盖。
- 覆盖率报告：未生成（隔离运行器无 coverage 插件，项目 tox 入口因依赖链不可用）。如实记录为未验证，不编造百分比。

## 缺陷回归（适用时）

不适用（功能新增，非缺陷任务）。

## Docs

- 受影响权威文档：无。改动仅影响 domain XML 的设备名输出（测试/演示用途），`README.rst` 与 `doc/` 无对应描述，无需更新。
- 系统默认 SOP，无仓库内 `.wally/docs/`，按 builtin-policy 第 3 条如实记录，不以此阻断。

## 增量 CR

- 读取规则：`nova/AGENTS.md`、builtin 默认 SOP core 全部规则；语言 Python 3.11。
- 最终 diff：`nova/virt/libvirt/config.py`(+28/-3)、`nova/tests/unit/virt/libvirt/test_config.py`(+25/-25)。
- 复核结果：
  - 后缀仅作用于 XML 输出，`target_dev` 内部值未变，按 dev 名查找（detach/snapshot）不受影响。
  - 幂等处理避免重复追加；空值不抛异常。
  - 三处 `<target dev>` 输出点全部覆盖（磁盘/快照磁盘/网卡），无遗漏。
- 未解决风险：带 `-test` 的设备名是否被 libvirt/KVM 接受未验证（IT 未配置，用户已知悉并接受）。

## 完成结论

- TDD：通过（Red 5 失败 → Green 7 通过，真实回归 0 新增失败）。
- 覆盖率：不适用/未生成报告（如实记录，不编造）。
- Docs：通过（无需更新，依据已记录）。
- 增量 CR：通过（无阻断性缺陷，风险已记录）。
- 适用门禁无失败，可进入 Review/Commit。

## 知识库证据

- 实际读取：`nova/AGENTS.md`、`sop-runtime/builtin/0ac183662b5491b3/core/`（knowledge/gates/workflow）、`nova/virt/libvirt/config.py`（26-55、721-790、961-1033、1284-1355）、`nova/tests/unit/virt/libvirt/test_config.py`（24-26、549-609、980-1130、1590-1740）。
- 源码核验：三处 `<target dev>` 输出点经 `grep 'etree.Element("target", dev=self.target_dev'` 确认为 786/1030/1350 三处，已全部覆盖。
- 缺口：完整 tox/stestr 入口因老版 Nova 与 Python 3.11 依赖不兼容不可用，采用隔离加载器真实执行被测源码；Deploy/IT 未配置自动 SKIPPED。最终 Review 对照完整任务 diff 复查。
