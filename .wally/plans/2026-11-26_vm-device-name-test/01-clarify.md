# 01. Clarify

## 目标与成功判据

- 目标：创建虚拟机时，hypervisor（libvirt）侧生成的全部设备名统一带 `-test` 后缀。
- 成功判据：
  - 库函数/单元测试：生成磁盘设备名与网卡设备名的入口在测试输入下均返回以 `-test` 结尾的名字。
  - XML 层：构造出的 domain XML 中，磁盘 `<target dev=...>`、网卡 `<target dev=...>` 的值均以 `-test` 结尾。
  - 反向判据：不改动设备名时现有测试全部通过。

## 范围、约束与依赖

- 仓库：`nova`（OpenStack Nova），基线 `master`，任务分支 `feat/vm-device-name-test`。
- 用户确认的范围：hypervisor 侧全部设备别名（即 libvirt domain XML 中 `<target dev='...'/>` 体现的磁盘与网卡设备名）。
- 约束（来自 AGENTS.md / builtin-policy.md）：
  - 业务源码改动必须先完成 01→02 并获用户确认；本阶段不写业务源码。
  - SQL 参数化、密钥不落库、不硬编码内部地址（本任务不涉及）。
  - 全程简体中文记录。
- 依赖：Python 3 + oslo.config + lxml；测试入口待 Plan 阶段探测（项目为 OpenStack Nova，通常使用 `tox`/`stestr`）。

## 问题与决策

- 术语澄清：用户所说「设备别名」在 Nova/libvirt 代码中没有名为 `alias` 的字段（仓库中 `alias` 仅指 `nova/conf/pci.py` 的 PCI alias 和 setuptools entry point）。经代码核验，hypervisor 侧设备名实际落点是 `nova/virt/libvirt/config.py` 中输出的 XML 属性 `<target dev=...>`（三处：`LibvirtConfigGuestDisk`/`LibvirtConfigGuestSnapshotDisk`/`LibvirtConfigGuestInterface`）。据用户选择「hypervisor 侧全部设备别名」，本任务把该术语落地为 libvirt domain XML 中磁盘与网卡的 `<target dev=...>` 设备名。
- 待用户确认（见方案确认卡）：改动落点（设备名生成源头 vs XML 输出出口）、`-test` 为后缀还是前缀、是否只影响新建 VM。
- 输入来源：用户本轮需求描述 + 对话卡片选择（第 1 题新建 `feat/vm-device-name-test` 分支；第 2 题 hypervisor 侧全部设备别名）。

## 代码事实核验（来源）

- 磁盘设备名生成：`nova/virt/libvirt/blockinfo.py:165` `find_disk_dev_for_disk_bus()`，按总线前缀（virtio→`vd`、ide→`hd` 等，`blockinfo.py:112`）生成 `vda`、`hdc` 等，并由 `has_disk_dev`（`blockinfo.py:95`）去重。
- 网卡设备名生成：`nova/virt/libvirt/vif.py:96` `get_vif_devname()`，取 `vif['devname']` 否则 `nic<id>`；`vif.py:101` `get_vif_devname_with_prefix()`。
- XML 输出：`nova/virt/libvirt/config.py` 的 `LibvirtConfigGuestDisk`（约 `config.py:786`）、`LibvirtConfigGuestSnapshotDisk`（约 `config.py:1030`）、`LibvirtConfigGuestInterface`（约 `config.py:1352`）把 `target_dev` 写成 `<target dev=...>`；`LibvirtConfigGuestHostdev` 不输出 `<target dev>`。
- 磁盘配置装配：`nova/virt/libvirt/driver.py:3634` `_get_guest_disk_config()` 用 `disk_info['dev']` 调用 `disk.libvirt_info(...)` 生成 `conf.target_dev`。

## 缺陷 / 性能输入（适用时）

不适用（功能新增，非缺陷/性能任务）。

## 完成结论

目标可验证；术语与范围已据代码核验落地，改动落点、后缀形式与生效范围待用户在方案确认卡确认后进入 02 Plan。

## 知识库证据

- 实际读取路径：
  - `sop-runtime/builtin/0ac183662b5491b3/core/`（builtin-policy.md / clarify.md / workflow.md / gates.md / interaction.md）
  - `nova/AGENTS.md`（仓库根共享规则）
  - `nova/nova/virt/libvirt/`：`designer.py`、`vif.py`、`blockinfo.py`、`config.py`、`driver.py`
- 源码核验结论：见「代码事实核验」小节；Nova 无 hypervisor 设备 `alias` 字段，设备名以 `<target dev=...>` 为准。
- 受影响文档：本任务不强制新建 `.wally/docs/`（系统默认 SOP）；现有 `README.rst`/`doc/` 预计无需更新，待 03 Docs 阶段按实际 diff 复查。
- 缺口/校验：`-test` 的具体落点与形式待用户确认，不凭猜测实现。
