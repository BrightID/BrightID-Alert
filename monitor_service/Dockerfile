FROM python:3.9-slim

WORKDIR /app

COPY monitor_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY monitor_service/ .
COPY shared ./shared

RUN useradd -m appuser && chown -R appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1

CMD ["python", "monitor_service.py"]
