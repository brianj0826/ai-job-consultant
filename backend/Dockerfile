FROM python:3.10-slim
WORKDIR /app

# 使用清华 PyPI 镜像（对大包支持更好）
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/

# 安装依赖，增加超时
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=120 -r requirements.txt

COPY . /app/backend/
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]