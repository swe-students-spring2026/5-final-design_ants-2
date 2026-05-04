FROM python:3.11-slim

WORKDIR /app

COPY checkin-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY db ./db
COPY checkin-service .

ENV PORT=5000
EXPOSE ${PORT}

CMD ["python", "app.py"]