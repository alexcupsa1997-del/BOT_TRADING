FROM python:3.10-slim

WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install pyarrow # Ensure pyarrow is present

# Source
COPY . .

# Set Path
ENV PYTHONPATH=/app

# Run as non-root
RUN adduser --disabled-password --no-create-home appuser
USER appuser

# Default command
CMD ["python", "dummy_train.py"]
