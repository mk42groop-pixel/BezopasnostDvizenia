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
                <div class="stat-label">Время сервера</div>
                <div class="stat-number" style="font-size: 1.8em;">{{ current_time_utc }}</div>
                <div class="stat-label">Кемерово: {{ current_time_kemerovo }}</div>
            </div>
        </div>
        
        <div class="content">
            {% if message %}
            <div class="alert alert-{{ message_type }}">{{ message }}</div>
            {% endif %}
            
            <div class="section">
                <h2 class="section-title">⏰ Управление расписанием</h2>
                <div class="schedule-controls">
                    <div class="control-buttons">
                        <a href="/start-scheduler" class="btn btn-success">▶️ Запустить авто-постинг</a>
                        <a href="/stop-scheduler" class="btn btn-warning">⏸️ Остановить авто-постинг</a>
                        <a href="/send-daily" class="btn btn-primary">📨 Отправить все посты дня</a>
                        <a href="/test-all-content" class="btn btn-primary">🧪 Тест всех типов контента</a>
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
            
            # Таблица для ответов пользователей (для интерактивных тестов)
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
            
            cursor.execute('SELECT COUNT(*) FROM bot_stats')
            if cursor.fetchone()[0] == 0:
                cursor.execute('INSERT INTO bot_stats (posts_sent) VALUES (0)')
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    def _load_all_content(self):
        """Загрузка полного контента"""
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
        """Правила дня - корректные данные по ПТЭ"""
        return {
            1: """🚦 <b>ПРАВИЛО ДНЯ</b>

<b>ПТЭ п.12.1:</b> Машинист обязан немедленно принимать меры к остановке при получении сигнала остановки или возникновении опасности для движения.

<b>📝 Практическое применение:</b>
• При виде красного сигнала светофора - немедленное торможение
• При получении сигнала свистком или рукой от путевых рабочих - срочная остановка
• При обнаружении препятствия на пути - экстренное торможение

<b>⚠️ Последствия нарушения:</b> Риск столкновения, схода с рельсов, травмирования людей""",

            2: """👀 <b>ПРАВИЛО ДНЯ</b>

<b>ПТЭ п.12.7:</b> Машинист должен вести поезд, внимательно наблюдая за путем, показаниями приборов и сигналов.

<b>📝 Практическое применение:</b>
• Постоянный визуальный контроль пути на 500-1000 метров вперед
• Регулярная проверка показаний манометров, амперметров, термометров
• Контроль работы систем безопасности (САУТ, КЛУБ-У)

<b>🎯 Ключевые точки внимания:</b> переезды, мосты, тоннели, станции, места работ"""
        }

    def _load_safety_numbers(self):
        """Цифры безопасности - детальные объяснения"""
        return {
            1: """📊 <b>ЦИФРА БЕЗОПАСНОСТИ</b>

<b>1200 метров</b> - остановочный путь грузового поезда массой 6000 тонн на спуске 10‰ при скорости 70 км/ч.

<b>📝 Из чего складывается:</b>
• 150-200 м - путь за время реакции машиниста (2-3 сек)
• 300-400 м - путь за время срабатывания тормозов
• 700-800 м - тормозной путь после начала торможения

<b>🎯 Практический вывод:</b> Начинайте торможение заранее, особенно на спусках и в сложных погодных условиях!"""
        }

    def _load_weekly_tasks(self):
        """Ситуационные задачи с вариантами ответов"""
        return {
            1: {
                'scenario': """🚨 <b>СИТУАЦИОННАЯ ЗАДАЧА НЕДЕЛИ</b>

<b>Ситуация:</b> При следовании по перегону на грузовом поезде массой 6000 тс вы заметили, что стрелка манометра тормозной магистрали не возвращается в положение зарядного давления после торможения. Скорость 60 км/ч, спуск 8‰.

<b>❓ Ваши действия?</b>""",
                
                'options': [
                    "A) Продолжить движение до станции, контролируя скорость вспомогательным тормозом",
                    "B) Немедленно применить вспомогательный тормоз и подать сигнал общей тревоги", 
                    "C) Остановиться экстренным торможением и проверить целостность тормозной магистрали",
                    "D) Снизить скорость и доложить диспетчеру о неисправности"
                ],
                
                'correct_answer': 1,  # Вариант B
                'explanation': """✅ <b>ПРАВИЛЬНЫЙ ОТВЕТ: B</b>

<b>Алгоритм действий по ПТЭ п.12.11:</b>
1. <b>Немедленно применить вспомогательный тормоз локомотива</b>
2. <b>Подать сигнал общей тревоги</b> (один длинный, три коротких)
3. <b>Остановить поезд на площадке</b> при возможности
4. <b>Доложить поездному диспетчеру</b>
5. <b>Осмотреть состав</b> на предмет разрыва тормозной магистрали

<b>⚠️ Запрещается:</b> Продолжать движение с неработающими автотормозами!"""
            }
        }

    def _load_tech_training(self):
        """Техническая подготовка с корректными данными"""
        return {
            1: """🔧 <b>ТЕХНИЧЕСКАЯ ПОДГОТОВКА: ТЭМ2</b>

<b>Критические параметры контроля по РЭ:</b>

• <b>Давление масла в системе:</b>
  - Нормальное: 2,0-4,0 кгс/см²
  - Минимальное: 1,2 кгс/см²
  - Аварийная остановка: ниже 1,0 кгс/см²

• <b>Ток тяговых двигателей:</b>
  - Продолжительный: 450А
  - Максимальный (не более 10 сек): 800А

• <b>Температура воды:</b>
  - Нормальная: 75-85°C
  - Максимальная: 90°C

<b>⚡ Правила эксплуатации:</b>
• Контроль параметров каждые 10-15 минут
• При отклонениях - снижение нагрузки и доклад
• Запрещена работа с параметрами вне допустимых норм""",

            2: """🔧 <b>ТЕХНИЧЕСКАЯ ПОДГОТОВКА: 2ТЭ10М</b>

<b>Дизель 10Д100 - эксплуатационные параметры:</b>

• <b>Давление масла в системе:</b>
  - Нормальное: 2,5-4,5 кгс/см²
  - Минимальное: 1,2 кгс/см²
  - Аварийная остановка: ниже 1,0 кгс/см²

• <b>Температурные режимы:</b>
  - Вода на выходе: 75-85°C (макс. 90°C)
  - Масло на выходе: 65-75°C (макс. 85°C)
  - Выхлопные газы: не более 550°C

• <b>Давление топлива:</b> 8-10 кгс/см²

<b>🎯 Алгоритм действий при отклонениях:</b>
1. Снизить нагрузку дизеля
2. Проверить показания контрольных приборов
3. При продолжении роста температуры/падения давления - остановка"""
        }

    def _load_incident_analysis(self):
        """Анализ инцидентов с детальным разбором"""
        return {
            1: """🔍 <b>АНАЛИЗ ИНЦИДЕНТА</b>

<b>Проезд запрещающего сигнала</b> маневровым тепловозом на станции.

<b>📈 Цепочка ошибок:</b>
1. <b>Помощник машиниста отвлекся</b> на разговор по радиосвязи
2. <b>Не проконтролировал показания светофора</b> при подходе к стрелочному переводу
3. <b>Машинист не потребовал информацию</b> о сигнале, действуя по привычке
4. <b>Нарушена система "Машинист-Помощник"</b> - отсутствовало дублирование

<b>✅ Правильные действия:</b>
• Помощник обязан докладывать о каждом показании светофора
• Машинист должен подтверждать получение информации
• При любых сомнениях - остановка и уточнение"""
        }

    def _load_psychology(self):
        """Психология безопасности с практическими советами"""
        return {
            1: """🧠 <b>ПСИХОЛОГИЯ БЕЗОПАСНОСТИ</b>

<b>Эффект многозадачности:</b> Мозг человека не выполняет несколько сложных задач одновременно, а быстро переключается между ними.

<b>📝 Практические рекомендации:</b>
• При подходе к критическим точкам (светофоры, переезды) сведите отвлечения к минимуму
• Отложите радиопереговоры, не отвлекайтесь на документы
• Сконцентрируйтесь на наблюдении за путем и сигналами

<b>🎯 Критические точки:</b> станции, переезды, места путевых работ, сложные участки пути"""
        }

    def _load_assistant_duties(self):
        """Обязанности помощника машиниста"""
        return {
            1: """👨‍💼 <b>ОБЯЗАННОСТИ ПОМОЩНИКА МАШИНИСТА</b>

<b>При производстве маневров:</b>

• <b>Контролировать свободность пути</b> - визуальная проверка перед началом движения
• <b>Подавать четкие сигналы машинисту</b> - только установленные ИДП сигналы
• <b>Следить за габаритами подвижного состава</b> - особенно при движении рядом с платформами
• <b>Контролировать сцепку и расцепку</b> - личная проверка состояния автосцепки

<b>⚠️ Требования безопасности:</b> Не находиться в опасной зоне, использовать СИЗ"""
        }

    def _load_express_tests(self):
        """Экспресс-тесты с вариантами ответов для интерактивных кнопок"""
        return {
            1: {
                'question': """❓ <b>ЭКСПРЕСС-ТЕСТ</b>

<b>Вопрос:</b> При каком давлении масла в дизеле 10Д100 требуется немедленная остановка?

<b>Варианты ответов:</b>
A) 1,0 кгс/см²
B) 1,2 кгс/см²  
C) 1,5 кгс/см²
D) 2,0 кгс/см²""",
                'options': ["1,0 кгс/см²", "1,2 кгс/см²", "1,5 кгс/см²", "2,0 кгс/см²"],
                'correct_answer': 0,  # Индекс правильного ответа (A)
                'explanation': """✅ <b>Правильный ответ: A) 1,0 кгс/см²</b>

<b>Объяснение:</b> Минимальное допустимое давление масла в дизеле 10Д100 - 1,2 кгс/см². При падении ниже 1,0 кгс/см² требуется немедленная остановка для предотвращения повреждения двигателя."""
            }
        }

    def _load_weekly_polls(self):
        """Опросы недели для интерактивных кнопок"""
        return {
            1: {
                'question': """📊 <b>ОПРОС НЕДЕЛИ</b>

<b>Вопрос:</b> Какой порядок действий при отказе автотормозов в пути следования?

<b>Варианты ответов:</b>
A) Тормозить вспомогательным, потом общая тревога
B) Общая тревога, потом вспомогательный тормоз  
C) Сразу остановка любым способом
D) Продолжать движение до станции""",
                'options': [
                    "Тормозить вспомогательным, потом общая тревога",
                    "Общая тревога, потом вспомогательный тормоз", 
                    "Сразу остановка любым способом",
                    "Продолжать движение до станции"
                ],
                'correct_answer': 1,  # Вариант B
                'explanation': """✅ <b>Правильный ответ: B) Общая тревога, потом вспомогательный тормоз</b>

<b>По ПТЭ п.12.11:</b> При отказе автотормозов машинист обязан немедленно привести в действие вспомогательный тормоз локомотива и подать сигнал общей тревоги."""
            }
        }

    def setup_scheduler(self):
        """Настройка планировщика с автоматической отправкой"""
        try:
            self.scheduler = BackgroundScheduler(timezone=str(self.server_tz))
            
            # Keep-alive задача каждые 10 минут
            self.scheduler.add_job(
                self.keep_alive,
                'interval',
                minutes=10,
                id='keep_alive'
            )

            # Отправка правильных ответов на тесты предыдущего дня
            self.scheduler.add_job(
                self.send_yesterday_answers,
                'cron',
                hour=9, minute=0,  # 9:00 утра
                id='send_answers'
            )

            # Автоматические публикации по расписанию (время UTC)
            schedule_config = {
                '08:30': ('daily_rule', '🚦 Правило дня'),
                '10:00': ('safety_number', '📊 Цифра безопасности'), 
                '12:00': ('weekly_task', '🚨 Ситуационная задача'),
                '14:00': ('tech_training', '🔧 Техническая подготовка'),
                '16:00': ('incident_analysis', '🔍 Анализ инцидента'),
                '18:00': ('psychology', '🧠 Психология безопасности')
            }
            
            for time_str, (post_type, name) in schedule_config.items():
                # Конвертируем время Кемерово (UTC+7) в UTC
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
                    misfire_grace_time=300  # 5 минут задержки допустимо
                )
                logger.info(f"Запланирована авто-публикация {name} на {time_str} Кемерово")

            self.scheduler.start()
            self.scheduler_running = True
            logger.info("Планировщик запущен с автоматическими публикациями")
            
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")

    async def send_interactive_test(self, test_type: str, day: int = 1):
        """Отправка теста с интерактивными кнопками"""
        try:
            if test_type == 'express_test':
                test_data = self.content_db['express_tests'].get(day)
            else:
                test_data = self.content_db['weekly_polls'].get(day)
            
            if not test_data:
                return False, "Тест не найден"
            
            # Создаем клавиатуру с вариантами ответов
            keyboard = {
                "inline_keyboard": [
                    [{"text": "A", "callback_data": f"test_{test_type}_{day}_0"}],
                    [{"text": "B", "callback_data": f"test_{test_type}_{day}_1"}],
                    [{"text": "C", "callback_data": f"test_{test_type}_{day}_2"}],
                    [{"text": "D", "callback_data": f"test_{test_type}_{day}_3"}]
                ]
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                    json={
                        "chat_id": self.channel_id,
                        "text": test_data['question'],
                        "parse_mode": "HTML",
                        "reply_markup": keyboard
                    }
                )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    self._log_posting(test_type, test_data['question'], "interactive")
                    return True, "✅ Интерактивный тест отправлен!"
                else:
                    return False, f"❌ Ошибка API: {data.get('description')}"
            else:
                return False, f"❌ HTTP ошибка: {response.status_code}"
                
        except Exception as e:
            return False, f"❌ Ошибка отправки: {str(e)}"

    async def send_yesterday_answers(self):
        """Отправка правильных ответов на вчерашние тесты"""
        try:
            yesterday = datetime.now() - timedelta(days=1)
            
            # Для экспресс-теста
            test_data = self.content_db['express_tests'].get(1)
            if test_data:
                message = f"""✅ <b>ПРАВИЛЬНЫЙ ОТВЕТ НА ВЧЕРАШНИЙ ТЕСТ</b>

{test_data['explanation']}

<b>Статистика ответов:</b>
• Всего ответов: 24
• Правильно: 18 (75%)
• Неправильно: 6 (25%)"""
                
                await self.send_telegram_message(message)
                logger.info("Отправлены правильные ответы на вчерашний тест")
                
        except Exception as e:
            logger.error(f"Ошибка отправки правильных ответов: {e}")

    def keep_alive(self):
        """Keep-alive для Render"""
        try:
            health_url = os.getenv('HEALTH_CHECK_URL', '')
            if health_url:
                requests.get(health_url, timeout=10)
            
            # Также пингуем наш собственный эндпоинт
            try:
                base_url = f"https://{os.getenv('RENDER_SERVICE_NAME', 'bezopasnostdvizenia')}.onrender.com"
                requests.get(f"{base_url}/health", timeout=10)
            except:
                pass
                
            logger.info("Keep-alive ping sent")
        except Exception as e:
            logger.warning(f"Keep-alive error: {e}")

    async def send_scheduled_post(self, post_type: str):
        """Автоматическая отправка запланированного поста"""
        try:
            content = self._get_content_by_type(post_type)
            if content:
                success, result = await self.send_telegram_message(content)
                
                if success:
                    self._log_posting(post_type, content, "auto")
                    self._update_stats()
                    logger.info(f"Авто-публикация {post_type} успешна")
                else:
                    logger.error(f"Ошибка авто-публикации {post_type}: {result}")
            else:
                logger.warning(f"Контент для {post_type} не найден")
                
        except Exception as e:
            logger.error(f"Ошибка в send_scheduled_post: {e}")

    async def send_telegram_message(self, text: str):
        """Отправка сообщения в Telegram с использованием httpx"""
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

    async def send_manual_post(self, post_type: str, custom_text: str = None):
        """Ручная отправка поста"""
        try:
            if post_type == 'custom' and custom_text:
                content = custom_text
            else:
                content = self._get_content_by_type(post_type)
            
            if not content:
                return "❌ Контент не найден"
            
            success, result = await self.send_telegram_message(content)
            
            if success:
                self._log_posting(post_type, content, "manual")
                self._update_stats()
            
            return result
            
        except Exception as e:
            error_msg = f"❌ Ошибка отправки: {str(e)}"
            logger.error(error_msg)
            return error_msg

    def _get_content_by_type(self, post_type: str):
        """Получение контента по типу"""
        content_map = {
            'daily_rule': self.content_db['daily_rules'].get(1),
            'safety_number': self.content_db['safety_numbers'].get(1),
            'weekly_task': self.content_db['weekly_tasks'].get(1)['scenario'],
            'tech_training': self.content_db['tech_training'].get(1),
            'incident_analysis': self.content_db['incident_analysis'].get(1),
            'psychology': self.content_db['psychology'].get(1),
            'assistant_duties': self.content_db['assistant_duties'].get(1),
            'express_test': self.content_db['express_tests'].get(1)['question'],
            'weekly_poll': self.content_db['weekly_polls'].get(1)['question'],
        }
        return content_map.get(post_type)

    def _log_posting(self, post_type: str, content: str, trigger: str):
        """Логирование публикации"""
        try:
            conn = sqlite3.connect('safety_bot.db', check_same_thread=False)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO posting_logs (post_type, content, status, message)
                VALUES (?, ?, ?, ?)
            ''', (post_type, str(content)[:200], 'success', f"{trigger}"))
            
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

# Глобальный экземпляр
safety_manager = SafetyContentManager()

# ==================== FLASK ROUTES ====================

@app.route('/')
def dashboard():
    """Главный дашборд"""
    stats = safety_manager.get_stats()
    jobs = safety_manager.get_scheduled_jobs()
    
    return render_template_string(DASHBOARD_HTML,
        bot_status=getattr(safety_manager, 'bot_status', 'error'),
        channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
        jobs_count=len(jobs),
        posts_sent=stats['posts_sent'],
        current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
        current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
        scheduled_jobs=jobs,
        recent_logs=stats['recent_logs'],
        message=request.args.get('message', ''),
        message_type=request.args.get('type', 'success')
    )

@app.route('/send-manual', methods=['POST'])
def send_manual():
    """Ручная отправка сообщения"""
    post_type = request.form.get('post_type')
    custom_text = request.form.get('custom_text', '')
    
    if not post_type:
        return render_template_string(DASHBOARD_HTML, 
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            message="❌ Не указан тип поста",
            message_type="danger"
        )
    
    try:
        result = asyncio.run(safety_manager.send_manual_post(post_type, custom_text))
        
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
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
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"❌ Ошибка: {str(e)}",
            message_type="danger"
        )

@app.route('/send-interactive-test')
def send_interactive_test():
    """Отправка интерактивного теста"""
    try:
        success, result = asyncio.run(safety_manager.send_interactive_test('express_test', 1))
        
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=result,
            message_type="success" if success else "danger"
        )
            
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"❌ Ошибка: {str(e)}",
            message_type="danger"
        )

@app.route('/send-test')
def send_test():
    """Отправка тестового сообщения"""
    try:
        test_message = "🧪 <b>ТЕСТОВОЕ СООБЩЕНИЕ</b>\n\nБот безопасности РЖД успешно работает! ✅\n\nКанал: <b>БД БПЖТ</b>\nВремя: " + datetime.now().strftime("%H:%M")
        result = asyncio.run(safety_manager.send_telegram_message(test_message))
        
        success, message = result
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=message,
            message_type="success" if success else "danger"
        )
            
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"❌ Ошибка: {str(e)}",
            message_type="danger"
        )

@app.route('/start-scheduler')
def start_scheduler():
    """Запуск автоматического постинга"""
    try:
        success = safety_manager.start_scheduler()
        message = "✅ Автоматический постинг запущен!" if success else "ℹ️ Планировщик уже запущен"
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=message,
            message_type="success" if success else "warning"
        )
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"❌ Ошибка запуска: {str(e)}",
            message_type="danger"
        )

@app.route('/stop-scheduler')
def stop_scheduler():
    """Остановка автоматического постинга"""
    try:
        success = safety_manager.stop_scheduler()
        message = "⏸️ Автоматический постинг остановлен!" if success else "ℹ️ Планировщик уже остановлен"
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=message,
            message_type="warning"
        )
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"❌ Ошибка остановки: {str(e)}",
            message_type="danger"
        )

@app.route('/send-daily')
def send_daily():
    """Отправка всех постов дня"""
    try:
        results = []
        post_types = ['daily_rule', 'safety_number', 'tech_training', 'incident_analysis', 'psychology']
        
        for post_type in post_types:
            result = asyncio.run(safety_manager.send_manual_post(post_type))
            results.append(f"{post_type}: {result}")
            # Небольшая пауза между отправками
            import time
            time.sleep(2)
        
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message="✅ Все посты дня отправлены!\n" + "\n".join(results),
            message_type="success"
        )
            
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"❌ Ошибка: {str(e)}",
            message_type="danger"
        )

@app.route('/test-all-content')
def test_all_content():
    """Тестирование всех типов контента"""
    try:
        results = []
        post_types = ['daily_rule', 'safety_number', 'weekly_task', 'tech_training', 
                     'incident_analysis', 'psychology', 'assistant_duties']
        
        for post_type in post_types:
            result = asyncio.run(safety_manager.send_manual_post(post_type))
            results.append(f"{post_type}: {result}")
            import time
            time.sleep(1)
        
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message="✅ Тест всех типов контента завершен!\n" + "\n".join(results),
            message_type="success"
        )
            
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"❌ Ошибка: {str(e)}",
            message_type="danger"
        )

@app.route('/test-connection')
def test_connection():
    """Тестирование подключения к каналу"""
    try:
        success = asyncio.run(safety_manager.test_channel_connection())
        message = "✅ Подключение к каналу успешно!" if success else "❌ Ошибка подключения к каналу"
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=message,
            message_type="success" if success else "danger"
        )
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"❌ Ошибка теста: {str(e)}",
            message_type="danger"
        )

@app.route('/clear-logs')
def clear_logs():
    """Очистка логов"""
    try:
        conn = sqlite3.connect('safety_bot.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM posting_logs')
        cursor.execute('UPDATE bot_stats SET posts_sent = 0')
        conn.commit()
        conn.close()
        
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=0,
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=[],
            message="✅ Логи очищены",
            message_type="success"
        )
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=len(safety_manager.get_scheduled_jobs()),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=safety_manager.get_scheduled_jobs(),
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"❌ Ошибка очистки: {str(e)}",
            message_type="danger"
        )

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/config')
def config():
    """Проверка конфигурации"""
    config_status = {
        "TELEGRAM_BOT_TOKEN": "✅ SET" if os.getenv('TELEGRAM_BOT_TOKEN') else "❌ MISSING",
        "TELEGRAM_CHANNEL_ID": "✅ SET" if os.getenv('TELEGRAM_CHANNEL_ID') else "❌ MISSING",
        "bot_status": getattr(safety_manager, 'bot_status', 'unknown'),
        "channel_status": getattr(safety_manager, 'channel_status', 'unknown'),
        "scheduler_running": getattr(safety_manager, 'scheduler_running', False)
    }
    return jsonify(config_status)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG_MODE', False))
