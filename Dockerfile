FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app
COPY token_refresher.py .
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "token_refresher.py"]


#asia-south1-docker.pkg.dev/zerodha-algo-trading-297611/kite-algo-trading