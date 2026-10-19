FROM python:3.12-slim

# DejaVu gives the PDF exporter a Unicode font with Vietnamese glyphs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY backend/ backend/
COPY constraints.txt ./constraints.txt

RUN python -m pip install --no-cache-dir "./backend[worker,export]" -c constraints.txt

EXPOSE 8000

# The same image runs the worker with:
#   celery -A legal_checker.worker.celery_app worker --beat --loglevel=INFO
CMD ["uvicorn", "legal_checker.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
