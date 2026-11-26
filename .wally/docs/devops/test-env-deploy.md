# Test environment deployment (static verification only)

Prepared from repository files only; no build, deployment, test or verification command was executed. Status: `pending` (see `deploy.gaps` in `.wally/config.json`).

## Sources inspected

`README.rst`, `setup.cfg`, `tox.ini`, `doc/source/install/` (`verify.rst`, `controller-install-*`, `compute-install-*`), `doc/source/cli/nova-manage.rst`, `doc/source/cli/nova-status.rst`, `doc/source/contributor/development-environment.rst`, `gate/`, `devstack/`. No Dockerfile, Compose file, Makefile or CI pipeline definition exists in this repository.

## Real deployment entry points found

Nova is an OpenStack service installed from OS packages and configured under `/etc/nova/`; there is no single in-repo deploy command.

- Service entry points (`setup.cfg` -> `console_scripts`): `nova-api`, `nova-api-metadata`, `nova-compute`, `nova-scheduler`, `nova-conductor`, `nova-consoleauth`, `nova-novncproxy`, `nova-spicehtml5proxy`, `nova-status`, `nova-manage`; WSGI: `nova-placement-api`, `nova-api-wsgi`, `nova-metadata-wsgi`.
- Schema setup on the controller (`doc/source/install/controller-install-*.rst`): `su -s /bin/sh -c "nova-manage db sync" nova`, plus `nova-manage api_db sync` and cells v2 setup `nova-manage cell_v2 simple_cell_setup`.
- Services are started by the host init system after packages and `/etc/nova/nova.conf` are in place.
- DevStack is referenced for a full dev/test cloud (`doc/source/contributor/development-environment.rst`) but lives in an external repository; no `local.conf` exists here.

## Verification (documented, not executed)

After sourcing admin credentials (`. admin-openrc`), `doc/source/install/verify.rst` specifies `openstack compute service list` (services enabled and `up`), `openstack catalog list` (identity/image/compute/placement endpoints), `openstack image list` (active image visible), and `nova-status upgrade check` (Cells v2 / Placement API / Resource Providers = Success).

## Failure and rollback

No rollback procedure or rollback command is documented. `nova-manage db` (`doc/source/cli/nova-manage.rst`) offers only `db version`, `db sync [--version]`, `db archive_deleted_rows`, and `null_instance_uuid_scan`; `db archive_deleted_rows` is the sole cleanup command referenced by `gate/post_test_hook.sh`. There is no versioned deployment rollback in this repository.

## Gaps blocking activation

No project-owned deploy command, no target test environment, no credential acquisition method, no documented rollback. This guide path alone must not activate the phase.
