# Makefile
# Set default value of ENV to "dev" if not provided
ENV ?= dev

poetryVersion := $(shell cat .github/workflows/.poetry-version)

# Bootstrap the project
# Prerequisites: Activate your Python environment first (e.g., micromamba activate py313)
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
	ENV=$(ENV) npx cdk synth --app "python app.py" --toolkit-stack-name cdk-bootstrap -c "@aws-cdk/core:bootstrapQualifier=myproject"
	@ if [ "$(ENV)" = "dev" ]; then \
		npx cdk-dia; \
	fi

.PHONY: deploy
deploy: build
	ENV=$(ENV) npx cdk deploy --app "python app.py" --all --toolkit-stack-name cdk-bootstrap -c "@aws-cdk/core:bootstrapQualifier=myproject" --require-approval=never

# Destroy resources in dev environment with confirmation
.PHONY: destroy-dev
destroy-dev:
	@read -p "Are you sure you want to destroy the dev environment? (y/N): " confirm; \
	if [ "$$confirm" = "y" ]; then \
		ENV=dev npx cdk destroy --app "python app.py" --all --toolkit-stack-name cdk-bootstrap -c "@aws-cdk/core:bootstrapQualifier=myproject"; \
	else \
		echo "Aborted destroy for dev environment."; \
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
