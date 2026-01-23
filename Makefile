# Makefile
# Set default value of ENV to "dev" if not provided
ENV ?= dev
TEST_RUN_ID ?= default

poetryVersion := $(shell cat .github/workflows/.poetry-version)

# Bootstrap the project
# Prerequisites: Activate your Python environment first (e.g., micromamba activate py312)
# This uses in-project virtualenvs so each repo has isolated dependencies in .venv/
# Workflow: micromamba manages Python version, Poetry manages per-project deps
.PHONY: bootstrap
bootstrap:
	pip install --upgrade pip pre-commit poetry==${poetryVersion} poetry-plugin-export
	pre-commit install
	poetry config --local virtualenvs.in-project true
	poetry install
	npm install -g aws-cdk@^2

# Build Lambda code for deployment
# - Exports main dependencies (not dev) to requirements.txt for layer
# - Copies service folder to .build/service for CDK to package
.PHONY: build
build:
	@echo "Building Lambda code..."
	rm -rf .build
	mkdir -p .build/service .build/layer
	@echo "Exporting lambda dependencies to requirements.txt..."
	poetry export --without-hashes -f requirements.txt -o .build/layer/requirements.txt
	cp -r service .build/
	@echo "Build complete!"

.PHONY: synth
synth: build
	ENV=$(ENV) TEST_RUN_ID=$(TEST_RUN_ID) npx cdk synth --app "python perf_app.py" --toolkit-stack-name cdk-bootstrap -c "@aws-cdk/core:bootstrapQualifier=renre"
	@ if [ "$(ENV)" = "dev" ]; then \
		npx cdk-dia; \
	fi

.PHONY: deploy
deploy: build
	ENV=$(ENV) TEST_RUN_ID=$(TEST_RUN_ID) npx cdk deploy --app "python perf_app.py" scenario-1-$(ENV) --toolkit-stack-name cdk-bootstrap -c "@aws-cdk/core:bootstrapQualifier=renre" --require-approval=never

# Destroy resources in dev environment with confirmation
.PHONY: destroy
destroy:
	@read -p "Are you sure you want to destroy the stack? (y/N): " confirm; \
	if [ "$$confirm" = "y" ]; then \
		ENV=$(ENV) npx cdk destroy --app "python perf_app.py" scenario-1-$(ENV) --toolkit-stack-name cdk-bootstrap -c "@aws-cdk/core:bootstrapQualifier=renre"; \
	else \
		echo "Aborted destroy."; \
	fi

# Clean build artifacts
.PHONY: clean
clean:
	rm -rf .build cdk.out

# Run all linting and checking tools
.PHONY: lint
lint: pre-commit

.PHONY: pre-commit
pre-commit:
	pre-commit run --all-files

# Run all linting and checking tools
.PHONY: lint-fix
lint-fix:
	@echo "Running black"
	poetry run black .
	@echo "Running ruff"
	poetry run ruff check --fix

# Python linting with flake8
.PHONY: lint-strict
lint-strict:
	@echo "Running mypy"
	poetry run mypy --pretty cdk tests service


# Snapshot target to update pytest snapshot tests
.PHONY: snapshot-update
snapshot-update:
	poetry run pytest --snapshot-update

# Unit test target
.PHONY: test-unit
test-unit:
	poetry run pytest tests/unit

# =============================================================================
# Performance Testing Targets
# =============================================================================

# Run performance test (sends messages to queue)
.PHONY: run
run:
	poetry run python scripts/run_perf_test.py --messages $(MESSAGES) --env $(ENV)

# Show help
.PHONY: help
help:
	@echo "Commands:"
	@echo ""
	@echo "  make synth                         - Synthesize stack"
	@echo "  make deploy                        - Deploy stack"
	@echo "  make destroy                       - Destroy stack"
	@echo "  make run MESSAGES=100              - Run perf test with N messages"
	@echo ""
	@echo "Environment Variables:"
	@echo "  ENV=dev|prod                       - Target environment (default: dev)"
	@echo "  TEST_RUN_ID=<id>                   - Cost allocation tag for this test run"
	@echo ""
	@echo "Workflow:"
	@echo "  1. Deploy once:  make deploy ENV=dev"
	@echo "  2. Tag test run: TEST_RUN_ID=test-001 make deploy ENV=dev"
	@echo "  3. Run test:     make run MESSAGES=1000 ENV=dev"
	@echo "  4. View costs in AWS Cost Explorer filtered by PerfTestRun tag"
