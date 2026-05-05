<<<<<<< HEAD
FROM python:3.12-slim
WORKDIR /app
RUN pip install flask
COPY app.py .
CMD ["python", "app.py"]
=======
FROM python:3.11-slim
WORKDIR /app
COPY webapp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY webapp/app.py .
COPY webapp/templates/ templates/
COPY webapp/static/ static/
CMD ["python", "app.py"]
>>>>>>> origin/main
