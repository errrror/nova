# 02. Plan

## 方案与改动范围

- 需求判据：创建虚拟机时，libvirt domain XML 中磁盘与网卡的 `<target dev=...>` 值以 `-test` 结尾。
- 范围：hypervisor（libvirt）侧全部设备名，覆盖磁盘与网卡两类 `<target dev=...>`。
- 候选落点（待用户在方案确认卡定夺）：
  - 方案 A（XML 输出出口，推荐）：在 `nova/virt/libvirt/config.py` 的 `format_dom()` 输出 `<target dev=...>` 处对 `target_dev` 追加后缀，涉及 `LibvirtConfigGuestDisk`、`LibvirtConfigGuestSnapshotDisk`、`LibvirtConfigGuestInterface`（实测三处，约 `config.py:786/1030/1352`）。改动集中在 1 个文件、可逆，不改内部 mapping 与宿主机 tap 设备名。
  - 方案 B（设备名生成源头）：在 `blockinfo.find_disk_dev_for_disk_bus()` 与 `vif.get_vif_devname()` 的返回值追加后缀。全链路一致，但会改变宿主机 tap 设备名、影响内部按 dev 名查找（detach/snapshot 等），改动面更大。
- 后缀形式（待确认）：后缀（`vda` → `vda-test`）还是前缀（`vda` → `test-vda`）。默认按用户需求描述取后缀。
- 依赖：Python 3、oslo.config、lxml；单测入口 `nova/tests/unit/virt/libvirt/test_config.py`（已确认存在）。
- 风险等级：中。理由：改动 domain XML 契约，影响 libvirt 对设备名的合法性校验，且涉及多个 XML 输出点；不涉及数据迁移/计费/并发一致性。

## 调用链与兼容性

- 磁盘：`driver._get_guest_disk_config()`（`driver.py:3634`）→ `disk.libvirt_info(...)`（`driver.py:3655`）→ `config.LibvirtConfigGuestDisk.target_dev` → `formatXML()`（`config.py:771`）→ `<target dev=...>`。
- 网卡：`vif.get_vif_devname()`（`vif.py:96`）→ `designer.set_vif_host_backend_*_config()`（`designer.py:41/51/74/93/113`）→ `config.LibvirtConfigGuestInterface.target_dev` → `format_dom()`（约 `config.py:1352`）→ `<target dev=...>`。
- 快照磁盘：`config.LibvirtConfigGuestSnapshotDisk.format_dom()`（约 `config.py:1030`）→ `<target dev=...>`。
- 兼容性：追加 `-test` 后设备名不再是 `vd[a-z]` / `tap...` 的常规形式，libvirt 可能拒绝 domain 定义或 guest 无法识别；本需求面向测试/演示场景，需在确认时让用户知悉该影响。方案 A 不改内部 `target_dev` 值，只改 XML 输出，回滚影响最小。
- 副作用时机：仅在生成 domain XML 时追加；不涉及数据库、网络或存储写入。
- 回滚：删除追加后缀的辅助逻辑并提交 revert 即可；无数据迁移，不需要状态回滚。

## UT 设计

测试位置：`nova/tests/unit/virt/libvirt/test_config.py`（参考现有 `LibvirtConfigGuestDiskTest`，`test_config.py:549`）。

- U1（磁盘正向）：`LibvirtConfigGuestDisk.target_dev='vda'` → formatXML 后断言 `<target dev='vda-test'>`。
- U2（网卡正向）：`LibvirtConfigGuestInterface.target_dev='tapabc'` → formatXML 后断言 `<target dev='tapabc-test'>`。
- U3（快照磁盘正向）：`LibvirtConfigGuestSnapshotDisk.target_dev='vda'` → format_dom 后断言 `<target dev='vda-test'>`。
- U4（逆向）：不注入后缀逻辑前，原有 `test_config.py` 全量通过（Red 基线）。
- U5（边界/幂等）：`target_dev` 已以 `-test` 结尾时不重复追加。
- U6（边界/空值）：`target_dev` 为 `None` 或空串时不抛异常、不输出非法 `dev`。
- U7（Unicode）：设备名含非 ASCII 字符时按 UTF-8 追加后缀，断言无异常且结果含 `-test`。
- U8（路径形式）：`target_dev='/dev/hda'`（现有测试形式）→ 断言 `<target dev='/dev/hda-test'>`。

## IT 设计（六步适用）

- `execution.json` 中 deploy/it 均未配置，按 builtin-policy 自动 SKIPPED（零耗时，创建任务时已记录决定），不编造环境。
- 真实 libvirt/KVM 创建 VM 的端到端验证未配置，属未验证边界；若用户后续提供环境与命令，可按 U1–U3 的 XML 断言补做 IT。

## 风险与完成结论

- 待用户确认：改动落点（A/B）、后缀形式。确认前不写业务源码。
- 未覆盖边界：真实 libvirt 环境未验证；带 `-test` 的设备名是否被 libvirt 接受未验证。
- 兜底：若 libvirt 拒绝带 `-test` 的设备名，按用户确认调整形式或落点。
- 适用测试已先于实现设计（Red 基线 U4 → Green U1/U2/U3 → 边界 U5–U8）。

## 知识库证据

- 实际读取：`nova/nova/virt/libvirt/config.py`（`config.py:771/1015/1335`）、`blockinfo.py`（`blockinfo.py:95/112/165`）、`vif.py`（`vif.py:96/101`）、`designer.py`、`driver.py`（`driver.py:3634/3655`）、`nova/tests/unit/virt/libvirt/test_config.py`（`test_config.py:549`）与 `test_blockinfo.py`/`test_vif.py` 文件清单。
- 测试入口核验：`tox.ini:29` 使用 `ostestr`；单测文件存在，断言形式与现有用例一致。
- 受影响文档：系统默认 SOP，无仓库内 `.wally/docs/`；现有 `README.rst`/`doc/` 预计无需更新，待 03 Docs 按实际 diff 复查。
- 缺口：落点与后缀形式待方案确认卡确认，不凭猜测实现。
