.PHONY: ingest sample api web test up
ingest:  ## download the real January 2026 data from Elexon
	python scripts/ingest.py
sample:  ## synthetic data for offline development only
	python scripts/make_sample_data.py
api:
	uvicorn backend.app.main:app --reload --port 8000
web:
	cd frontend && npm install && npm run dev
test:
	python -m pytest backend/tests -q
up:
	docker compose up --build
