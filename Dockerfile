FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY zoomFASTYouTube.py .
RUN mkdir -p /videos /credentials
CMD ["python", "zoomFASTYouTube.py"]

