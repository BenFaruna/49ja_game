# ==================================================================================== #
# HELPERS
# ==================================================================================== #

## help: print this help message
.PHONY: help
help:
	@echo 'Usage:'
	@sed -n 's/^##//p' ${MAKEFILE_LIST} | column -t -s ':' | sed -e 's/^/ /'


# ==================================================================================== #
# DEVELOPMENT
# ==================================================================================== #

## dev: runs the application in development mode
.PHONY: dev
run:
	@echo "starting server..."
	gunicorn app:app --reload

# ==================================================================================== #
# DEPLOYMENT
# ==================================================================================== #

## pull: pull latest changes from remote
.PHONY: pull
pull:
	git pull origin main

## deploy: deploy the application to remote server using docker compose
.PHONY: deploy
deploy:
	docker compose up -d --build

## deploy-podman: deploy the application to remote server using podman compose
.PHONY: deploy-podman
deploy-podman:
	podman compose up -d --build