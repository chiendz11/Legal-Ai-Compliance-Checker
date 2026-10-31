FROM python:3.12-slim

WORKDIR /workspace
COPY backend/ backend/
COPY constraints.txt ./constraints.txt

RUN python -m pip install --no-cache-dir ./backend -c constraints.txt \
    && groupadd --gid 10001 legal \
    && useradd --uid 10001 --gid 10001 --no-create-home legal

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "legal_checker.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
