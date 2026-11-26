# 01. Clarify

## 目标与成功判据

在 nova 新增 `GET /welcome` REST 端点：命中后在 nova 日志打印 `welcome`，并向对端 cinder 的 welcome 端点发起一次 HTTP 调用（携带转发标记）；若请求已带转发标记则只打印、不再回呼，避免无限递归；对端不可达时降级返回成功。

成功判据：
1. `GET /welcome` 返回 200 且响应含 `welcome`。
2. `nova` 日志打印 `welcome`。
3. 无转发标记时调用对端一次；带 `X-Welcome-Forwarded: 1` 时不调用对端。
4. 对端异常时仍返回成功并记录 warning。
5. 对应 UT 全部通过。

## 范围、约束与依赖

范围（`nova` 仓库）：新增 welcome controller、对端地址配置项、路由注册、单元测试。
约束：对端地址走 `oslo.config` 配置项，默认回环地址，不硬编码任何 `*.woa.com` / 内部平台地址；日志沿用 `oslo_log` 的 `LOG.info`；不修改 `AGENTS.md`，不写 `.wally/versions/`。
依赖：仓库 `requirements.txt` 已含 `requests>=2.14.2`，无需新增运行依赖。04/05 未配置，SKIPPED。

## 问题与决策

用户卡片确认：新建分支 `task/welcome-api`；范围含 nova+cinder+awesome-architecture；REST API 端点；相互调用对方接口并在各自日志打印 welcome。
设计取舍（02 Plan 展开并由用户确认方案）：防递归头 `X-Welcome-Forwarded`、对端地址配置项、故障降级。

## 问题判据（缺陷 / 性能任务适用）

功能新增，不适用。

## 完成结论

目标可验证，业务决策已由用户确认，风险为跨组件 HTTP 依赖且已设计降级。

## 知识库证据

系统内置默认 SOP，无仓库内 `.wally/docs/`；已读 `nova` 的 router/routes、controller、LOG 用法、requirements、tox.ini 与现有 UT 样例。实际读取：`nova/nova/api/openstack/compute/routes.py`、`nova/nova/api/openstack/compute/versions.py`、`requirements.txt`、`tox.ini`。无文档变更需求（能力说明由 awesome-architecture 承载）。
