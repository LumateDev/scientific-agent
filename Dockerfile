FROM python:3.11-slim

WORKDIR /app

# Устанавливаем системные зависимости для lxml и других библиотек
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости и устанавливаем
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаём папки для вывода и кэша
RUN mkdir -p output cache logs

# Точка входа
CMD ["python", "main.py", "--web"]