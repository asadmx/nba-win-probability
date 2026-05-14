# Use the slim Python 3.11 image — smaller than the full image,
# but still has enough utilities for most needs.
FROM python:3.11-slim

# Set the working directory inside the container.
WORKDIR /app

# Install system dependencies that some Python packages need to compile.
# We'll need build-essential when we add PyTorch and pandas later.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first, separately from the rest of the code.
# This is a Docker caching trick: if requirements.txt doesn't change,
# Docker reuses the cached pip install layer on subsequent builds.
# Without this, every code change would trigger a full reinstall.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the application code.
COPY . .

# Document the port the container listens on (not actual port-forwarding).
EXPOSE 8000

# The command that runs when the container starts.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]