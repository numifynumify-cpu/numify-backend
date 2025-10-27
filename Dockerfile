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

# Install Playwright browsers (final fix for Debian Trixie on Render)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    fonts-unifont \
    fonts-dejavu-core \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libdrm2 \
    libgbm1 \
    libxshmfence1 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxrender1 \
    wget && \
    rm -rf /var/lib/apt/lists/* && \
    playwright install chromium


# Copy source code
COPY . .

# Expose port
EXPOSE 10000

# Command to run app
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]





