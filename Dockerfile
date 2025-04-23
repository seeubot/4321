FROM python:3.9-slim

# Install system dependencies including procps for pgrep
RUN apt-get update && apt-get install -y \
    aria2 \
    ffmpeg \
    libmagic1 \
    git \
    procps \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot code
COPY . .

# Create necessary directories
RUN mkdir -p templates thumbnails

# Expose the port for the Flask web server
EXPOSE 8080

# Set environment variables
ENV PORT=8080

# Start script permissions
COPY start.sh /app/
RUN chmod +x /app/start.sh

# Command to run the bot
CMD ["/app/start.sh"]
