# Portable container for the Kvoč API - works on Render, Railway, Fly.io,
# or any other Docker-capable host. See docs/DEPLOYMENT.md.
FROM python:3.12-slim

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.py .

ENV HOST=0.0.0.0
ENV KVOC_RELOAD=0

EXPOSE 8000

CMD ["python", "run.py"]
