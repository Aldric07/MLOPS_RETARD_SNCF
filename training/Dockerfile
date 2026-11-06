FROM python:3.11-slim
WORKDIR /app
COPY training/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common ./common
COPY training/train.py .
CMD ["python", "train.py"]
