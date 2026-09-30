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

## create-admin: create a new admin account (interactive CLI — use --super for super-admin)
.PHONY: create-admin
create-admin:
	@echo "Launching admin creation utility..."
	python scripts/create_admin.py $(ARGS)

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

## test-email: send a test email to verify SMTP config (pass EMAIL=addr@example.com)
.PHONY: test-email
test-email:
	@echo "Sending test email to $(EMAIL)..."
	python -c "from utils.email_service import _send_email, _is_configured; \
	  assert _is_configured(), 'SMTP not configured — set SMTP_USER and SMTP_PASSWORD in .env'; \
	  _send_email('$(EMAIL)', '✅ 49ja Test Email', '<h2>SMTP is working!</h2><p>Your email configuration is correct.</p>')"