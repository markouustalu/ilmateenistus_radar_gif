# Use official lightweight Python runtime as base
FROM python:3.10-slim

# Set working directory inside container
WORKDIR /app

# Install system fonts for beautiful GIF text rendering inside Linux
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy python dependency list and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files into container
COPY . .

# Expose port configured in app.py
EXPOSE 8096

# Command to run application server
CMD ["python", "app.py"]
