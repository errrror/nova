# 2026-11-26_vm-device-name-test

## Meta

| 项 | 值 |
|----|----|
| 分支 | `feat/vm-device-name-test` |
| WallyTask | `WallyTask: wally-8c6976e5b5410415-7` |
| SOP 版本 | 2.0 |
| SOP 规则 | sop-runtime/builtin/0ac183662b5491b3/core |
| 项目配置 | .wally/profiles/project.md |
| 流程 | 6 步 |
| 摘要 | 创建虚拟机时为 hypervisor 侧全部设备名（domain XML 的 `<target dev=...>`）追加 `-test` 后缀 |
| 任务类型 | 功能新增 |
| 状态 | 进行中 |
| 创建日期 | 2026-11-26 |
| 负责人 | wally |
| Issue | 无 |
| 风险等级及依据 | 中：改动 domain XML 契约，影响 libvirt 对设备名合法性校验；不涉及数据迁移/计费/并发一致性 |
| 授权范围与停止边界 | 仅改 nova 仓库业务源码；用户已确认方案 A + 后缀形式 + 接受测试场景风险；Commit/Push 需另行授权 |
| 执行位置 / 委托决策 | 本地；无委托 |
| 测试环境 | 未配置：unit 用本地 tox/stestr；Deploy/IT 未配置自动 SKIPPED |

## Progress

- [x] 01. Clarify → [01-clarify.md](./01-clarify.md)
- [x] 02. Plan → [02-plan.md](./02-plan.md)
- [x] 03. Implement + UT + Docs → [03-implement.md](./03-implement.md)
- [x] 04. Deploy [SKIPPED: not configured] → [04-deploy.md](./04-deploy.md)
- [x] 05. IT [SKIPPED: not configured] → [05-it.md](./05-it.md)
- [ ] 06. Review + Commit → [06-review-commit.md](./06-review-commit.md)

## 当前步骤

- 步骤：06. Review + Commit
- 文件：[06-review-commit.md](./06-review-commit.md)
- 上次更新：2026-11-26 20:18:36

## 时间记录

| # | 步骤 | 开始时间 | 结束时间 | 耗时 | 对话轮次 | 备注 |
|---|------|---------|---------|------|---------|------|
| 01 | Clarify | 2026-11-26 20:05:26 | 2026-11-26 20:06:29 | 1m03s | 2 | 术语澄清 + 范围确认；未写业务源码 |
| 02 | Plan | 2026-11-26 20:06:29 | 2026-11-26 20:11:02 | 4m33s | 2 | 方案确认：A / 后缀 / 接受风险；范围只改 nova |
| 03 | Implement + UT + Docs | 2026-11-26 20:11:11 | 2026-11-26 20:18:36 | 7m25s | 2 | TDD Red→Green；7 专项用例通过；真实 test_config.py 170 例 0 失败（22 基线 matcher 误判） |
| 04 | Deploy | 2026-11-26 20:05:41+08:00 | 2026-11-26 20:05:41+08:00 | 0s | 0 | SKIPPED: not configured; decision time, not execution |
| 05 | IT | 2026-11-26 20:05:41+08:00 | 2026-11-26 20:05:41+08:00 | 0s | 0 | SKIPPED: not configured; decision time, not execution |
| 06 | Review + Commit | 2026-11-26 20:18:36 | 2026-11-26 20:19:49 | 1m13s | 1 | 独立 diff 审查通过；提交准备完成，Commit/Push 待用户授权 |

## AI 交互 Token 报告（Commit 阶段生成）

<!-- TOKEN_USAGE_START -->
未生成；启用采集后由报告脚本生成，未启用不表示零消耗。
<!-- TOKEN_USAGE_END -->

## 关键决策备忘

- 分支：`feat/vm-device-name-test`（新建并切换，用户确认）。
- 术语：Nova/libvirt 无设备 `alias` 字段；用户所指「hypervisor 侧设备别名」落地为 domain XML 的 `<target dev=...>`。
- 方案 A（用户确认）：只在 `nova/virt/libvirt/config.py` 的 `formatXML()` 输出 `<target dev=...>` 处追加后缀，不改内部 `target_dev` 值与宿主机 tap 设备名。
- 后缀形式（用户确认）：`vda` → `vda-test`，追加在末尾；幂等（已以 `-test` 结尾不重复追加）。
- 风险接受（用户确认）：仅测试/演示，以 XML 输出断言为准，不保证真实 KVM 能创建成功。
- 范围（用户确认）：只改 nova，不改 cinder/neutron/glance（设备名生成属 nova/libvirt 独有职责）。
- Deploy/IT：未配置，创建任务时已记录 SKIPPED 决定，不编造环境。

## 风险与未验证边界

- 真实 libvirt/KVM 端到端创建未验证（IT 未配置）。
- 带 `-test` 的设备名是否被 libvirt 接受未验证；用户已知悉并接受。
- 方案 A 只改 XML 输出，内部 `target_dev` 仍为原值；按 dev 名查找的后续操作（detach/snapshot）不受影响。

## 提交结果

- 提交准备：完成
- Commit：已执行，commit `db473d6020b55710bb12507e21fb27dcad894d3b`（Message: Add -test suffix to hypervisor device names in domain XML）
- Push：已执行，`feat/vm-device-name-test` → origin（含 2 个业务文件 + 13 个 SOP 产物）
- MR/PR：已创建，GitHub PR #3 → https://github.com/errrror/nova/pull/3 （base: master，state: open）
