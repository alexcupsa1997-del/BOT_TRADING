.PHONY: test-all test-py test-go test-rs up down logs health

test-py:
	cd analysis && PYTHONPATH=. pytest tests/ -v

test-go:
	cd gateway && go test -v ./...

test-rs:
	cd engine && cargo test --release

test-all: test-py test-go test-rs

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

health:
	@curl -sf http://localhost:8080/health && echo " Gateway OK" || echo " Gateway DOWN"
	@curl -sf http://localhost:8080/api/signal/XAUUSD && echo " Analysis OK" || echo " Analysis DOWN"
