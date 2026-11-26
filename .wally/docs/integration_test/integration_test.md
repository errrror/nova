# Integration testing

Status: static verification only (no test command was executed). Readiness: pending.

## Verified project facts and sources
- Test runner: tox + testr/os-testr (`tox.ini`, `.testr.conf`, `test-requirements.txt`).
- Real local entrypoint: `tox -e functional` (`OS_TEST_PATH=./nova/tests/functional`, `tox.ini:57-67`). Unit layers: `tox`, `tox -e py27`, `tox -e py35` (HACKING.rst, "Running Tests").
- DB fixture setup: `tools/test-setup.sh` creates the MySQL/PostgreSQL `openstack_citest` user and database.
- Real integration jobs: Tempest through devstack (`devstack/tempest-dsvm-*-rc`, `gate/`). The rc files export `DEVSTACK_GATE_TEMPEST_REGEX` and `DEVSTACK_LOCAL_CONFIG`.

## Gaps blocking IT activation
- No runnable integration target environment is defined in the repository; Tempest jobs depend on an external devstack/OpenStack deployment.
- No credential acquisition method for Tempest/admin access: `tempest.conf` and `admin-openrc` are produced outside this repository.
- `tox -e functional` is a real local test entrypoint but is a functional suite, not end-to-end verification against a deployed cloud.

## Success criteria
`tox -e functional` exits 0 with no failed tests and a non-empty, non-all-skipped result. For Tempest runs, every case selected by `devstack/tempest-dsvm-*-rc` must pass. Distinguish assertion, environment, and execution errors; empty or all-skipped runs are not passes. For defect A/B verification retain comparable before/after evidence.

## Cleanup and evidence
Retain testr/subunit output, executed command, code version, environment identifiers, and conclusion. Clean up fixture data created by `tools/test-setup.sh` when the environment is released.

Static findings only; not evidence of execution.
