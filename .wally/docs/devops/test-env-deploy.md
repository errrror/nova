# Test environment deployment

Status: static verification only (no build, deploy, or test command was executed). Readiness: pending.

## Verified project facts and sources
- Build/package: `setup.py` + `setup.cfg` (pbr). Runtime: Python 2.7 / 3.5 (`setup.cfg`, `tox.ini`).
- Service entrypoints are console scripts in `setup.cfg [entry_points]`: `nova-api`, `nova-compute`, `nova-scheduler`, `nova-conductor`, `nova-manage`, and related services.
- No `Makefile`, `Dockerfile`, `docker-compose*`, or CI deploy job exists; `.github/` contains only `copilot-instructions.md`.
- Operator install/verify guides: `doc/source/install/controller-install*.rst`, `compute-install*.rst`, `verify.rst`.
- `gate/post_test_hook.sh` runs `nova-manage db archive_deleted_rows` (cleanup, not rollback).

## Gaps blocking deployment activation
- No deploy command or entrypoint exists in the repository.
- No target test environment identifier or owner is defined.
- No credential acquisition procedure: `doc/source/install/verify.rst` assumes an existing `admin-openrc`.
- No versioned rollback target or rollback command is defined.

## Verification (real commands from doc/source/install/verify.rst)
Source an `admin-openrc`. Then run `openstack compute service list` (expected nova services enabled/up), `openstack catalog list`, `openstack image list`, and `nova-status upgrade check` (Cells v2, Placement API, Resource Providers = Success).

## Failure and rollback
No project-defined rollback procedure exists. `gate/post_test_hook.sh` only archives deleted DB rows. Supply a rollback target and command from the environment owner before execution; record environment retention/release ownership.

This guide records static findings only and is not evidence of execution.
