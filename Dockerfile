FROM python:3.9-alpine

WORKDIR /app

COPY . .

ENTRYPOINT ["python", "rag_http_mcp_server.py"]