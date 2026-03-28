# Dockerfile - Containerized deployment (Ch.5 - Docker)
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY mass_text.py .
COPY config.yaml .
COPY contacts.yaml .
COPY templates/ templates/

RUN mkdir -p logs

CMD ["python3", "mass_text.py", "--dry-run", "-b", "Hello from container"]
