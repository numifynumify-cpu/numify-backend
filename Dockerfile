# Use a stable Python version
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy dependencies first
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Expose port (Render expects 10000)
EXPOSE 10000

# Define environment variable for FastAPI / Flask
ENV PORT=10000

# Start FastAPI app with Uvicorn (faster and simpler than gunicorn for now)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]

