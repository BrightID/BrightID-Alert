FROM python:3.9-slim

WORKDIR /app

# Install system dependencies & Keybase
RUN apt-get update && \
    apt-get install -y curl libayatana-appindicator3-1 fuse psmisc lsof procps libasound2 libnss3 libxss1 libxtst6 libgtk-3-0 && \
    curl -O https://prerelease.keybase.io/keybase_amd64.deb && \
    dpkg -i keybase_amd64.deb || apt-get install -f 
    #&& rm keybase_amd64.deb

# Add Keybase to PATH
ENV PATH="/usr/bin:/usr/local/bin:${PATH}"

# Copy dependencies and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV KEYBASE_SERVICE_DIR=/home/appuser/.config/keybase

# Create a non-root user and switch to it
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Start Keybase and running the app
CMD keybase service & sleep 10 && python /app/alert_service.py
