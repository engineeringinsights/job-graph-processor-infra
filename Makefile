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
	ENV=$(ENV) TEST_RUN_ID=$(TEST_RUN_ID) npx cdk synth --app "python perf_app.py" --all --toolkit-stack-name cdk-bootstrap -c "@aws-cdk/core:bootstrapQualifier=renre"
	@ if [ "$(ENV)" = "dev" ]; then \
		npx cdk-dia; \
	fi

# Deploy all scenarios (shared VPC + scenario 1 + scenario 2)
.PHONY: deploy
deploy: build
	ENV=$(ENV) TEST_RUN_ID=$(TEST_RUN_ID) npx cdk deploy --app "python perf_app.py" --all --toolkit-stack-name cdk-bootstrap -c "@aws-cdk/core:bootstrapQualifier=renre" --require-approval=never

.PHONY: deploy-lambda
deploy-lambda: build
	ENV=$(ENV) TEST_RUN_ID=$(TEST_RUN_ID) npx cdk deploy --app "python perf_app.py" scenario-1-$(ENV) --toolkit-stack-name cdk-bootstrap -c "@aws-cdk/core:bootstrapQualifier=renre" --require-approval=never

# Destroy scenario 1 (Lambda) resources with confirmation
.PHONY: destroy-lambda
destroy-lambda:
	@read -p "Are you sure you want to destroy the scenario-1 stack? (y/N): " confirm; \
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

# Run performance test for scenario 1 (Lambda)
.PHONY: run
run:
	poetry run python scripts/run_perf_test.py --messages $(MESSAGES) --env $(ENV) --scenario 1

# Run performance test for scenario 2 (ECS)
.PHONY: run-ecs
run-ecs:
	poetry run python scripts/run_perf_test.py --messages $(MESSAGES) --env $(ENV) --scenario 2

# =============================================================================
# Scenario 2 (ECS Fargate) Targets
# =============================================================================

# Default scaling values
DESIRED_COUNT ?= 1

# Deploy scenario 2 (includes VPC + ECS)
.PHONY: deploy-ecs
deploy-ecs: build
	ENV=$(ENV) TEST_RUN_ID=$(TEST_RUN_ID) npx cdk deploy --app "python perf_app.py" perf-shared-$(ENV) scenario-2-$(ENV) --toolkit-stack-name cdk-bootstrap -c "@aws-cdk/core:bootstrapQualifier=renre" --require-approval=never

# Destroy scenario 2
.PHONY: destroy-ecs
destroy-ecs:
	@read -p "Are you sure you want to destroy scenario-2 stack? (y/N): " confirm; \
	if [ "$$confirm" = "y" ]; then \
		ENV=$(ENV) npx cdk destroy --app "python perf_app.py" scenario-2-$(ENV) --toolkit-stack-name cdk-bootstrap -c "@aws-cdk/core:bootstrapQualifier=renre"; \
	else \
		echo "Aborted destroy."; \
	fi

# Scale ECS service up (start processing)
.PHONY: scale-up
scale-up:
	@echo "Scaling scenario-2-$(ENV)-service to $(DESIRED_COUNT) tasks..."
	aws ecs update-service \
		--cluster scenario-2-$(ENV)-cluster \
		--service scenario-2-$(ENV)-service \
		--desired-count $(DESIRED_COUNT) \
		--query 'service.desiredCount' \
		--output text
	@echo "Service scaled to $(DESIRED_COUNT) tasks"

# Scale ECS service down (stop all tasks)
.PHONY: scale-down
scale-down:
	@echo "Scaling scenario-2-$(ENV)-service to 0 tasks..."
	aws ecs update-service \
		--cluster scenario-2-$(ENV)-cluster \
		--service scenario-2-$(ENV)-service \
		--desired-count 0 \
		--query 'service.desiredCount' \
		--output text
	@echo "Service scaled to 0 tasks"

# Check ECS service status
.PHONY: ecs-status
ecs-status:
	@echo "ECS Service Status for scenario-2-$(ENV):"
	@aws ecs describe-services \
		--cluster scenario-2-$(ENV)-cluster \
		--services scenario-2-$(ENV)-service \
		--query 'services[0].{DesiredCount:desiredCount,RunningCount:runningCount,PendingCount:pendingCount,Status:status}' \
		--output table

# Run the External Scheduler (job graph workflow)
.PHONY: run-scheduler
run-scheduler:
	poetry run python scripts/run_scheduler.py --env $(ENV)

# Show help
.PHONY: help
help:
	@echo "Commands:"
	@echo ""
	@echo "  make synth                         - Synthesize all stacks"
	@echo "  make deploy                        - Deploy all scenarios (Lambda + ECS)"
	@echo "  make deploy-lambda                 - Deploy scenario 1 (Lambda) only"
	@echo "  make deploy-ecs                    - Deploy scenario 2 (ECS) only"
	@echo "  make destroy-lambda                - Destroy scenario 1 (Lambda)"
	@echo "  make destroy-ecs                   - Destroy scenario 2 (ECS)"
	@echo "  make run MESSAGES=100              - Run perf test with N messages (scenario 1)"
	@echo "  make run-ecs MESSAGES=100          - Run perf test with N messages (scenario 2)"
	@echo "  make scale-up DESIRED_COUNT=2      - Scale ECS service up"
	@echo "  make scale-down                    - Scale ECS service to 0"
	@echo "  make ecs-status                    - Check ECS service status"
	@echo "  make run-scheduler                 - Run job graph scheduler"
	@echo ""
	@echo "Environment Variables:"
	@echo "  ENV=dev|prod                       - Target environment (default: dev)"
	@echo "  TEST_RUN_ID=<id>                   - Cost allocation tag for this test run"
	@echo "  DESIRED_COUNT=N                    - Number of ECS tasks (default: 1)"
	@echo ""
	@echo "Workflow:"
	@echo "  1. Deploy all:   make deploy ENV=dev"
	@echo "  2. Tag test run: TEST_RUN_ID=test-001 make deploy ENV=dev"
	@echo "  3. Run test:     make run MESSAGES=1000 ENV=dev"
	@echo "  4. Or run graph: make run-scheduler ENV=dev"
	@echo "  5. View costs in AWS Cost Explorer filtered by PerfTestRun tag"
