FROM python:3.12-slim
WORKDIR /app
COPY server/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY server/backend/app ./app
EXPOSE 8077
CMD ["uvicorn","app.v401:app","--host","0.0.0.0","--port","8077","--proxy-headers","--forwarded-allow-ips=*"]
