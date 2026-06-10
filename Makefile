# Host: GCP targets run inside the `deploy` service (gcloud/docker see /root in the container).
# Inside that container: pass IN_CONTAINER=1 (set automatically by the wrappers below).
RUFF_IMAGE ?= ghcr.io/astral-sh/ruff:latest
COMPOSE_SA := -f docker-compose.yml -f docker-compose.gcp-sa.yml
RUN_DEPLOY := docker compose run --rm -e IN_CONTAINER=1 deploy

.PHONY: docker-push deploy-job deploy-scheduler deploy job-run build-local run-local \
	ruff-docker-check ruff-docker-format deploy-compose-sa

# --- Local app image (Docker Compose service avatar-job) ---
build-local:
	@test -f vacations.json || cp vacations.example.json vacations.json
	docker compose build avatar-job

run-local:
	@test -f vacations.json || cp vacations.example.json vacations.json
	docker compose run --rm avatar-job

# --- Ruff via Docker (no local ruff install) ---
ruff-docker-check:
	docker run --rm -v "$(CURDIR):/work" -w /work $(RUFF_IMAGE) \
	    check src scripts

ruff-docker-format:
	docker run --rm -v "$(CURDIR):/work" -w /work $(RUFF_IMAGE) \
	    format src scripts

# --- GCP: one-shot deploy inside container (reads COMPOSE_FILE from .env if set) ---
deploy-compose-sa:
	docker compose $(COMPOSE_SA) run --rm -e IN_CONTAINER=1 deploy $(MAKE) deploy

ifeq ($(IN_CONTAINER),1)

docker-push:
	bash scripts/docker-push.sh

deploy-job:
	bash scripts/deploy-job.sh

deploy-scheduler:
	bash scripts/deploy-scheduler.sh

job-run:
	bash scripts/job-run.sh

deploy: docker-push deploy-job deploy-scheduler

else

docker-push:
	$(RUN_DEPLOY) $(MAKE) docker-push

deploy-job:
	$(RUN_DEPLOY) $(MAKE) deploy-job

deploy-scheduler:
	$(RUN_DEPLOY) $(MAKE) deploy-scheduler

job-run:
	$(RUN_DEPLOY) $(MAKE) job-run

deploy:
	$(RUN_DEPLOY) $(MAKE) docker-push deploy-job deploy-scheduler

endif
