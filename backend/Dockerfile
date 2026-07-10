FROM python:3.11-slim
WORKDIR /app

# 安装依赖，增加超时
COPY requirements.txt .
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --no-cache-dir --default-timeout=120 --index-url "${PIP_INDEX_URL}" -r requirements.txt

COPY . /app/backend/
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
