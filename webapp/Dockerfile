FROM python:3.11-slim
WORKDIR /app
COPY webapp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY webapp/app.py .
COPY webapp/templates/ templates/
COPY webapp/static/ static/
CMD ["python", "app.py"]
