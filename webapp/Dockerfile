FROM python:3.11-slim
WORKDIR /app
RUN pip install flask requests
COPY webapp/app.py .
COPY webapp/templates/ templates/
CMD ["python", "app.py"]