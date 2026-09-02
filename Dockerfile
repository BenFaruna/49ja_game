FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Firefox ESR and GeckoDriver dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    firefox-esr \
    wget \
    bzip2 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install GeckoDriver manually
ARG GECKODRIVER_VERSION=v0.34.0
RUN wget -q https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VERSION}/geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz \
    && tar -xzf geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz -C /usr/local/bin/ \
    && rm geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz

WORKDIR /app
RUN touch game_data.db app.log

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

EXPOSE 5000

# Run Gunicorn using gunicorn.conf.py (Master process lifecycle hook starts scraper)
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
