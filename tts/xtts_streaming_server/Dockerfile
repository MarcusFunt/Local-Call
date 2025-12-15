
FROM python:3.11-slim

RUN apt-get update && apt-get install -y git

RUN git clone https://github.com/coqui-ai/xtts-streaming-server.git /app/xtts-streaming-server

WORKDIR /app/xtts-streaming-server

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "app.py"]
