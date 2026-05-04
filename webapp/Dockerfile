FROM python:3.12-slim
WORKDIR /app
RUN pip install flask requests
COPY webapp/app.py .
COPY webapp/templates/ templates/
CMD ["python", "app.py"]