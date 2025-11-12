import os
import logging
import asyncio
import sqlite3
import json
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import requests

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
        
        .jobs-list { background: white; border-radius: 10px; overflow: hidden; }
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
        
        .logs { background: #2c3e50; color: white; padding: 20px; border-radius: 10px; }
        .log-entry { 
            padding: 8px 0; border-bottom: 1px solid #34495e; 
            font-family: 'Courier New', monospace; font-size: 0.9em;
        }
        .log-entry:last-child { border-bottom: none; }
        
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
        .btn-danger { background: #e74c3c; color: white; }
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
                <div class="stat-label">на сегодня</div>
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
                <h2 class="section-title">📊 Ручная отправка постов</h2>
                <div class="manual-post">
                    <form method="POST" action="/send-manual">
                        <div class="form-group">
                            <label for="post_type">Тип контента:</label>
                            <select id="post_type" name="post_type" required>
                                <option value="daily_rule">🚦 Правило дня</option>
                                <option value="safety_number">📊 Цифра безопасности</option>
                                <option value="tech_training">🔧 Техническая подготовка</option>
                                <option value="incident_analysis">🔍 Анализ инцидента</option>
                                <option value="psychology">🧠 Психология безопасности</option>
                                <option value="assistant_duties">👨‍💼 Обязанности помощника</option>
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
                        <a href="/force-schedule" class="btn btn-success">⏰ Запустить все задания</a>
                        <a href="/clear-logs" class="btn btn-danger">🗑️ Очистить логи</a>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2 class="section-title">⏰ Запланированные задания</h2>
                <div class="jobs-list">
                    {% for job in scheduled_jobs %}
                    <div class="job-item">
                        <div class="job-info">
                            <div class="job-name">{{ job.name }}</div>
                            <div class="job-time">Следующий запуск: {{ job.next_run }}</div>
                        </div>
                        <div class="job-status status-active">Активно</div>
                    </div>
                    {% endfor %}
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
        
        try:
            # Инициализация Telegram бота
            from telegram import Bot
            self.bot = Bot(token=self.bot_token)
            self.bot_status = "active"
            logger.info("Telegram bot initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing bot: {e}")
            self.bot_status = "error"
            self.channel_status = f"❌ Ошибка инициализации: {e}"
            return
        
        self.init_db()
        self.content_db = self._load_all_content()
        self.setup_scheduler()
        asyncio.run(self.test_channel_connection())
        
    async def test_channel_connection(self):
        """Тестирование подключения к каналу"""
        try:
            chat = await self.bot.get_chat(self.channel_id)
            self.channel_status = f"✅ Канал: {chat.title}"
            logger.info(f"Channel access confirmed: {chat.title}")
        except Exception as e:
            self.channel_status = f"❌ Ошибка доступа: {e}"
            logger.error(f"Channel access failed: {e}")

    def init_db(self):
        """Инициализация базы данных"""
        try:
            conn = sqlite3.connect('safety_bot.db', check_same_thread=False)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS posting_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_type TEXT,
                    content TEXT,
                    scheduled_time DATETIME,
                    actual_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    message TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    posts_sent INTEGER DEFAULT 0,
                    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
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
        """Загрузка всего контента"""
        return {
            'daily_rules': {
                1: "🚦 <b>ПРАВИЛО ДНЯ</b>\n\nПТЭ п.12.1: Машинист обязан немедленно принимать меры к остановке при получении сигнала остановки или возникновении опасности для движения.",
                2: "👀 <b>ПРАВИЛО ДНЯ</b>\n\nПТЭ п.12.7: Машинист должен вести поезд, внимательно наблюдая за путем, показаниями приборов и сигналов.",
                3: "🛑 <b>ПРАВИЛО ДНЯ</b>\n\nПТЭ Прил.2: Перед отправлением поезда машинист обязан убедиться в правильности подготовки тормозов и опробованием проверить их действие.",
            },
            'safety_numbers': {
                1: "📊 <b>ЦИФРА БЕЗОПАСНОСТИ</b>\n\nОстановочный путь грузового поезда 6000т на спуске 10‰ при 70км/ч составляет ~1200 метров",
                2: "⏱️ <b>ЦИФРА БЕЗОПАСНОСТИ</b>\n\nРеакция машиниста 1 секунда = 14 метров пути при скорости 50км/ч",
            },
            'tech_training': {
                1: "🔧 <b>ТЕХНИЧЕСКАЯ ПОДГОТОВКА: ТЭМ2</b>\n\nСистема управления РКСУ: Контроллер имеет 25 позиций. При переходе с позиции на позицию выдерживать паузу 2-3 секунды.",
                2: "🔧 <b>ТЕХНИЧЕСКАЯ ПОДГОТОВКА: 2ТЭ10М</b>\n\nДизель 10Д100: Критические параметры:\n- Давление масла: мин. 1,2 кгс/см²\n- Температура воды: макс. 90°C",
            },
            'incident_analysis': {
                1: "🔍 <b>АНАЛИЗ ИНЦИДЕНТА</b>\n\nПроезд запрещающего сигнала маневровым тепловозом.\n<b>Цепочка ошибок:</b>\n1. Помощник машиниста отвлекся\n2. Машинист не проконтролировал",
                2: "🔍 <b>АНАЛИЗ ИНЦИДЕНТА</b>\n\nСамопроизвольный уход подвижного состава.\n<b>Цепочка ошибок:</b>\n1. Недостаточное закрепление\n2. Отсутствие контроля",
            },
            'psychology': {
                1: "🧠 <b>ПСИХОЛОГИЯ БЕЗОПАСНОСТИ</b>\n\nЭффект многозадачности: Мозг переключается между задачами. При подходе к светофорам сведите отвлечения к минимуму.",
                2: "🧠 <b>ПСИХОЛОГИЯ БЕЗОПАСНОСТИ</b>\n\nСиндром привыкания: После 1000 безопасных поездок риск воспринимается минимальным.",
            },
            'assistant_duties': {
                1: "👨‍💼 <b>ОБЯЗАННОСТИ ПОМОЩНИКА МАШИНИСТА</b>\n\nПри маневрах:\n• Контролировать свободность пути\n• Подавать четкие сигналы машинисту\n• Следить за габаритами",
                2: "👨‍💼 <b>ОБЯЗАННОСТИ ПОМОЩНИКА МАШИНИСТА</b>\n\nЗакрепление состава:\n• Правильная установка башмаков\n• Контроль ручных тормозов\n• Проверка надежности",
            }
        }

    def setup_scheduler(self):
        """Настройка планировщика"""
        try:
            self.scheduler = BackgroundScheduler(timezone=str(self.server_tz))
            
            # Keep-alive задача каждые 10 минут
            self.scheduler.add_job(
                self.keep_alive,
                'interval',
                minutes=10,
                id='keep_alive'
            )

            self.scheduler.start()
            logger.info("Scheduler started successfully")
        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")

    def keep_alive(self):
        """Keep-alive для Render"""
        try:
            health_url = os.getenv('HEALTH_CHECK_URL', '')
            if health_url:
                requests.get(health_url, timeout=10)
            logger.info("Keep-alive ping sent")
            
            # Также пингуем наш собственный эндпоинт
            try:
                requests.get(f"https://{os.getenv('RENDER_SERVICE_NAME', 'bezopasnostdvizenia')}.onrender.com/health", timeout=10)
            except:
                pass
                
        except Exception as e:
            logger.warning(f"Keep-alive error: {e}")

    async def send_manual_post(self, post_type: str, custom_text: str = None):
        """Ручная отправка поста"""
        try:
            if post_type == 'custom' and custom_text:
                content = custom_text
            else:
                content = self._get_content_by_type(post_type)
            
            if not content:
                return "❌ Контент не найден"
            
            # Используем простую отправку без кнопок для теста
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=content,
                parse_mode='HTML'
            )
            
            # Логирование
            self._log_posting(post_type, content, "manual")
            self._update_stats()
            
            return f"✅ Сообщение отправлено в канал"
            
        except Exception as e:
            error_msg = f"❌ Ошибка отправки: {str(e)}"
            logger.error(error_msg)
            return error_msg

    def _get_content_by_type(self, post_type: str):
        """Получение контента по типу"""
        content_map = {
            'daily_rule': self.content_db['daily_rules'].get(1),
            'safety_number': self.content_db['safety_numbers'].get(1),
            'tech_training': self.content_db['tech_training'].get(1),
            'incident_analysis': self.content_db['incident_analysis'].get(1),
            'psychology': self.content_db['psychology'].get(1),
            'assistant_duties': self.content_db['assistant_duties'].get(1),
        }
        return content_map.get(post_type)

    def _log_posting(self, post_type: str, content: str, trigger: str):
        """Логирование публикации"""
        try:
            conn = sqlite3.connect('safety_bot.db', check_same_thread=False)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO posting_logs (post_type, content, scheduled_time, status, message)
                VALUES (?, ?, ?, ?, ?)
            ''', (post_type, str(content)[:200], datetime.now(), 'success', f"Manual: {trigger}"))
            
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
                'timestamp': row[4].split('.')[0] if row[4] else 'N/A',
                'message': f"{row[1]}: {row[6]}"
            } for row in cursor.fetchall()]
            
            conn.close()
            
            return {
                'posts_sent': posts_sent,
                'recent_logs': recent_logs
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {'posts_sent': 0, 'recent_logs': []}

# Глобальный экземпляр
safety_manager = SafetyContentManager()

# ==================== FLASK ROUTES ====================

@app.route('/')
def dashboard():
    """Главный дашборд"""
    stats = safety_manager.get_stats()
    
    # Получение запланированных заданий
    scheduled_jobs = []
    if hasattr(safety_manager, 'scheduler'):
        for job in safety_manager.scheduler.get_jobs():
            scheduled_jobs.append({
                'name': job.name,
                'next_run': job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else 'N/A'
            })
    
    return render_template_string(DASHBOARD_HTML,
        bot_status=getattr(safety_manager, 'bot_status', 'error'),
        channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
        jobs_count=len(scheduled_jobs),
        posts_sent=stats['posts_sent'],
        current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
        current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
        scheduled_jobs=scheduled_jobs,
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
        # Запускаем асинхронную функцию
        result = asyncio.run(safety_manager.send_manual_post(post_type, custom_text))
        
        if "✅" in result:
            return render_template_string(DASHBOARD_HTML,
                bot_status=getattr(safety_manager, 'bot_status', 'error'),
                channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
                jobs_count=0,
                posts_sent=safety_manager.get_stats()['posts_sent'],
                current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
                current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
                scheduled_jobs=[],
                recent_logs=safety_manager.get_stats()['recent_logs'],
                message=result,
                message_type="success"
            )
        else:
            return render_template_string(DASHBOARD_HTML,
                bot_status=getattr(safety_manager, 'bot_status', 'error'),
                channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
                jobs_count=0,
                posts_sent=safety_manager.get_stats()['posts_sent'],
                current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
                current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
                scheduled_jobs=[],
                recent_logs=safety_manager.get_stats()['recent_logs'],
                message=result,
                message_type="danger"
            )
            
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=0,
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=[],
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"❌ Ошибка: {str(e)}",
            message_type="danger"
        )

@app.route('/test-connection')
def test_connection():
    """Тестирование подключения к каналу"""
    try:
        asyncio.run(safety_manager.test_channel_connection())
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=0,
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=[],
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message="✅ Тест подключения выполнен",
            message_type="success"
        )
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=0,
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=[],
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"❌ Ошибка теста: {str(e)}",
            message_type="danger"
        )

@app.route('/force-schedule')
def force_schedule():
    """Принудительный запуск всех заданий"""
    try:
        # Отправляем тестовое сообщение
        asyncio.run(safety_manager.send_manual_post('daily_rule'))
        
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=0,
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=[],
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message="✅ Тестовое сообщение отправлено",
            message_type="success"
        )
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=0,
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=[],
            recent_logs=safety_manager.get_stats()['recent_logs'],
            message=f"❌ Ошибка: {str(e)}",
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
            jobs_count=0,
            posts_sent=0,
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=[],
            recent_logs=[],
            message="✅ Логи очищены",
            message_type="success"
        )
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            jobs_count=0,
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            scheduled_jobs=[],
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
        "channel_status": getattr(safety_manager, 'channel_status', 'unknown')
    }
    return jsonify(config_status)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG_MODE', False))
