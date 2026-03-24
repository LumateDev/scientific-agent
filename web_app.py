"""
Простой веб-интерфейс на Flask.

Позволяет:
- Вводить поисковые запросы через форму
- Просматривать результаты поиска
- Скачивать JSON-отчёты
"""

import json
import logging
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, send_file

from config import Config

logger = logging.getLogger("sci_agent.web")

app = Flask(__name__)

# Шаблон веб-интерфейса
INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔬 Scientific Article Search Agent</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: #f0f2f5;
            min-height: 100vh;
        }
        .container { max-width: 900px; margin: 0 auto; padding: 20px; }
        
        header {
            background: linear-gradient(135deg, #1a5276, #2980b9);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            text-align: center;
        }
        header h1 { font-size: 1.8em; margin-bottom: 5px; }
        
        .search-form {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            margin-bottom: 20px;
        }
        .search-form input[type="text"] {
            width: 100%;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 1em;
            margin-bottom: 10px;
            transition: border-color 0.3s;
        }
        .search-form input[type="text"]:focus {
            outline: none;
            border-color: #2980b9;
        }
        .search-form .controls {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }
        .search-form label { font-size: 0.9em; color: #666; }
        .search-form input[type="number"] {
            width: 80px;
            padding: 8px;
            border: 2px solid #e0e0e0;
            border-radius: 6px;
        }
        .search-form button {
            background: #2980b9;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            font-size: 1em;
            cursor: pointer;
            transition: background 0.3s;
        }
        .search-form button:hover { background: #1a5276; }
        .search-form button:disabled {
            background: #ccc;
            cursor: wait;
        }
        
        .status {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            display: none;
        }
        .status.loading {
            display: block;
            background: #fff3e0;
            color: #e65100;
        }
        .status.error {
            display: block;
            background: #ffebee;
            color: #c62828;
        }
        .status.success {
            display: block;
            background: #e8f5e9;
            color: #2e7d32;
        }
        
        #results { margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔬 Scientific Article Search Agent</h1>
            <p>Поиск научных статей в arXiv, eLibrary, Scopus, WoS</p>
        </header>
        
        <div class="search-form">
            <form id="searchForm">
                <input type="text" id="query" name="query" 
                       placeholder="Введите поисковый запрос..."
                       value="{{ default_query }}">
                <div class="controls">
                    <label>Макс. результатов:</label>
                    <input type="number" id="max_results" 
                           value="10" min="1" max="50">
                    <button type="submit" id="searchBtn">
                        🔍 Искать
                    </button>
                </div>
            </form>
        </div>
        
        <div id="status" class="status"></div>
        <div id="results"></div>
    </div>
    
    <script>
        document.getElementById('searchForm').addEventListener('submit', 
            async function(e) {
                e.preventDefault();
                
                const query = document.getElementById('query').value;
                const maxResults = document.getElementById('max_results').value;
                const statusEl = document.getElementById('status');
                const resultsEl = document.getElementById('results');
                const btn = document.getElementById('searchBtn');
                
                btn.disabled = true;
                btn.textContent = '⏳ Поиск...';
                statusEl.className = 'status loading';
                statusEl.textContent = 'Поиск статей... Это может занять некоторое время.';
                resultsEl.innerHTML = '';
                
                try {
                    const response = await fetch('/api/search', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            query: query, 
                            max_results: parseInt(maxResults)
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (data.error) {
                        statusEl.className = 'status error';
                        statusEl.textContent = 'Ошибка: ' + data.error;
                    } else {
                        statusEl.className = 'status success';
                        statusEl.textContent = 
                            'Найдено ' + data.total + ' статей. ' +
                            'JSON: ' + (data.json_path || '') + ' | ' +
                            'HTML: ' + (data.html_path || '');
                        
                        // Отображаем результаты
                        let html = '';
                        for (const article of data.articles) {
                            html += '<div style="background:white;' +
                                'padding:20px;border-radius:10px;' +
                                'margin-bottom:15px;' +
                                'box-shadow:0 2px 8px rgba(0,0,0,0.08);' +
                                'border-left:4px solid #2980b9">';
                            html += '<h3><a href="' + article.url + 
                                '" target="_blank">' + 
                                article.title + '</a></h3>';
                            html += '<p style="color:#666;font-style:italic">' + 
                                (article.authors || []).join(', ') + '</p>';
                            if (article.year) {
                                html += '<p>📅 ' + article.year + 
                                    ' | 📰 ' + (article.journal || '') + '</p>';
                            }
                            if (article.summary_ru) {
                                html += '<div style="background:#f8f9fa;' +
                                    'padding:10px;border-radius:6px;' +
                                    'margin-top:10px;border-left:3px solid #28a745">';
                                html += '<strong>📝 Резюме:</strong> ' + 
                                    article.summary_ru;
                                html += '</div>';
                            }
                            html += '</div>';
                        }
                        resultsEl.innerHTML = html;
                    }
                } catch (err) {
                    statusEl.className = 'status error';
                    statusEl.textContent = 'Ошибка сети: ' + err.message;
                }
                
                btn.disabled = false;
                btn.textContent = '🔍 Искать';
            }
        );
    </script>
</body>
</html>"""


@app.route('/')
def index():
    """Главная страница с формой поиска."""
    return render_template_string(
        INDEX_TEMPLATE,
        default_query=Config.DEFAULT_QUERY
    )


@app.route('/api/search', methods=['POST'])
def api_search():
    """
    API endpoint для поиска статей.
    
    Принимает JSON: {"query": "...", "max_results": 10}
    Возвращает JSON с результатами.
    """
    try:
        data = request.get_json()
        query = data.get('query', Config.DEFAULT_QUERY)
        max_results = data.get('max_results', 10)

        # Импортируем агента здесь, чтобы избежать кольцевого импорта
        from main import SearchAgent

        agent = SearchAgent()
        articles = agent.search(query, max_results=max_results)

        # Генерируем отчёты
        from report_generator import ReportGenerator
        reporter = ReportGenerator()
        json_path = reporter.generate_json(articles, query)
        html_path = reporter.generate_html(articles, query)

        return jsonify({
            'total': len(articles),
            'articles': [a.to_dict() for a in articles],
            'json_path': json_path,
            'html_path': html_path,
        })

    except Exception as e:
        logger.error(f"Ошибка API поиска: {e}")
        return jsonify({'error': str(e)}), 500


def run_web():
    """Запуск веб-сервера."""
    logger.info(
        f"Запуск веб-интерфейса: "
        f"http://{Config.FLASK_HOST}:{Config.FLASK_PORT}"
    )
    app.run(
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG
    )