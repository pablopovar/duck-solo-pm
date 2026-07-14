FROM node:22-slim AS editor-build

WORKDIR /build

COPY web/editor/package.json ./
RUN npm install --no-audit --no-fund

COPY web/editor/vite.config.js ./
COPY web/editor/src/ ./src/

RUN npm run build


FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY web/ ./web/

COPY --from=editor-build /build/dist/ ./web/static/editor/

EXPOSE 3200

CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "3200"]
