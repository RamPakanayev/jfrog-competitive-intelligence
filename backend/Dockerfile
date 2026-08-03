FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY config ./config
COPY data/demo ./data/demo
ENV DATABASE_URL=sqlite:////data/ribbit.db \
    CONFIG_DIR=/app/config \
    DEMO_SEED_PATH=/app/data/demo/seed.json
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
