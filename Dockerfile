FROM python:3.9-alpine

WORKDIR /app

COPY requirements.txt .
COPY . .

RUN pip install -r requirements.txt

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "rag_http_mcp_server.py", "--service-url", "http://localhost:9621", "--key", "your_api_key"]