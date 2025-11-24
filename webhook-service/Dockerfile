# Use official Python runtime as base image
FROM python:3.11-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory in container
WORKDIR /app

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (only Chromium)
RUN python -m playwright install chromium

# Copy application code
COPY app.py .
COPY dhan_client.py .
COPY dhan_auth.py .
COPY telegram_notifier.py .
COPY signal_queue.py .
COPY trading_calendar.py .
COPY security_id_list.csv .

# Create directory for CSV logs
RUN mkdir -p /app/logs

# Expose port (Cloud Run will override this with $PORT)
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application
CMD exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}
