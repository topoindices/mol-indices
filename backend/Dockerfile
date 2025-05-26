FROM python:3.10-slim-bullseye

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    libboost-python-dev \
    libcairo2-dev \
    cmake \
    build-essential \
    libxrender1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Create user with home directory
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Set up PATH and environment
ENV PATH="/home/appuser/.local/bin:${PATH}"
ENV UPLOAD_FOLDER=/app/uploads
ENV PYTHONPATH=/app

# Create uploads directory
RUN mkdir -p /app/uploads && chmod 777 /app/uploads

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt && \
    pip install --upgrade pip && \
    pip install rdkit-pypi

# Copy application files
COPY --chown=appuser:appuser . .

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "app:app"]