# Use official Python base image
FROM python:3.10-slim

# Set work directory
WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y wget libnss3 libatk-bridge2.0-0 libxkbcommon0 libdrm2 libgbm1 libasound2 libxshmfence1 && \
    rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Copy source code
COPY . .

# Expose port
EXPOSE 10000

# Command to run app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]





