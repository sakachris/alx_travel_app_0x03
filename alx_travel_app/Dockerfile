# Dockerfile for ALX Travel App Backend

# Stage 1: Builder
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    default-libmysqlclient-dev \
    libmariadb-dev-compat \
    libmariadb-dev \
    pkg-config \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Stage 2: Final Image
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ✅ Install netcat and MySQL runtime libraries here
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    default-libmysqlclient-dev \
    libmariadb-dev-compat \
    libmariadb-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

EXPOSE 8000
CMD ["gunicorn", "alx_travel_app.wsgi:application", "--bind", "0.0.0.0:8000"]


# # Stage 2: Final Image
# FROM python:3.11-slim

# ENV PYTHONDONTWRITEBYTECODE=1
# ENV PYTHONUNBUFFERED=1

# # ✅ Install netcat-openbsd here in the final image
# RUN apt-get update && apt-get install -y netcat-openbsd && apt-get clean && rm -rf /var/lib/apt/lists/*

# WORKDIR /app

# COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
# COPY --from=builder /usr/local/bin /usr/local/bin

# COPY . .

# COPY entrypoint.sh /entrypoint.sh
# RUN chmod +x /entrypoint.sh

# ENTRYPOINT ["/entrypoint.sh"]

# EXPOSE 8000
# CMD ["gunicorn", "alx_travel_app.wsgi:application", "--bind", "0.0.0.0:8000"]


# # Stage 1: Build
# FROM python:3.11-slim AS builder

# ENV PYTHONDONTWRITEBYTECODE=1
# ENV PYTHONUNBUFFERED=1

# # RUN apt-get update && apt-get install -y \
# #     gcc \
# #     pkg-config \
# #     default-libmysqlclient-dev \
# #     libmariadb-dev \
# #     netcat \
# #     && rm -rf /var/lib/apt/lists/*

# RUN apt-get update && apt-get install -y \
#     gcc \
#     g++ \
#     python3-dev \
#     default-libmysqlclient-dev \
#     libmariadb-dev-compat \
#     libmariadb-dev \
#     pkg-config \
#     netcat-openbsd \
#     && apt-get clean && rm -rf /var/lib/apt/lists/*

# WORKDIR /app

# COPY requirements.txt .
# RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# # Stage 2: Final Image
# FROM python:3.11-slim

# ENV PYTHONDONTWRITEBYTECODE=1
# ENV PYTHONUNBUFFERED=1

# WORKDIR /app

# COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
# COPY --from=builder /usr/local/bin /usr/local/bin

# COPY . .

# # Debugging: Print the contents of /app to verify manage.py location
# RUN ls -l /app

# # RUN python manage.py collectstatic --noinput

# COPY entrypoint.sh /entrypoint.sh
# RUN chmod +x /entrypoint.sh

# # Set the entrypoint
# ENTRYPOINT ["/entrypoint.sh"]

# EXPOSE 8000
# CMD ["gunicorn", "alx_travel_app.wsgi:application", "--bind", "0.0.0.0:8000"]