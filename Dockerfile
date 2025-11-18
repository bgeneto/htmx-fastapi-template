FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Compile translations for production
RUN pybabel compile -d translations

RUN mkdir -p /app && touch /app/dev.db && chown nobody:nogroup /app/dev.db || true
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
