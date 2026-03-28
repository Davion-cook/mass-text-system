# Makefile - Central task runner (Ch.5 - Development Tools)
SHELL=/bin/bash

.PHONY: all install test dry-run send clean docker-build docker-run

all: install

install:
	pip3 install -r requirements.txt

dry-run:
	python3 mass_text.py --dry-run -b "Test message" -g all_staff

send:
	python3 mass_text.py -b "$(MESSAGE)" -g $(GROUPS)

test:
	python3 -m pytest tests/ -v

clean:
	rm -rf logs/*.log __pycache__ .pytest_cache

docker-build:
	docker build . -t mass-text-system:latest

docker-run:
	docker run --env-file .env mass-text-system:latest
