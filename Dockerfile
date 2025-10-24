# Use official Playwright image with Python and browsers installed
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Set working directory
WORKDIR /app

# Copy dependency files first (for caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code
COPY . .

# Ensure playwright browsers are installed
RUN playwright install --with-deps chromium

# Expose Render’s port (Render provides PORT env variable)
EXPOSE 10000

# Start the FastAPI app using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]




