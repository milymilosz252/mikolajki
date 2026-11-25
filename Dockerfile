FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir flask gunicorn

COPY app.py .
COPY static ./static

ENV DATA_DIR=/data PYTHONUNBUFFERED=1
EXPOSE 5000

# najpierw synchronizacja uczestników i haseł (z wypisaniem haseł), potem serwer
CMD ["sh", "-c", "python app.py --prepare && exec gunicorn -b 0.0.0.0:5000 -w 2 app:app"]