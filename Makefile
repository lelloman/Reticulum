all: release

test:
	@echo Running tests...
	python3 -m tests.all

test-e2e:
	@echo Running E2E tests...
	python3 -m tests.e2e.runner

test-vectors:
	@echo Running vector tests only...
	python3 -m tests.e2e.runner --vectors-only

test-interop:
	@echo Running interoperability tests...
	python3 -m tests.e2e.runner --interop

# E2E Docker tests - real network testing with multiple nodes
test-e2e-docker-build:
	@echo Building Docker E2E test environment...
	cd tests/e2e/docker && SHARD=0 docker compose -p rns-e2e-0 build

test-e2e-docker-up: test-e2e-docker-build
	@echo Starting Docker E2E test environment...
	cd tests/e2e/docker && SHARD=0 docker compose -p rns-e2e-0 up -d transport node-a node-c
	@echo Waiting for nodes to become healthy...
	@sleep 5
	@docker exec rns-node-a-0 rnstatus || true
	@docker exec rns-node-c-0 rnstatus || true

test-e2e-docker-down:
	@echo Stopping Docker E2E test environment...
	cd tests/e2e/docker && SHARD=0 docker compose -p rns-e2e-0 down -v

test-e2e-docker: test-e2e-docker-up
	@echo Running Docker E2E tests...
	SHARD=0 docker compose -f tests/e2e/docker/docker-compose.yml -p rns-e2e-0 run --rm --entrypoint "python -m pytest tests/e2e/scenarios/ -v --tb=short" test-runner || true
	$(MAKE) test-e2e-docker-down

test-e2e-docker-run:
	@echo Running Docker E2E tests (environment must be up)...
	SHARD=0 python3 -m pytest tests/e2e/scenarios/ -v --tb=short

test-e2e-docker-logs:
	cd tests/e2e/docker && SHARD=0 docker compose -p rns-e2e-0 logs -f

test-e2e-docker-shell-a:
	docker exec -it rns-node-a-$${SHARD:-0} /bin/bash

test-e2e-docker-shell-c:
	docker exec -it rns-node-c-$${SHARD:-0} /bin/bash

test-e2e-docker-shell-transport:
	docker exec -it rns-transport-$${SHARD:-0} /bin/bash

test-e2e-docker-parallel:
	@echo Running parallel Docker E2E tests...
	./tests/e2e/run_parallel.sh

clean:
	@echo Cleaning...
	@-rm -rf ./build
	@-rm -rf ./dist
	@-rm -rf ./*.data
	@-rm -rf ./__pycache__
	@-rm -rf ./RNS/__pycache__
	@-rm -rf ./RNS/Cryptography/__pycache__
	@-rm -rf ./RNS/Cryptography/aes/__pycache__
	@-rm -rf ./RNS/Cryptography/pure25519/__pycache__
	@-rm -rf ./RNS/Interfaces/__pycache__
	@-rm -rf ./RNS/Utilities/__pycache__
	@-rm -rf ./RNS/vendor/__pycache__
	@-rm -rf ./RNS/vendor/i2plib/__pycache__
	@-rm -rf ./tests/__pycache__
	@-rm -rf ./tests/e2e/__pycache__
	@-rm -rf ./tests/e2e/interfaces/__pycache__
	@-rm -rf ./tests/e2e/utils/__pycache__
	@-rm -rf ./tests/e2e/scenarios/__pycache__
	@-rm -rf ./tests/e2e/helpers/__pycache__
	@-rm -rf ./tests/e2e/scripts/__pycache__
	@-rm -rf ./tests/e2e/docker/results
	@-rm -rf ./tests/rnsconfig/storage
	@-rm -rf ./*.egg-info
	@make -C docs clean
	@echo Done

purge_docs:
	@echo Purging documentation build...
	@-rm -rf ./docs/manual
	@-rm -rf ./docs/*.pdf
	@-rm -rf ./docs/*.epub

remove_symlinks:
	@echo Removing symlinks for build...
	-rm Examples/RNS
	-rm RNS/Utilities/RNS

create_symlinks:
	@echo Creating symlinks...
	-ln -s ../RNS ./Examples/
	-ln -s ../../RNS ./RNS/Utilities/

build_sdist: purge_docs
	python3 setup.py sdist

build_wheel:
	python3 setup.py bdist_wheel

build_pure_wheel:
	python3 setup.py bdist_wheel --pure

documentation:
	make -C docs html

manual:
	make -C docs latexpdf epub

build_spkg: remove_symlinks build_sdist create_symlinks

release: test remove_symlinks build_sdist build_wheel build_pure_wheel documentation manual create_symlinks

debug: remove_symlinks build_wheel build_pure_wheel create_symlinks

upload:
	@echo Ready to publish release, hit enter to continue
	@read VOID
	@echo Uploading to PyPi...
	twine upload dist/*
	@echo Release published
