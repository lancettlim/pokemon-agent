.PHONY: setup lint test dbt-build validate check dashboard extract-all refresh release

setup:
	uv sync
	uv run playwright install --with-deps chromium

lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest

dbt-build:
	cd dbt && uv run dbt build

validate:
	uv run python -m pipelines.cli validate

check: lint test validate

dashboard: dbt-build
	uv run python -m pipelines.cli render-share-cards
	uv run python -m pipelines.cli build-dashboard

# extract-all -> dbt-build -> validate, chained the same way `dashboard`
# chains dbt-build -> build-dashboard (backlog.md #5). `release` extends the
# same chain one step further, gated on an explicit VERSION since deciding
# the next dataset_version is a human call `pipelines.cli extract`'s default
# (the latest published version, see pipelines/versioning.py) shouldn't make
# on its own.
extract-all:
	uv run python -m pipelines.cli extract all

refresh: extract-all dbt-build validate

release: refresh
	@if [ -z "$(VERSION)" ]; then \
		echo "Usage: make release VERSION=X.Y.Z"; \
		exit 1; \
	fi
	uv run python -m pipelines.cli release --version $(VERSION)
