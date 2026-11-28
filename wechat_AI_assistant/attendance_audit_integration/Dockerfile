FROM python:3.9-slim-bullseye

WORKDIR /app

ENV PYTHONUNBUFFERED=1
# config.py derives ROOT_DIR (where .env/data/logs live) from its own file
# location assuming the src/attendance_audit_integration/../.. layout under
# /app; `pip install .` alone would put the package under site-packages at a
# different nesting depth and silently break ROOT_DIR (and .env loading).
# Keep /app/src ahead of site-packages on the import path so the mounted
# source tree (not the installed copy) is what actually runs.
ENV PYTHONPATH=/app/src

# Configure Aliyun mirrors for ultra-fast apt-get install inside China
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Dependencies now come from pyproject.toml (requirements.txt was retired when
# the project moved to the code_dev_audit_framework scaffolding, see
# docs/archive/requirements_txt_pre_v2.txt).
COPY pyproject.toml .
COPY src/ /app/src/
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ .

EXPOSE 8000

# Run uvicorn FastAPI server
CMD ["uvicorn", "attendance_audit_integration.main:app", "--host", "0.0.0.0", "--port", "8000"]
