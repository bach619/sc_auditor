FROM python:3.12-slim

WORKDIR /app

COPY services/17-experience/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/shared
COPY services/17-experience /app/services/17-experience

ENV PYTHONPATH=/app
EXPOSE 8019

CMD ["uvicorn", "services.17-experience.app:app", "--host", "0.0.0.0", "--port", "8019", "--log-level", "info"]
