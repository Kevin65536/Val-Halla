FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY src/ ./src/
RUN mkdir -p config data/backups data/database data/logs export runtime/processes
EXPOSE 8080
CMD ["python", "-m", "src.main", "webui", "--host", "0.0.0.0", "--port", "8080"]
