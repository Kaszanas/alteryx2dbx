.PHONY: sync test lint convert-example

sync:
	uv sync

test:
	uv run pytest --cov=alteryx2dbx

lint:
	uv run ruff check .

convert-example:
	uv run alteryx2dbx convert examples/simple_filter.yxmd -o ./output --full
