# Build and run the avatar job with the project Dockerfile.
# Requires Docker. Create `.env` before running (see README).

IMAGE_NAME ?= auto-slack-avatar
IMAGE_TAG ?= latest
IMAGE := $(IMAGE_NAME):$(IMAGE_TAG)

# Prefer repo venv binary when present; override with make lint RUFF=/path/to/ruff
ifneq (,$(wildcard $(CURDIR)/.venv/bin/ruff))
	RUFF := $(CURDIR)/.venv/bin/ruff
else
	RUFF ?= ruff
endif

.PHONY: default help build run lint

default: run

help:
	@echo "Targets:"
	@echo "  make / make run  Build image and run one shot (same mounts as compose)"
	@echo "  make build       Build the Docker image only"
	@echo "  make lint        Run Ruff linter (ruff check) on src/"

build:
	docker build -t $(IMAGE) .

lint:
	$(RUFF) check "$(CURDIR)/src"

run: build
	docker run --rm \
		--env-file .env \
		-e TZ=$${TZ:-UTC} \
		-v "$(CURDIR)/assets/images:/app/assets/images:ro" \
		-v "$(CURDIR)/prompts.json:/app/prompts.json:ro" \
		-v "$(CURDIR)/output:/app/output:rw" \
		$(IMAGE)
