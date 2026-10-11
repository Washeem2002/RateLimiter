.PHONY: up down test lint fmt typecheck loadtest migrate run worker

up:
	docker compose up --build -d

down:
	docker compose down

test:
	pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	ruff check app worker tests

fmt:
	ruff format app worker tests

typecheck:
	mypy app

migrate:
	alembic upgrade head

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	python -m worker.click_consumer

loadtest:
	locust -f loadtest/locustfile.py --headless -u 200 -r 20 -t 60s --host http://localhost:8000

install:
	pip install -e ".[dev]"
