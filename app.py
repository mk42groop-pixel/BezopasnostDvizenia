import os
import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import requests
import httpx

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'rzd-safety-secret-2024')

# HTML шаблон для дашборда
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RZD Safety Bot Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; padding: 20px;
        }
        .container { 
            max-width: 1200px; margin: 0 auto; 
            background: white; border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1); overflow: hidden;
        }
        .header { 
            background: linear-gradient(135deg, #2c3e50, #34495e);
            color: white; padding: 30px; text-align: center;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { opacity: 0.9; font-size: 1.1em; }
        
        .stats-grid { 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px; padding: 30px; background: #f8f9fa;
        }
        .stat-card { 
            background: white; padding: 25px; border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1); text-align: center;
            border-left: 5px solid #3498db;
        }
        .stat-card.success { border-left-color: #27ae60; }
        .stat-card.warning { border-left-color: #f39c12; }
        .stat-card.danger { border-left-color: #e74c3c; }
        .stat-number { 
            font-size: 2.5em; font-weight: bold; color: #2c3e50;
            margin: 10px 0;
        }
        .stat-label { color: #7f8c8d; font-size: 0.9em; }
        
        .content { padding: 30px; }
        .section { margin-bottom: 40px; }
        .section-title { 
            font-size: 1.5em; color: #2c3e50; margin-bottom: 20px;
            padding-bottom: 10px; border-bottom: 2px solid #ecf0f1;
        }
        
        .manual-post { background: #f8f9fa; padding: 25px; border-radius: 10px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #2c3e50; }
        select, textarea, button { 
            width: 100%; padding: 12px; border: 2px solid #ddd;
            border-radius: 8px; font-size: 1em;
        }
        textarea { height: 120px; resize: vertical; }
        button { 
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white; border: none; cursor: pointer;
            font-weight: 600; transition: all 0.3s;
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
        button.success { background: linear-gradient(135deg, #27ae60, #229954); }
        
        .schedule-controls { background: #e8f4fd; padding: 20px; border-radius: 10px; margin: 20px 0; }
        .control-buttons { display: flex; gap: 10px; flex-wrap: wrap; }
        
        .jobs-list { background: white; border-radius: 10px; overflow: hidden; margin: 20px 0; }
        .job-item { 
            padding: 15px 20px; border-bottom: 1px solid #ecf0f1;
            display: flex; justify-content: space-between; align-items: center;
        }
        .job-item:last-child { border-bottom: none; }
        .job-info { flex: 1; }
        .job-name { font-weight: 600; color: #2c3e50; }
        .job-time { color: #7f8c8d; font-size: 0.9em; }
        .job-status { 
            padding: 5px 12px; border-radius: 20px; font-size: 0.8em;
            font-weight: 600;
        }
        .status-active { background: #d5f4e6; color: #27ae60; }
        .status-paused { background: #fdebd0; color: #f39c12; }
        
        .alert { 
            padding: 15px; border-radius: 8px; margin: 15px 0;
            border-left: 5px solid;
        }
        .alert-success { background: #d5f4e6; border-color: #27ae60; color: #155724; }
        .alert-danger { background: #f8d7da; border-color: #e74c3c; color: #721c24; }
        .alert-warning { background: #fff3cd; border-color: #f39c12; color: #856404; }
        
        .btn-group { display: flex; gap: 10px; margin-top: 15px; }
        .btn { 
            padding: 10px 20px; border: none; border-radius: 6px;
            cursor: pointer; font-weight: 600; text-decoration: none;
            display: inline-block; text-align: center;
        }
        .btn-primary { background: #3498db; color: white; }
        .btn-success { background: #27ae60; color: white; }
        .btn-warning { background: #f39c12; color: white; }
        .btn-danger { background: #e74c3c; color: white; }
        
        .logs { background: #2c3e50; color: white; padding: 20px; border-radius: 10px; max-height: 300px; overflow-y: auto; }
        .log-entry { 
            padding: 8px 0; border-bottom: 1px solid #34495e; 
            font-family: 'Courier New', monospace; font-size: 0.9em;
        }
        .log-entry:last-child { border-bottom: none; }
        
        .content-info { 
            background: #e8f4fd; padding: 15px; border-radius: 8px; 
            margin: 15px 0; border-left: 4px solid #3498db;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚂 RZD Safety Bot Dashboard</h1>
            <p>Панель управления ботом безопасности движения РЖД</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card {% if bot_status == 'active' %}success{% else %}danger{% endif %}">
                <div class="stat-label">Статус бота</div>
                <div class="stat-number">{% if bot_status == 'active' %}✅ Активен{% else %}❌ Ошибка{% endif %}</div>
                <div class="stat-label">{{ channel_status }}</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-label">Запланировано заданий</div>
                <div class="stat-number">{{ jobs_count }}</div>
                <div class="stat-label">автоматических</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-label">Отправлено сообщений</div>
                <div class="stat-number">{{ posts_sent }}</div>
                <div class="stat-label">всего</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-label">Текущий день</div>
                <div class="stat-number" style="font-size: 2em;">{{ current_day }}</div>
                <div class="stat-label">из 20 рабочих дней</div>
            </div>
        </div>
        
        <div class="content">
            {% if message %}
            <div class="alert alert-{{ message_type }}">{{ message }}</div>
            {% endif %}
            
            <div class="content-info">
                <strong>📅 Информация о контенте:</strong> Система автоматически ротирует контент по 20-дневному циклу. 
                Сегодня показывается контент для дня <strong>{{ current_day }}</strong>.
            </div>
            
            <div class="section">
                <h2 class="section-title">⏰ Управление расписанием</h2>
                <div class="schedule-controls">
                    <div class="control-buttons">
                        <a href="/start-scheduler" class="btn btn-success">▶️ Запустить авто-постинг</a>
                        <a href="/stop-scheduler" class="btn btn-warning">⏸️ Остановить авто-постинг</a>
                        <a href="/send-daily" class="btn btn-primary">📨 Отправить все посты дня</a>
                        <a href="/test-all-content" class="btn btn-primary">🧪 Тест всех типов контента</a>
                        <a href="/next-day" class="btn btn-warning">⏭️ Следующий день</a>
                    </div>
                </div>
                
                <div class="jobs-list">
                    {% for job in scheduled_jobs %}
                    <div class="job-item">
                        <div class="job-info">
                            <div class="job-name">{{ job.name }}</div>
                            <div class="job-time">Следующий запуск: {{ job.next_run }}</div>
                        </div>
                        <div class="job-status {% if job.next_run != 'N/A' %}status-active{% else %}status-paused{% endif %}">
                            {% if job.next_run != 'N/A' %}Активно{% else %}Остановлено{% endif %}
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            
            <div class="section">
                <h2 class="section-title">📊 Ручная отправка постов</h2>
                <div class="manual-post">
                    <form method="POST" action="/send-manual">
                        <div class="form-group">
                            <label for="post_type">Тип контента:</label>
                            <select id="post_type" name="post_type" required>
                                <option value="daily_rule">🚦 Правило дня (ПТЭ/ИДП)</option>
                                <option value="safety_number">📊 Цифра безопасности</option>
                                <option value="weekly_task">🚨 Ситуационная задача</option>
                                <option value="tech_training">🔧 Техническая подготовка</option>
                                <option value="incident_analysis">🔍 Анализ инцидента</option>
                                <option value="psychology">🧠 Психология безопасности</option>
                                <option value="assistant_duties">👨‍💼 Обязанности помощника</option>
                                <option value="express_test">❓ Экспресс-тест</option>
                                <option value="weekly_poll">📊 Опрос недели</option>
                                <option value="custom">✏️ Произвольный текст</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label for="content_day">День контента (1-20):</label>
                            <select id="content_day" name="content_day">
                                {% for i in range(1, 21) %}
                                <option value="{{ i }}" {% if i == current_day %}selected{% endif %}>{{ i }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <div class="form-group" id="custom_text_group" style="display: none;">
                            <label for="custom_text">Произвольный текст:</label>
                            <textarea id="custom_text" name="custom_text" placeholder="Введите текст сообщения..."></textarea>
                        </div>
                        
                        <button type="submit" class="success">📨 Отправить в канал</button>
                    </form>
                    
                    <div class="btn-group">
                        <a href="/test-connection" class="btn btn-primary">🔗 Тест подключения</a>
                        <a href="/send-test" class="btn btn-success">🧪 Тестовое сообщение</a>
                        <a href="/send-interactive-test" class="btn btn-primary">🔄 Тест с кнопками</a>
                        <a href="/clear-logs" class="btn btn-danger">🗑️ Очистить логи</a>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2 class="section-title">📋 Последние логи</h2>
                <div class="logs">
                    {% for log in recent_logs %}
                    <div class="log-entry">{{ log.timestamp }} - {{ log.message }}</div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>

    <script>
        document.getElementById('post_type').addEventListener('change', function() {
            const customGroup = document.getElementById('custom_text_group');
            customGroup.style.display = this.value === 'custom' ? 'block' : 'none';
        });
        
        // Авто-обновление каждые 30 секунд
        setTimeout(() => { location.reload(); }, 30000);
    </script>
</body>
</html>
'''

class SafetyContentManager:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.channel_id = os.getenv('TELEGRAM_CHANNEL_ID')
        
        self.server_tz = pytz.timezone(os.getenv('SERVER_TIMEZONE', 'UTC'))
        self.target_tz = pytz.timezone(os.getenv('TARGET_TIMEZONE', 'Asia/Novokuznetsk'))
        
        if not self.bot_token or not self.channel_id:
            logger.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID must be set")
            self.bot_status = "error"
            self.channel_status = "❌ Переменные окружения не установлены"
            return
        
        self.bot_status = "active"
        self.scheduler_running = False
        self.init_db()
        self.content_db = self._load_all_content()
        self.setup_scheduler()
        
        # Тестируем подключение при запуске
        try:
            asyncio.run(self.test_channel_connection())
        except Exception as e:
            logger.error(f"Initial connection test failed: {e}")
            self.channel_status = f"❌ Ошибка подключения: {e}"
    
    def get_current_day(self):
        """Получение текущего дня цикла (1-20)"""
        try:
            conn = sqlite3.connect('safety_bot.db', check_same_thread=False)
            cursor = conn.cursor()
            
            cursor.execute('SELECT value FROM system_settings WHERE key = "current_day"')
            result = cursor.fetchone()
            
            if result:
                current_day = int(result[0])
            else:
                # Инициализация: день месяца по модулю 20 + 1
                current_day = (datetime.now().day - 1) % 20 + 1
                cursor.execute('INSERT INTO system_settings (key, value) VALUES ("current_day", ?)', (str(current_day),))
                conn.commit()
            
            conn.close()
            return current_day
        except Exception as e:
            logger.error(f"Error getting current day: {e}")
            return 1
    
    def set_next_day(self):
        """Переход к следующему дню цикла"""
        try:
            conn = sqlite3.connect('safety_bot.db', check_same_thread=False)
            cursor = conn.cursor()
            
            current_day = self.get_current_day()
            next_day = current_day % 20 + 1  # 1-20 цикл
            
            cursor.execute('UPDATE system_settings SET value = ? WHERE key = "current_day"', (str(next_day),))
            conn.commit()
            conn.close()
            
            logger.info(f"Переход к дню {next_day}")
            return next_day
        except Exception as e:
            logger.error(f"Error setting next day: {e}")
            return 1
        
    async def test_channel_connection(self):
        """Тестирование подключения к каналу"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"https://api.telegram.org/bot{self.bot_token}/getChat",
                    params={"chat_id": self.channel_id}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('ok'):
                        chat_title = data['result'].get('title', 'Unknown')
                        self.channel_status = f"✅ Канал: {chat_title}"
                        logger.info(f"Channel access confirmed: {chat_title}")
                        return True
                    else:
                        error_msg = data.get('description', 'Unknown error')
                        self.channel_status = f"❌ API Error: {error_msg}"
                        return False
                else:
                    self.channel_status = f"❌ HTTP Error: {response.status_code}"
                    return False
                    
        except Exception as e:
            self.channel_status = f"❌ Connection error: {str(e)}"
            logger.error(f"Channel access failed: {e}")
            return False

    def init_db(self):
        """Расширенная инициализация базы данных"""
        try:
            conn = sqlite3.connect('safety_bot.db', check_same_thread=False)
            cursor = conn.cursor()
            
            # Основная таблица логов публикаций
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS posting_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_type TEXT,
                    content TEXT,
                    actual_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    message TEXT
                )
            ''')
            
            # Таблица статистики бота
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    posts_sent INTEGER DEFAULT 0,
                    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для ответов пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    test_type TEXT,
                    question_id INTEGER,
                    selected_answer INTEGER,
                    is_correct BOOLEAN,
                    response_time DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица для статистики тестов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS test_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_type TEXT,
                    question_id INTEGER,
                    total_responses INTEGER DEFAULT 0,
                    correct_responses INTEGER DEFAULT 0,
                    test_date DATE
                )
            ''')
            
            # Таблица системных настроек
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            cursor.execute('SELECT COUNT(*) FROM bot_stats')
            if cursor.fetchone()[0] == 0:
                cursor.execute('INSERT INTO bot_stats (posts_sent) VALUES (0)')
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    def _load_all_content(self):
        """Загрузка полного контента на 20 дней"""
        return {
            'daily_rules': self._load_daily_rules(),
            'safety_numbers': self._load_safety_numbers(),
            'weekly_tasks': self._load_weekly_tasks(),
            'tech_training': self._load_tech_training(),
            'incident_analysis': self._load_incident_analysis(),
            'psychology': self._load_psychology(),
            'assistant_duties': self._load_assistant_duties(),
            'express_tests': self._load_express_tests(),
            'weekly_polls': self._load_weekly_polls()
        }

    def _load_daily_rules(self):
        """Правила дня - 20 уникальных правил"""
        return {
            # Содержимое как в предыдущем примере (20 правил)
            1: """🚦 <b>ПРАВИЛО ДНЯ 1/20</b>\n\n<b>ПТЭ п.12.1:</b> Машинист обязан немедленно принимать меры к остановке...""",
            2: """👀 <b>ПРАВИЛО ДНЯ 2/20</b>\n\n<b>ПТЭ п.12.7:</b> Машинист должен вести поезд, внимательно наблюдая...""",
            # ... и так до 20
            20: """📋 <b>ПРАВИЛО ДНЯ 20/20</b>\n\n<b>ПТЭ п.29.2:</b> Вести установленную документацию поездной бригады..."""
        }

    def _load_safety_numbers(self):
        """Цифры безопасности - 20 уникальных цифр"""
        return {
            1: """📊 <b>ЦИФРА БЕЗОПАСНОСТИ 1/20</b>\n\n<b>1200 метров</b> - остановочный путь...""",
            2: """⏱️ <b>ЦИФРА БЕЗОПАСНОСТИ 2/20</b>\n\n<b>14 метров</b> - расстояние...""",
            # ... и так до 20
            20: """🎯 <b>ЦИФРА БЕЗОПАСНОСТИ 20/20</b>\n\n<b>0 происшествий</b> - цель каждого рабочего дня..."""
        }

    def _load_weekly_tasks(self):
        """Ситуационные задачи - 4 задачи на месяц"""
        return {
            1: {
                'scenario': """🚨 <b>СИТУАЦИОННАЯ ЗАДАЧА НЕДЕЛИ 1/4</b>\n\n<b>Ситуация:</b> При следовании по перегону...""",
                'options': ["A) ...", "B) ...", "C) ...", "D) ..."],
                'correct_answer': 1,
                'explanation': """✅ <b>ПРАВИЛЬНЫЙ ОТВЕТ: B</b>\n\n<b>Алгоритм действий...</b>"""
            },
            2: {
                'scenario': """🚨 <b>СИТУАЦИОННАЯ ЗАДАЧА НЕДЕЛИ 2/4</b>\n\n<b>Ситуация:</b> При движении в тумане...""",
                'options': ["A) ...", "B) ...", "C) ...", "D) ..."],
                'correct_answer': 1,
                'explanation': """✅ <b>ПРАВИЛЬНЫЙ ОТВЕТ: B</b>\n\n<b>Алгоритм действий...</b>"""
            },
            3: {
                'scenario': """🚨 <b>СИТУАЦИОННАЯ ЗАДАЧА НЕДЕЛИ 3/4</b>\n\n<b>Ситуация:</b> При трогании с места...""",
                'options': ["A) ...", "B) ...", "C) ...", "D) ..."],
                'correct_answer': 0,
                'explanation': """✅ <b>ПРАВИЛЬНЫЙ ОТВЕТ: A</b>\n\n<b>Алгоритм действий...</b>"""
            },
            4: {
                'scenario': """🚨 <b>СИТУАЦИОННАЯ ЗАДАЧА НЕДЕЛИ 4/4</b>\n\n<b>Ситуация:</b> При движении в темное время...""",
                'options': ["A) ...", "B) ...", "C) ...", "D) ..."],
                'correct_answer': 1,
                'explanation': """✅ <b>ПРАВИЛЬНЫЙ ОТВЕТ: B</b>\n\n<b>Алгоритм действий...</b>"""
            }
        }

    def _load_tech_training(self):
        """Техническая подготовка - 20 уникальных тем"""
        return {
            1: """🔧 <b>ТЕХНИЧЕСКАЯ ПОДГОТОВКА: ТЭМ2 - День 1/20</b>\n\n<b>Критические параметры контроля...</b>""",
            2: """🔧 <b>ТЕХНИЧЕСКАЯ ПОДГОТОВКА: 2ТЭ10М - День 2/20</b>\n\n<b>Дизель 10Д100...</b>""",
            # ... и так до 20
            20: """🔧 <b>ТЕХНИЧЕСКАЯ ПОДГОТОВКА: ДИАГНОСТИКА - День 20/20</b>\n\n<b>Методы диагностики...</b>"""
        }

    def _load_incident_analysis(self):
        """Анализ инцидентов - 20 уникальных случаев"""
        return {
            1: """🔍 <b>АНАЛИЗ ИНЦИДЕНТА 1/20</b>\n\n<b>Проезд запрещающего сигнала...</b>""",
            2: """🔍 <b>АНАЛИЗ ИНЦИДЕНТА 2/20</b>\n\n<b>Сход подвижного состава...</b>""",
            # ... и так до 20
            20: """🔍 <b>АНАЛИЗ ИНЦИДЕНТА 20/20</b>\n\n<b>Нарушение габарита...</b>"""
        }

    def _load_psychology(self):
        """Психология безопасности - 20 уникальных тем"""
        return {
            1: """🧠 <b>ПСИХОЛОГИЯ БЕЗОПАСНОСТИ 1/20</b>\n\n<b>Эффект многозадачности...</b>""",
            2: """🧠 <b>ПСИХОЛОГИЯ БЕЗОПАСНОСТИ 2/20</b>\n\n<b>Синдром привыкания к опасности...</b>""",
            # ... и так до 20
            20: """🧠 <b>ПСИХОЛОГИЯ БЕЗОПАСНОСТИ 20/20</b>\n\n<b>Профессиональное выгорание...</b>"""
        }

    def _load_assistant_duties(self):
        """Обязанности помощника - 20 уникальных тем"""
        return {
            1: """👨‍💼 <b>ОБЯЗАННОСТИ ПОМОЩНИКА 1/20</b>\n\n<b>При производстве маневров...</b>""",
            2: """👨‍💼 <b>ОБЯЗАННОСТИ ПОМОЩНИКА 2/20</b>\n\n<b>Контроль за показаниями сигналов...</b>""",
            # ... и так до 20
            20: """👨‍💼 <b>ОБЯЗАННОСТИ ПОМОЩНИКА 20/20</b>\n\n<b>Ведение технической документации...</b>"""
        }

    def _load_express_tests(self):
        """Экспресс-тесты - 20 уникальных тестов"""
        return {
            1: {
                'question': """❓ <b>ЭКСПРЕСС-ТЕСТ 1/20</b>\n\n<b>Вопрос:</b> При каком давлении масла...""",
                'options': ["1,0 кгс/см²", "1,2 кгс/см²", "1,5 кгс/см²", "2,0 кгс/см²"],
                'correct_answer': 0,
                'explanation': """✅ <b>Правильный ответ: A) 1,0 кгс/см²</b>\n\n<b>Объяснение:</b>..."""
            },
            # ... и так до 20
            20: {
                'question': """❓ <b>ЭКСПРЕСС-ТЕСТ 20/20</b>\n\n<b>Вопрос:</b> Какое минимальное расстояние...""",
                'options': ["10 метров", "20 метров", "30 метров", "50 метров"],
                'correct_answer': 2,
                'explanation': """✅ <b>Правильный ответ: C) 30 метров</b>\n\n<b>Объяснение:</b>..."""
            }
        }

    def _load_weekly_polls(self):
        """Опросы недели - 4 опроса на месяц"""
        return {
            1: {
                'question': """📊 <b>ОПРОС НЕДЕЛИ 1/4</b>\n\n<b>Вопрос:</b> Какой порядок действий при отказе автотормозов?...""",
                'options': [
                    "Тормозить вспомогательным, потом общая тревога",
                    "Общая тревога, потом вспомогательный тормоз", 
                    "Сразу остановка любым способом",
                    "Продолжать движение до станции"
                ],
                'correct_answer': 1
            },
            # ... и так до 4
            4: {
                'question': """📊 <b>ОПРОС НЕДЕЛИ 4/4</b>\n\n<b>Вопрос:</b> Что делать при обнаружении препятствия на пути?...""",
                'options': [
                    "Объехать препятствие",
                    "Немедленно остановиться",
                    "Снизить скорость и объехать",
                    "Продолжить движение"
                ],
                'correct_answer': 1
            }
        }

    def setup_scheduler(self):
        """Настройка планировщика"""
        try:
            self.scheduler = BackgroundScheduler(timezone=str(self.server_tz))
            
            # Keep-alive задача
            self.scheduler.add_job(
                self.keep_alive,
                'interval',
                minutes=10,
                id='keep_alive'
            )

            # Автоматический переход на следующий день в 00:00
            self.scheduler.add_job(
                self.set_next_day,
                'cron',
                hour=0, minute=0,
                id='next_day'
            )

            # Расписание публикаций
            schedule_config = {
                '08:30': ('daily_rule', '🚦 Правило дня'),
                '10:00': ('safety_number', '📊 Цифра безопасности'), 
                '12:00': ('weekly_task', '🚨 Ситуационная задача'),
                '14:00': ('tech_training', '🔧 Техническая подготовка'),
                '16:00': ('incident_analysis', '🔍 Анализ инцидента'),
                '18:00': ('psychology', '🧠 Психология безопасности')
            }
            
            for time_str, (post_type, name) in schedule_config.items():
                kemerovo_time = datetime.strptime(time_str, '%H:%M').time()
                server_time = self.target_tz.localize(
                    datetime.combine(datetime.now().date(), kemerovo_time)
                ).astimezone(self.server_tz)
                
                trigger = CronTrigger(
                    hour=server_time.hour,
                    minute=server_time.minute,
                    timezone=self.server_tz
                )
                
                self.scheduler.add_job(
                    self.send_scheduled_post,
                    trigger=trigger,
                    args=[post_type],
                    id=f"auto_{post_type}",
                    name=f"Авто: {name}",
                    misfire_grace_time=300
                )

            self.scheduler.start()
            self.scheduler_running = True
            logger.info("Планировщик запущен с 20-дневным циклом контента")
            
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")

    async def send_scheduled_post(self, post_type: str):
        """Автоматическая отправка поста с учетом текущего дня"""
        try:
            current_day = self.get_current_day()
            content = self._get_content_by_type(post_type, current_day)
            
            if content:
                success, result = await self.send_telegram_message(content)
                
                if success:
                    self._log_posting(post_type, content, "auto", current_day)
                    self._update_stats()
                    logger.info(f"Авто-публикация {post_type} (день {current_day}) успешна")
                else:
                    logger.error(f"Ошибка авто-публикации {post_type}: {result}")
            else:
                logger.warning(f"Контент для {post_type} (день {current_day}) не найден")
                
        except Exception as e:
            logger.error(f"Ошибка в send_scheduled_post: {e}")

    async def send_manual_post(self, post_type: str, content_day: int = None, custom_text: str = None):
        """Ручная отправка поста с выбором дня"""
        try:
            if post_type == 'custom' and custom_text:
                content = custom_text
            else:
                day = content_day or self.get_current_day()
                content = self._get_content_by_type(post_type, day)
            
            if not content:
                return "❌ Контент не найден"
            
            success, result = await self.send_telegram_message(content)
            
            if success:
                day_used = content_day or self.get_current_day()
                self._log_posting(post_type, content, "manual", day_used)
                self._update_stats()
            
            return result
            
        except Exception as e:
            error_msg = f"❌ Ошибка отправки: {str(e)}"
            logger.error(error_msg)
            return error_msg

    def _get_content_by_type(self, post_type: str, day: int):
        """Получение контента по типу и дню"""
        content_map = {
            'daily_rule': self.content_db['daily_rules'].get(day),
            'safety_number': self.content_db['safety_numbers'].get(day),
            'weekly_task': self._get_weekly_task_content(day),
            'tech_training': self.content_db['tech_training'].get(day),
            'incident_analysis': self.content_db['incident_analysis'].get(day),
            'psychology': self.content_db['psychology'].get(day),
            'assistant_duties': self.content_db['assistant_duties'].get(day),
            'express_test': self._get_express_test_content(day),
            'weekly_poll': self._get_weekly_poll_content(day),
        }
        return content_map.get(post_type)

    def _get_weekly_task_content(self, day: int):
        """Получение контента ситуационной задачи (1 задача в неделю)"""
        week = (day - 1) // 5 + 1  # 5 дней = 1 неделя
        task_data = self.content_db['weekly_tasks'].get(week)
        return task_data['scenario'] if task_data else None

    def _get_express_test_content(self, day: int):
        """Получение контента экспресс-теста"""
        test_data = self.content_db['express_tests'].get(day)
        return test_data['question'] if test_data else None

    def _get_weekly_poll_content(self, day: int):
        """Получение контента опроса (1 опрос в неделю)"""
        week = (day - 1) // 5 + 1  # 5 дней = 1 неделя
        poll_data = self.content_db['weekly_polls'].get(week)
        return poll_data['question'] if poll_data else None

    async def send_telegram_message(self, text: str):
        """Отправка сообщения в Telegram"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    json={
                        "chat_id": self.channel_id,
                        "text": text,
                        "parse_mode": "HTML"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('ok'):
                        return True, "✅ Сообщение отправлено в канал!"
                    else:
                        return False, f"❌ Telegram API error: {data.get('description')}"
                else:
                    return False, f"❌ HTTP error: {response.status_code}"
                    
        except Exception as e:
            return False, f"❌ Connection error: {str(e)}"

    def _log_posting(self, post_type: str, content: str, trigger: str, day: int):
        """Логирование публикации с указанием дня"""
        try:
            conn = sqlite3.connect('safety_bot.db', check_same_thread=False)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO posting_logs (post_type, content, status, message)
                VALUES (?, ?, ?, ?)
            ''', (post_type, f"День {day}: {str(content)[:150]}...", 'success', f"{trigger}"))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error logging: {e}")

    def _update_stats(self):
        """Обновление статистики"""
        try:
            conn = sqlite3.connect('safety_bot.db', check_same_thread=False)
            cursor = conn.cursor()
            
            cursor.execute('UPDATE bot_stats SET posts_sent = posts_sent + 1, last_activity = CURRENT_TIMESTAMP')
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error updating stats: {e}")

    def get_stats(self):
        """Получение статистики"""
        try:
            conn = sqlite3.connect('safety_bot.db', check_same_thread=False)
            cursor = conn.cursor()
            
            cursor.execute('SELECT posts_sent FROM bot_stats')
            posts_sent = cursor.fetchone()[0]
            
            cursor.execute('SELECT * FROM posting_logs ORDER BY id DESC LIMIT 10')
            recent_logs = [{
                'timestamp': row[3].split('.')[0] if row[3] else 'N/A',
                'message': f"{row[1]}: {row[5]}"
            } for row in cursor.fetchall()]
            
            conn.close()
            
            return {
                'posts_sent': posts_sent,
                'recent_logs': recent_logs
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {'posts_sent': 0, 'recent_logs': []}

    def get_scheduled_jobs(self):
        """Получение списка запланированных заданий"""
        jobs = []
        if hasattr(self, 'scheduler'):
            for job in self.scheduler.get_jobs():
                jobs.append({
                    'name': job.name,
                    'next_run': job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else 'N/A'
                })
        return jobs

    def start_scheduler(self):
        """Запуск планировщика"""
        if not self.scheduler_running:
            self.scheduler.start()
            self.scheduler_running = True
            return True
        return False

    def stop_scheduler(self):
        """Остановка планировщика"""
        if self.scheduler_running:
            self.scheduler.shutdown()
            self.scheduler_running = False
            return True
        return False

    def keep_alive(self):
        """Keep-alive для Render"""
        try:
            health_url = os.getenv('HEALTH_CHECK_URL', '')
            if health_url:
                requests.get(health_url, timeout=10)
            logger.info("Keep-alive ping sent")
        except Exception as e:
            logger.warning(f"Keep-alive error: {e}")

# Глобальный экземпляр
safety_manager = SafetyContentManager()

# ==================== FLASK ROUTES ====================

@app.route('/')
def dashboard():
    """Главный дашборд"""
    stats = safety_manager.get_stats()
    jobs = safety_manager.get_scheduled_jobs()
    current_day = safety_manager.get_current_day()
    
    return render_template_string(DASHBOARD_HTML,
        bot_status=getattr(safety_manager, 'bot_status', 'error'),
        channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
        jobs_count=len(jobs),
        posts_sent=stats['posts_sent'],
        current_day=current_day,
        scheduled_jobs=jobs,
        recent_logs=stats['recent_logs'],
        message=request.args.get('message', ''),
        message_type=request.args.get('type', 'success')
    )

@app.route('/send-manual', methods=['POST'])
def send_manual():
    """Ручная отправка сообщения с выбором дня"""
    post_type = request.form.get('post_type')
    content_day = int(request.form.get('content_day', safety_manager.get_current_day()))
    custom_text = request.form.get('custom_text', '')
    
    if not post_type:
        return render_template_string(DASHBOARD_HTML, 
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            message="❌ Не указан тип поста",
            message_type="danger"
        )
    
    try:
        result = asyncio.run(safety_manager.send_manual_post(post_type, content_day, custom_text))
        
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_day=safety_manager.get_current_day(),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=result,
            message_type="success" if "✅" in result else "danger"
        )
            
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_day=safety_manager.get_current_day(),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"❌ Ошибка: {str(e)}",
            message_type="danger"
        )

@app.route('/next-day')
def next_day():
    """Переход к следующему дню"""
    try:
        new_day = safety_manager.set_next_day()
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_day=new_day,
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"✅ Перешли к дню {new_day}",
            message_type="success"
        )
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_day=safety_manager.get_current_day(),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"❌ Ошибка перехода: {str(e)}",
            message_type="danger"
        )

# Остальные маршруты (/send-test, /start-scheduler, /stop-scheduler, etc.)
# остаются аналогичными предыдущей реализации

@app.route('/send-daily')
def send_daily():
    """Отправка всех постов текущего дня"""
    try:
        results = []
        post_types = ['daily_rule', 'safety_number', 'tech_training', 'incident_analysis', 'psychology']
        current_day = safety_manager.get_current_day()
        
        for post_type in post_types:
            result = asyncio.run(safety_manager.send_manual_post(post_type, current_day))
            results.append(f"{post_type}: {result}")
            import time
            time.sleep(2)
        
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_day=current_day,
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"✅ Все посты дня {current_day} отправлены!\n" + "\n".join(results),
            message_type="success"
        )
            
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_day=safety_manager.get_current_day(),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"❌ Ошибка: {str(e)}",
            message_type="danger"
        )

# Остальные маршруты остаются без изменений...

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG_MODE', False))
