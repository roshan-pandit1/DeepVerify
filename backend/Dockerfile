FROM python:3.11-slim
WORKDIR /app
COPY requirements-investigation.txt .
RUN pip install --no-cache-dir -r requirements-investigation.txt
COPY investigation ./investigation
COPY start.sh .
RUN useradd --uid 10001 --create-home deepverify
USER 10001
CMD ["bash", "start.sh", "api"]
