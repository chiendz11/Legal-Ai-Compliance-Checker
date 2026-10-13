FROM python:3.12-slim

WORKDIR /workspace
COPY backend/ backend/
COPY constraints.txt ./constraints.txt
COPY data/knowledge.json data/knowledge.json

RUN python -m pip install --no-cache-dir ./backend -c constraints.txt

ENV KNOWLEDGE_PATH=/workspace/data/knowledge.json
ENV DATABASE_PATH=/workspace/data/private/runtime.sqlite3
EXPOSE 8000

CMD ["uvicorn", "legal_checker.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
