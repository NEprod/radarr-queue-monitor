FROM python:3.11-slim

WORKDIR /app

COPY radarr_queue_monitor.py .

RUN pip install requests

CMD ["python", "radarr_queue_monitor.py"]