import os
import logging
import sqlite3
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
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
                        <a href="/send-test" class="btn btn-success">🧪 Тестовое сообщение</a>
                        <a href="/clear-logs" class="btn btn-danger">🗑️ Очистить логи</a>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        document.getElementById('post_type').addEventListener('change', function() {
            const customGroup = document.getElementById('custom_text_group');
            customGroup.style.display = this.value === 'custom' ? 'block' : 'none';
        });
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
        self.init_db()
        self.content_db = self._load_all_content()
        self.setup_scheduler()
        asyncio.run(self.test_channel_connection())
        
    async def test_channel_connection(self):
        """Тестирование подключения к каналу"""
        try:
            # Используем прямое HTTP-подключение вместо библиотеки
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.telegram.org/bot{self.bot_token}/getChat",
                    params={"chat_id": self.channel_id},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('ok'):
                        chat_title = data['result'].get('title', 'Unknown')
                        self.channel_status = f"✅ Канал: {chat_title}"
                        logger.info(f"Channel access confirmed: {chat_title}")
                    else:
                        self.channel_status = f"❌ Ошибка: {data.get('description', 'Unknown error')}"
                else:
                    self.channel_status = f"❌ HTTP Error: {response.status_code}"
                    
        except Exception as e:
            self.channel_status = f"❌ Ошибка подключения: {e}"
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
        except Exception as e:
            logger.warning(f"Keep-alive error: {e}")

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
                        return True, "✅ Сообщение отправлено"
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
            else:
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
                INSERT INTO posting_logs (post_type, content, status, message)
                VALUES (?, ?, ?, ?)
            ''', (post_type, str(content)[:200], 'success', f"Manual: {trigger}"))
            
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
            
            conn.close()
            
            return {
                'posts_sent': posts_sent,
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {'posts_sent': 0}

# Глобальный экземпляр
safety_manager = SafetyContentManager()

# ==================== FLASK ROUTES ====================

@app.route('/')
def dashboard():
    """Главный дашборд"""
    stats = safety_manager.get_stats()
    
    return render_template_string(DASHBOARD_HTML,
        bot_status=getattr(safety_manager, 'bot_status', 'error'),
        channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
        posts_sent=stats['posts_sent'],
        current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
        current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
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
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            message=result,
            message_type="success" if "✅" in result else "danger"
        )
            
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
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
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            message=message,
            message_type="success" if success else "danger"
        )
            
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
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
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            message="✅ Тест подключения выполнен",
            message_type="success"
        )
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
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
            posts_sent=0,
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
            message="✅ Логи очищены",
            message_type="success"
        )
    except Exception as e:
        return render_template_string(DASHBOARD_HTML,
            bot_status=getattr(safety_manager, 'bot_status', 'error'),
            channel_status=getattr(safety_manager, 'channel_status', 'Не проверен'),
            posts_sent=safety_manager.get_stats()['posts_sent'],
            current_time_utc=datetime.now(pytz.UTC).strftime('%H:%M:%S'),
            current_time_kemerovo=datetime.now(pytz.timezone('Asia/Novokuznetsk')).strftime('%H:%M:%S'),
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
