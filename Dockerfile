# Use Playwright image that already has browsers & deps
FROM mcr.microsoft.com/playwright/python:1.40.0-focal

# App directory
WORKDIR /app

# Copy dependency files first for better cache
COPY requirements.txt .

# Install Python deps (Playwright is in requirements.txt)
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Expose port Render expects
ENV PORT=10000
EXPOSE 10000

# Run your app (adjust command if you use different entry)
# If you run with uvicorn directly:
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000", "--workers", "1"]
# Or if you prefer gunicorn + uvicorn worker:
CMD ["gunicorn", "main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:10000"]


