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
QUEUE_ALREADY = "Вы уже в очереди!"
QUEUE_NOT_FOUND = "Вы не в очереди."
QUEUE_CANCELLED = "❌ Поиск отменён.\n\nВозвращаемся в меню..."
LARGE_BOARD_INFO = "ℹ️ Большое поле: Активирован режим ввода по номерам!"
GAME_START_ERROR = "Ошибка запуска игры!"
OPPONENT_FALLBACK = "Соперник"
BOT_NAME_TEMPLATE = "🤖 Бот ({difficulty})"
BOT_DIFFICULTY_NAMES = {"easy": "Лёгкий", "medium": "Средний", "hard": "Сложный"}
BOT_DIFFICULTY_DEFAULT = "Средний"
BOT_EMOJI = "🤖"
USERNAME_NOT_SET = "не указан"
THEME_CLASSIC_NAME = "Классика"

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
INVITE_CREATED_HTML = """👥 <b>Приглашение создано!</b>

Нажми кнопку ниже, чтобы пригласить друга, или отправь ссылку:
<code>{link}</code>

Код: <code>{code}</code>

⏳ Ссылка действительна 10 минут."""
INVITE_SHARE_TEXT = "🎮 Давай сыграем в Точки и Квадраты!\n{link}"
INVITE_NOT_FOUND = """❌ *Приглашение не найдено*

Возможно, оно истекло или уже использовано."""
INVITE_ALREADY_STARTED = """❌ *Игра уже началась*

Это приглашение уже было использовано."""
INVITE_SELF_JOIN = """🤔 *Это ваше приглашение!*

Отправьте ссылку другу, чтобы он присоединился."""

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

LEAVE_GAME_MESSAGE = "👋 Вы покинули игру.\n\n{main_menu}"

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
BTN_CANCEL = "❌ Отменить"
BTN_INVITE_FRIEND = "📤 Пригласить друга"
BTN_WATCH_AD = "📺 Посмотреть рекламу"
