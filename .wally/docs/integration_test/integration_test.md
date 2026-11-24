# Integration testing

> 静态核验：仅读取仓库文件，未执行测试。对象：nova（基线 master）。

## 真实入口与来源

- `tox.ini` `[testenv:functional]`（py2.7）与 `[testenv:functional-py35]`（py3.5）：`OS_TEST_PATH=./nova/tests/functional`，底层命令 `ostestr`；入口 `tox -e functional`。
- `devstack/tempest-dsvm-*-rc`：仅用于外部 OpenStack CI job 设置 `DEVSTACK_GATE_TEMPEST_REGEX`，仓库内无 `tempest run` 入口；`setup.cfg` 未注册 tempest 插件。
- `test-requirements.txt`、`tests-py3.txt`、`tests-functional-py3.txt` 定义测试依赖。

## 缺口与判据

- `tox -e functional` 为仓库内 functional 测试，不等同于对已部署环境的端到端 Tempest IT。
- 未定义集成测试目标环境、认证/配置获取方式、数据准备与隔离、通过标准、失败分类、清理与证据位置。
- 因此 `it.readiness = pending`、`success_criteria` 暂缺；执行前须补齐，不得猜测命令或声称通过。
