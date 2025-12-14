FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y netcat-openbsd curl
RUN curl -fsSL https://get.docker.com -o get-docker.sh
RUN sh get-docker.sh

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Default command to run the application
CMD ["python", "-u", "apps/server.py"]
