PYTHON ?= python3
PROJECT_PYTHONPATH ?= src:.python-packages
TOOLS_DIR ?= .tools
TERRAFORM_VERSION ?= $(shell cat .terraform-version)
TERRAFORM_ZIP := $(TOOLS_DIR)/terraform_$(TERRAFORM_VERSION)_linux_amd64.zip
TERRAFORM := $(TOOLS_DIR)/bin/terraform
AWS := $(TOOLS_DIR)/bin/aws

.PHONY: install install-local install-tools aws-version terraform-version test lint format docker-build

install:
	$(PYTHON) -m pip install -e ".[dev]"

install-local:
	$(PYTHON) -m pip install --target .python-packages -e ".[dev]"

install-tools: install-local $(TERRAFORM)
	mkdir -p $(TOOLS_DIR)/bin
	printf '%s\n' '#!/usr/bin/env sh' 'PYTHONPATH=src:.python-packages exec $(PYTHON) -c "import sys; from awscli.clidriver import main; sys.exit(main())" "$$@"' > $(AWS)
	chmod +x $(AWS)

$(TERRAFORM): .terraform-version
	mkdir -p $(TOOLS_DIR)/bin
	curl -fsSL -o $(TERRAFORM_ZIP) https://releases.hashicorp.com/terraform/$(TERRAFORM_VERSION)/terraform_$(TERRAFORM_VERSION)_linux_amd64.zip
	unzip -o $(TERRAFORM_ZIP) -d $(TOOLS_DIR)/bin
	rm -f $(TERRAFORM_ZIP)

aws-version:
	PYTHONPATH=$(PROJECT_PYTHONPATH) $(AWS) --version

terraform-version:
	$(TERRAFORM) version

test:
	PYTHONPATH=$(PROJECT_PYTHONPATH) $(PYTHON) -m pytest

lint:
	PYTHONPATH=$(PROJECT_PYTHONPATH) $(PYTHON) -m ruff check src tests

format:
	PYTHONPATH=$(PROJECT_PYTHONPATH) $(PYTHON) -m ruff check --fix src tests
	PYTHONPATH=$(PROJECT_PYTHONPATH) $(PYTHON) -m ruff format src tests

docker-build:
	docker build -f Dockerfile.listener -t opera-ohip-listener:local .
	docker build -f Dockerfile.consumer -t opera-ohip-consumer:local .
	docker build -f Dockerfile.enricher -t opera-ohip-enricher:local .
	docker build -f Dockerfile.analytics -t opera-ohip-analytics:local .
