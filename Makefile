SHELL=/bin/bash
DATETIME:=$(shell date -u +%Y%m%dT%H%M%SZ)

ECR_NAME_DEV:=archival-packaging-tool-dev
ECR_URL_DEV:=222053980223.dkr.ecr.us-east-1.amazonaws.com/archival-packaging-tool-dev
FUNCTION_DEV:=archival-packaging-tool-dev
CPU_ARCH ?= $(shell cat .aws-architecture 2>/dev/null || echo "linux/amd64")

# Local SAM requests use these optional values from .env when present.
-include .env

.PHONY: help install venv update test coveralls lint lint-fix security check-arch dist-dev publish-dev docker-clean sam-build sam-invoke sam-http-run sam-http-ping update-lambda-dev dist-stage publish-stage update-lambda-stage

help: # Preview Makefile commands
	@awk 'BEGIN { FS = ":.*#"; print "Usage:  make <target>\n\nTargets:" } \
/^[-_[:alpha:]]+:.?*#/ { printf "  %-20s%s\n", $$1, $$2 }' $(MAKEFILE_LIST)

##############################################
# Python Environment and Dependency commands
##############################################

install: .venv .git/hooks/pre-commit .git/hooks/pre-push # Install Python dependencies and hooks
	uv sync --dev

.venv: # Create the Python virtual environment
	@echo "Creating virtual environment at .venv..."
	uv venv .venv

.git/hooks/pre-commit: # Install the pre-commit hook
	uv run pre-commit install --hook-type pre-commit

.git/hooks/pre-push: # Install the pre-push hook
	uv run pre-commit install --hook-type pre-push

venv: .venv # Create the Python virtual environment

update: # Update Python dependencies
	uv lock --upgrade
	uv sync --dev

######################
# Unit test commands
######################

test: # Run tests and print a coverage report
	uv run coverage run --source=apt -m pytest -vv
	uv run coverage report -m

coveralls: test # Write coverage data to an LCOV report
	uv run coverage lcov -o ./coverage/lcov.info

####################################
# Code linting and formatting
####################################

lint: # Run formatting, type, and lint checks without changes
	uv run ruff format --diff
	uv run mypy .
	uv run ruff check .

lint-fix: # Apply formatting and supported lint fixes
	uv run ruff format .
	uv run ruff check --fix .

security: # Run dependency vulnerability checks
	uv run pip-audit

###############################################
# Docker image, ECR, and Lambda Management
###############################################

check-arch: # Validate the requested architecture and derive the image tag
	@ARCH_FILE=".aws-architecture"; \
	if [[ "$(CPU_ARCH)" != "linux/amd64" && "$(CPU_ARCH)" != "linux/arm64" ]]; then \
		echo "Invalid CPU_ARCH: $(CPU_ARCH)"; exit 1; \
	fi; \
	if [[ -f $$ARCH_FILE ]]; then \
		echo "latest-$(shell echo $(CPU_ARCH) | cut -d'/' -f2)" > .arch_tag; \
	else \
		echo "latest" > .arch_tag; \
	fi

dist-dev: check-arch # Build the development container image
	@ARCH_TAG=$$(cat .arch_tag); \
	docker buildx inspect $(ECR_NAME_DEV) >/dev/null 2>&1 || docker buildx create --name $(ECR_NAME_DEV) --use; \
	docker buildx use $(ECR_NAME_DEV); \
	docker buildx build --platform $(CPU_ARCH) \
		--load \
		--tag $(ECR_URL_DEV):$$ARCH_TAG \
		--tag $(ECR_URL_DEV):make-$$ARCH_TAG \
		--tag $(ECR_URL_DEV):make-$(shell git describe --always) \
		--tag $(ECR_NAME_DEV):$$ARCH_TAG \
		.

publish-dev: dist-dev # Build, tag, and push the development image
	@ARCH_TAG=$$(cat .arch_tag); \
	aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(ECR_URL_DEV); \
	docker push $(ECR_URL_DEV):$$ARCH_TAG; \
	docker push $(ECR_URL_DEV):make-$$ARCH_TAG; \
	docker push $(ECR_URL_DEV):make-$(shell git describe --always); \
	echo "Cleaning up dangling Docker images..."; \
	docker image prune -f --filter "dangling=true"

docker-clean: # Clean up Docker artifacts
	@ARCH_TAG=$$(cat .arch_tag 2>/dev/null || echo latest); \
	echo "Cleaning up Docker leftovers (containers, images, builders)"; \
	docker rmi -f $(ECR_URL_DEV):$$ARCH_TAG || true; \
	docker rmi -f $(ECR_URL_DEV):make-$$ARCH_TAG || true; \
	docker rmi -f $(ECR_URL_DEV):make-$(shell git describe --always) || true; \
	docker rmi -f $(ECR_NAME_DEV):$$ARCH_TAG || true; \
	docker buildx rm $(ECR_NAME_DEV) || true
	@rm -f .arch_tag

####################################
# SAM Lambda
####################################

sam-build: # Build the Lambda image for local SAM use
	sam build --template tests/sam/template.yaml

sam-invoke: # Invoke the Lambda directly with a sample event
	echo '{"msg":"in a bottle"}' | sam local invoke -e -

sam-http-run: # Run the Lambda locally as an HTTP server
	sam local start-api --template tests/sam/template.yaml --env-vars tests/sam/env.json

sam-http-ping: # Send a sample HTTP request to local SAM
	curl --location 'http://localhost:3000/apt' \
		--header 'Content-Type: application/json' \
		--data '{"action":"ping","challenge_secret":"$(CHALLENGE_SECRET)","verbose":true}'

update-lambda-dev: # Update the development Lambda with the latest image
	aws lambda update-function-code --function-name $(FUNCTION_DEV) --image-uri $(ECR_URL_DEV):latest

# Retained emergency Stage publishing shortcuts. Stage ECR and function values are supplied by the operator.
dist-stage: check-arch # Only use in an emergency
	@ARCH_TAG=$$(cat .arch_tag); \
	docker buildx build --platform $(CPU_ARCH) \
		--load \
		--tag $(ECR_URL_STAGE):$$ARCH_TAG \
		--tag $(ECR_URL_STAGE):make-$$ARCH_TAG \
		--tag $(ECR_URL_STAGE):make-$(shell git describe --always) \
		--tag $(ECR_NAME_STAGE):$$ARCH_TAG \
		.

publish-stage: dist-stage # Only use in an emergency
	@ARCH_TAG=$$(cat .arch_tag); \
	aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(ECR_URL_STAGE); \
	docker push $(ECR_URL_STAGE):$$ARCH_TAG; \
	docker push $(ECR_URL_STAGE):make-$$ARCH_TAG; \
	docker push $(ECR_URL_STAGE):make-$(shell git describe --always)

update-lambda-stage: # Only use in an emergency
	aws lambda update-function-code --function-name $(FUNCTION_STAGE) --image-uri $(ECR_URL_STAGE):latest
