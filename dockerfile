FROM python:3.9-slim
RUN pip install --no-cache-dir pymupdf==1.22.5
WORKDIR /app
COPY main.py .
RUN mkdir -p input output
CMD ["python", "main.py"]