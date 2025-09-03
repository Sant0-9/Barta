FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt /app/
RUN pip install -r /app/requirements.txt

# Copy API code, ingestion modules, packages, tests, and alembic files
COPY apps/api ./apps/api
COPY apps/ingest ./apps/ingest
COPY packages ./packages
COPY tests ./tests
COPY infra/migrations ./infra/migrations
COPY alembic.ini ./

EXPOSE 8000

# Set Python path to include project root
ENV PYTHONPATH=/app:$PYTHONPATH

WORKDIR /app/apps/api
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]