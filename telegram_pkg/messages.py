"""
Russian message templates for the bot.

All user-facing text is defined here for easy localization.
"""

# Main menu
WELCOME_MESSAGE = """👋 Привет, {name}!

🎯 *Точки и Квадраты* — классическая игра на бумаге, теперь в Telegram!

Соедини точки линиями и захвати больше квадратов, чем противник.

Выбери действие:"""

MAIN_MENU_TITLE = "🎯 *Точки и Квадраты*\n\nВыбери действие:"

# Play menu
PLAY_MODE_TITLE = "🎮 *Выбери режим игры:*"
PLAY_SIZE_TITLE = "📐 *Выбери размер поля:*"
PLAY_DIFFICULTY_TITLE = "🤖 *Выбери сложность бота:*"

# In queue
QUEUE_WAITING = """⏳ *Ищем соперника...*

Размер поля: {size}×{size}
Позиция в очереди: {position}

Немного терпения! Мы найдём тебе достойного противника."""

QUEUE_FOUND = "🎉 Соперник найден! Начинаем игру..."

# Game in progress (HTML format to avoid Markdown issues with usernames)
GAME_STATUS = """📊 <b>Счёт:</b> {your_emoji} {your_score} — {opponent_score} {opponent_emoji}

🆚 Соперник: {opponent}

{turn_message}"""

YOUR_TURN = "🟢 <b>Твой ход!</b> Выбери грань на поле."
OPPONENT_TURN = "🔴 <b>Ход соперника.</b> Подожди немного..."
BOT_TURN = "🤖 <b>Бот думает...</b>"

NUMBERED_MODE_HELP = """
ℹ️ <b>Цифровой ввод:</b>
• Найди номер свободной грани на картинке
• Нажми соответствующую кнопку внизу"""

# Captures
CAPTURE_SINGLE = "✨ Отлично! Ты захватил 1 квадрат! Ходи ещё!"
CAPTURE_DOUBLE = "🔥 Невероятно! 2 квадрата за один ход! Ходи ещё!"
OPPONENT_CAPTURED = "Соперник захватил {count} квадрат(ов)."

# Game over (HTML format)
GAME_OVER_WIN = """🏆 <b>Победа!</b>

Поздравляем! Ты выиграл!
Твой счёт: {your_score}
Счёт соперника: {opponent_score}"""

GAME_OVER_LOSE = """😔 <b>Поражение</b>

В этот раз не повезло, но не расстраивайся!
Твой счёт: {your_score}
Счёт соперника: {opponent_score}"""

GAME_OVER_DRAW = """🤝 <b>Ничья!</b>

Отличная игра! Вы оба молодцы!
Счёт: {score}:{score}"""

# AFK
AFK_WARNING = """⏰ *Время на ход истекло!*

Не волнуйся, бывает. Ход переходит к сопернику."""

AFK_CHOICE = """😴 *Кажется, вы отошли?*

Прошло несколько ходов без ответа.
Что бы вы хотели сделать?

Мы подождём, никуда не торопимся! 💙"""

# Invites
INVITE_CREATED = """👥 *Приглашение создано!*

Отправь эту ссылку другу:
{link}

Или код для ввода: `{code}`

⏳ Ссылка действительна 10 минут."""

INVITE_EXPIRED = "❌ Приглашение истекло. Создай новое."

# Profile
PROFILE_TEMPLATE = """👤 *Профиль*

Имя: {name}
Username: {username}
Эмодзи: {emoji}"""

# Settings
SETTINGS_TEMPLATE = """⚙️ *Настройки*

Тема: {theme}"""

# Support
SUPPORT_MESSAGE = """💝 *Поддержать проект*

Спасибо за интерес к игре!
Способы поддержки появятся позже.

🚧 Раздел в разработке"""

# Errors
ERROR_NOT_YOUR_TURN = "❌ Сейчас не твой ход!"
ERROR_INVALID_MOVE = "❌ Эта линия уже занята!"
ERROR_NO_GAME = "❌ У тебя нет активной игры."
ERROR_ALREADY_IN_GAME = "❌ Ты уже в игре! Заверши её сначала."

# Buttons
BTN_PLAY = "🎮 Играть"
BTN_PROFILE = "👤 Профиль"
BTN_SETTINGS = "⚙️ Настройки"
BTN_SUPPORT = "💝 Поддержать проект"
BTN_BACK = "◀️ Назад"
BTN_PVE = "🤖 Против бота"
BTN_PVP_WORLD = "🌍 Случайный соперник"
BTN_PVP_FRIEND = "👥 Пригласить друга"
BTN_EASY = "😊 Лёгкий"
BTN_MEDIUM = "🤔 Средний"
BTN_HARD = "😈 Сложный"
BTN_REMATCH = "🔄 Реванш"
BTN_TO_MENU = "🏠 В меню"
BTN_CONTINUE_BOT = "🤖 Продолжить с ботом"
BTN_SURRENDER = "🏳️ Сдаться"
BTN_CANCEL_QUEUE = "❌ Отменить поиск"
BTN_WATCH_AD = "📺 Посмотреть рекламу"
