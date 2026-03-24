# 🔬 Scientific Article Search Agent

Модульный агент для автоматизированного поиска научных статей
по заданной тематике с поддержкой множества источников.

## 📋 Возможности

- **Мульти-источники**: arXiv, eLibrary.ru, Scopus, Web of Science
- **Автоматический перевод** аннотаций на русский язык
- **Экстрактивная суммаризация** — краткие резюме статей
- **Скачивание PDF** из открытого доступа (arXiv, eLibrary)
- **JSON + HTML отчёты** с карточками статей
- **SQLite база данных** для хранения и анализа
- **Кэширование** для ускорения повторных запросов
- **Веб-интерфейс** (Flask) для удобного поиска
- **Дедупликация** статей из разных источников

## 📐 Архитектура

```
┌───────────────────────────────────────────────────────────┐
│                    main.py (SearchAgent)                   │
│  Координация поиска, обработка, генерация отчётов         │
├───────────────┬───────────────┬───────────────────────────┤
│   Fetchers    │  Processing   │       Output              │
│               │               │                           │
│ ┌───────────┐ │ ┌───────────┐ │ ┌───────────────────────┐ │
│ │   arXiv   │ │ │ Translator│ │ │   JSON Report         │ │
│ ├───────────┤ │ ├───────────┤ │ ├───────────────────────┤ │
│ │ eLibrary  │ │ │Summarizer │ │ │   HTML Report         │ │
│ ├───────────┤ │ ├───────────┤ │ ├───────────────────────┤ │
│ │  Scopus   │ │ │PDF Downl. │ │ │   SQLite Database     │ │
│ ├───────────┤ │ └───────────┘ │ ├───────────────────────┤ │
│ │   WoS     │ │               │ │   Console Summary     │ │
│ └───────────┘ │               │ └───────────────────────┘ │
└───────────────┴───────────────┴───────────────────────────┘
```

## 🚀 Быстрый старт

### 1. Клонирование и установка

```bash
git clone <repo_url>
cd scientific_agent

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Настройка конфигурации

```bash
cp .env.example .env
# Отредактируйте .env при необходимости
```

**Минимальная конфигурация** (работает "из коробки"):

- arXiv — не требует ключей
- eLibrary — парсинг, может блокироваться

**Расширенная конфигурация** (требуются API-ключи):

- Scopus: получите ключ на https://dev.elsevier.com/
- WoS: получите ключ на https://developer.clarivate.com/

### 3. Запуск

```bash
# Базовый поиск с параметрами по умолчанию
python main.py

# Поиск по конкретному запросу
python main.py --query "dissociation recombination water transport electromagnetic" --max_results 20

# Быстрый поиск (без PDF и перевода)
python main.py -q "water molecules EMC" -n 10 --no-pdf --no-translate

# Только JSON-отчёт
python main.py -q "electromagnetic compatibility" --json-only

# Запуск веб-интерфейса
python main.py --web

# Статистика базы данных
python main.py --db-stats

# Очистка кэша
python main.py --clear-cache
```

## 📁 Структура файлов

```
scientific_agent/
├── main.py              # Главный модуль, точка входа
├── config.py            # Конфигурация из .env
├── database.py          # SQLite хранилище
├── summarizer.py        # Экстрактивная суммаризация
├── report_generator.py  # Генерация JSON/HTML отчётов
├── web_app.py           # Flask веб-интерфейс
├── fetchers/            # Модули источников
│   ├── base_fetcher.py  # Базовый класс + модель Article
│   ├── arxiv_fetcher.py # arXiv.org (Atom API)
│   ├── elibrary_fetcher.py  # eLibrary.ru (парсинг)
│   ├── scopus_fetcher.py    # Scopus (Elsevier API)
│   └── wos_fetcher.py       # Web of Science (Clarivate API)
├── utils/               # Утилиты
│   ├── translator.py    # Перевод (Google Translate)
│   ├── pdf_downloader.py    # Скачивание PDF
│   └── cache.py         # Менеджер кэша
├── output/              # Результаты (JSON, HTML, PDF)
├── cache/               # Кэш запросов
└── logs/                # Логи
```

## 🔧 Настройки источников

### arXiv (✅ работает без ключа)

- Полностью бесплатный API
- Все статьи в открытом доступе
- PDF всегда доступен для скачивания

### eLibrary.ru (⚠️ парсинг)

- Официального API нет
- Парсинг может блокироваться
- При блокировке используются демо-данные
- Часть статей в открытом доступе

### Scopus (🔑 нужен API-ключ)

- Бесплатный ключ: https://dev.elsevier.com/
- Без ключа — демо-данные
- Полнофункциональный RESTful API

### Web of Science (🔑 нужен API-ключ)

- Ключ: https://developer.clarivate.com/
- WoS Starter API (ограниченный доступ)
- Без ключа — демо-данные

## 📊 Формат выходных данных

### JSON-отчёт

```json
{
  "meta": {
    "query": "dissociation recombination water",
    "date": "2024-01-15T10:30:00",
    "total_results": 15,
    "sources": ["arxiv", "elibrary", "scopus"]
  },
  "articles": [
    {
      "title": "...",
      "authors": ["Author A", "Author B"],
      "abstract": "...",
      "doi": "10.xxxx/...",
      "url": "https://...",
      "pdf_url": "https://...",
      "year": 2023,
      "journal": "...",
      "keywords": ["keyword1", "keyword2"],
      "source": "arxiv",
      "summary_ru": "Краткое резюме на русском...",
      "abstract_ru": "Перевод аннотации..."
    }
  ]
}
```

### HTML-отчёт

Визуальный отчёт с карточками статей, открывается в браузере.
Включает статистику по источникам, ссылки на DOI и PDF.

### SQLite база данных

Таблицы: `articles`, `searches`, `search_results`.
Позволяет выполнять SQL-запросы для анализа.

## 🐳 Docker

Соберите образ и запустите контейнер:

```bash
docker-compose up -d
```

## 📝 Примечания

- Для корректной работы суммаризатора требуется интернет
  (скачивание NLTK данных при первом запуске)
- eLibrary может потребовать CAPTCHA при частых запросах
- Рекомендуемая задержка между запросами: 1-3 секунды
- Кэш результатов хранится 24 часа (настраивается)

## 🔍 Тема исследования по умолчанию

**«Влияние диссоциации/рекомбинации молекул воды
на процессы переноса в ЭМС»**

Ключевые слова для поиска:

- EN: dissociation, recombination, water molecules,
  transport processes, electromagnetic compatibility
- RU: диссоциация, рекомбинация, молекулы воды,
  перенос заряда, электромагнитная совместимость
