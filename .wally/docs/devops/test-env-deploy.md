# Test environment deployment

> 静态核验：仅读取仓库文件，未执行构建/部署/测试。对象：nova（基线 master）。

## 发现（来源）

- `README.rst`：部署与配置指南指向外部 `https://docs.openstack.org/nova/`；仓库内无测试环境部署脚本、Makefile、Compose 或 Dockerfile。
- `setup.cfg` console_scripts 提供 `nova-api`、`nova-compute`、`nova-scheduler`、`nova-conductor`、`nova-manage` 等服务入口，但无配套部署配置或启动命令。
- `gate/` 为 OpenStack infra CI hook（`post_test_hook.sh` 仅执行 db archive）；`devstack/` 仅含外部 tempest-dsvm job 的测试选择 rc 脚本。二者均非可执行的部署入口。

## 缺口

- 仓库内无真实测试环境部署 command；部署依赖外部 devstack，目标环境标识/负责人/授权边界未指定。
- 未提供凭证获取方式（无 in-repo openrc / 凭证样例）。
- 未定义 verify、rollback 命令与触发条件、有效版本核对与健康检查验收判据。

因此 `deploy.readiness = pending`；执行前须补齐，不得猜测命令。
