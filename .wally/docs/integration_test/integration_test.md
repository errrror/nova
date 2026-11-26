# Integration testing (static verification only)

Prepared from repository files only; no build, deployment, test or verification command was executed. Status: `pending` (see `it.gaps` in `.wally/config.json`).

## Sources inspected

`doc/source/contributor/testing.rst`, `tox.ini`, `.testr.conf`, `HACKING.rst`, `devstack/tempest-dsvm-*-rc`, `gate/`, `tools/test-setup.sh`, `setup.cfg`. No Dockerfile, Compose file, Makefile or CI pipeline definition exists in this repository.

## Real runners found

- Integration tests are the Tempest suite against a full live OpenStack deployment, typically deployed with DevStack (`doc/source/contributor/testing.rst`). Tempest is a separate repository; no Tempest runner command or configuration exists here.
- In-repo `tox -e functional` (`OS_TEST_PATH=./nova/tests/functional`) runs isolated functional tests with a WSGI app, services and a database; these are not integration tests against a live cloud.
- Unit tests `tox` / `tox -e py27,py35` (`OS_TEST_PATH=./nova/tests/unit`, `tools/test-setup.sh` for DB prerequisites) are not a substitute for IT.
- `devstack/tempest-dsvm-*-rc` files only set `DEVSTACK_GATE_TEMPEST_REGEX` for OpenStack CI jobs.

## Success criteria

Not defined in this repository. There are no in-repo gate thresholds or pass/fail definition for a Tempest run; `doc/source/contributor/testing.rst` describes strategy only.

## Gaps blocking activation

No in-repo IT command, no target live environment/endpoint, no credential acquisition method, no concrete measurable success criteria. This guide path alone must not activate the phase.
