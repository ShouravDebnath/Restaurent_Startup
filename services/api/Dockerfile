FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml .
COPY requirements-runtime-lock.txt .
COPY src ./src
COPY alembic.ini .
COPY migrations ./migrations
RUN pip install --no-cache-dir -c requirements-runtime-lock.txt .

EXPOSE 8000
CMD ["uvicorn", "restaurant_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
