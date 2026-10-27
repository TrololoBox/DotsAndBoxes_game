# DotsAndBoxes v1.5 — проверка и стабилизация

Дата: 27 октября 2026. Репозиторий: https://github.com/TrololoBox/DotsAndBoxes_game.
Рабочая ветка: `work/dots-state-regression`. Production и реальный Telegram не использовались.

## 1. Исходное состояние и границы доказательств

- Актуальный `main`: `af42c1a051a738ba07ec49bfd0291992431fb9ee` (v1.5, 25.01.2026).
- PR #4: https://github.com/TrololoBox/DotsAndBoxes_game/pull/4, OPEN, не merged, конфликтует с main. Head: `52c3fb6288d0be6827acbac311d9d887243fd8a7`. Общий предок: `e385cca2cfaab88b7fccf6bdfebe31ee6b5fc9d2`.
- PR #4: один коммит, 17 файлов, +1533 / −497 строк; в описании прямо сказано, что автоматические тесты не выполнялись; обсуждений/ревью в полученном timeline нет. Это не доказательство отсутствия любых частных ручных проверок автора.
- `git merge-tree --write-tree main origin/pr-4` воспроизводит конфликты в `bot/handlers/game.py` и `bot/handlers/start.py`. Это анализ дерева, без merge, checkout PR поверх main или изменения PR.
- Первоначальное клонирование задерживалось, поэтому исходники дополнительно читались через GitHub-коннектор. Клонирование затем завершилось: локальный HEAD, дерево и источник сравнения — настоящий Git `af42c1a…`, а не синтетический snapshot.
- В репозитории нет AGENTS.md, исходных тестов или CI-проверок игры. До добавления тестов `python -m pytest -q` вернул exit 5: `no tests ran`.

## 2. Карта фактического исполнения

Точка входа: `python -m bot.main`. Стек — **python-telegram-bot**, не aiogram.

| Поток | Активные компоненты |
| --- | --- |
| Update /start, /menu | `bot/main.py` → `bot/handlers/start.py:start_command`; deep link → `handle_invite_join` |
| Выбор режима, размера, сложности | `bot/main.py` → `bot/handlers/play.py:play_callback` → создание Room / очередь / приглашение |
| Кнопки поля | `bot/main.py` → `game_callback` → `telegram_pkg/callback_parser.py` → матричная координата или `game/edge_numbering.py` → ход |
| Правила | `game/turn.py:apply_turn` → `Board.place_edge` → `game/capture.py:detect_captures`; итог — `game/scoring.py:calculate_result` |
| AI | `bot/handlers/game.py:BOTS` → `ai/easy.py`, `medium.py`, `hard.py` → те же правила хода |
| Представление | `render/board_renderer.py`, `render/themes.py` → PNG; `telegram_pkg/keyboards.py` → inline keyboard |
| Runtime state | `state/rooms.py:_rooms`, `_invite_codes`; `state/players.py:_players`; `state/queues.py:_queues` |
| Очистка | `state/cleanup.py`; теперь вызывается при /start, setup и игровых действиях, без фонового бесконечного цикла |
| Таймеры / AFK | `timers/turn_timer.py` содержит утилиты; нет зарегистрированного scheduler/job, вызывающего timeout или AFK-клавиатуру |
| Исторические спецификации | `game-dots-and-boxes/` — документы, не альтернативный исполняемый бот |

В ветке один синхронный `Room.apply_move` применяет ход, захват, счётчики, версию, очередь и завершение **до первого await**. Stateful callbacks и доставка сериализованы `room.lock`. Чистые правила `game/turn.py` и алгоритмы AI сохранены.

## 3. P0: секрет в Git

**SEC-01, P0, HIGH:** `.env` отслеживается в HEAD и содержит совпадение с форматом Telegram bot token. В доступной истории два коммита изменяли этот путь. Значение не включено ни в отчёт, ни в тесты, diff или PR; на действительность не проверялось и для Telegram не использовалось. Файл не материализован в рабочем каталоге, локально помечен skip-worktree.

**Действие владельца:** отозвать/заменить потенциально раскрытый токен через BotFather и отдельно обновить deployment. Формат не доказывает, что токен сейчас действует. Новая `.gitignore` предотвращает случайное добавление новых env/cache-файлов, но **не удаляет уже отслеживаемый `.env` и не очищает историю**. Удаление tracked-секрета из текущей ветки и возможная очистка истории — отдельная согласованная задача после ротации. История не переписывалась, `.env` не изменён.

## 4. Подтверждённые дефекты и воспроизведения

Строки ниже относятся к **исходному af42c1a**, а имена функций указывают также на исправленный код. В тестах используются только искусственные ID 1/2/3 и вымышленный token.

| ID / приоритет | Факт, причина и воспроизведение | Минимальное решение и проверка |
| --- | --- | --- |
| GAME-01 / P1 | `game.py:194–236`, `343–431`: после `apply_turn` делался `await query.answer()` до смены игрока/завершения. Два разных callback одного игрока, запущенные через `asyncio.gather`, применяют два хода и два переключения. Штатный PTB по умолчанию обрабатывает updates последовательно: конкурентная ошибка доказана для параллельного вызова handlers, а не как измеренный production-инцидент. | Синхронный `Room.apply_move`, lock комнаты, версия; `test_concurrent_different_buttons_apply_once`, `test_numbered_double_click`, `test_capture_rejects_second_old_button_even_with_extra_turn`. |
| GAME-02 / P1 | `callback_parser.py:124–142`, `game.py:149–175`: кнопка не содержит room ID/версию; комната берётся из текущего профиля. После A→B→A старая кнопка применяет новый ход; кнопка предыдущего матча может изменить новый матч. | Формат `исходные_поля:room_id:state_version`; строгая проверка под lock. `test_stale_button_after_two_turns`, `test_old_room_button_cannot_affect_new_room`, `test_legacy_buttons_fail_closed`, `test_out_of_turn_and_non_member`. |
| GAME-03 / P1 | `callback_parser.py:132–137`, `game.py:59–62,112–116`: `leave` становится NOOP и возвращается раньше обработчика выхода. | Отдельный LEAVE; немедленное условное освобождение игроков и удаление invite index. `test_leave_releases_both_players`, `test_pending_invite_cancel_and_expiry`. |
| GAME-04 / P1 | `game.py:808–809,830–832`: после результата current_room_id очищается, поэтому кнопка реванша всегда уходит в меню. `960–962`: недостижимая при обычном потоке ветка отказа содержит undefined `clear_player_room`. `853–863,968–980`: тема теряется при новом матче. | Сохранять completed-связь на существующие 5 минут TTL, проверять обоих участников, удалять предшественника условно; сохранять тему/сложность/размер/эмодзи. `test_finished_game_can_rematch`, `test_pvp_rematch_response_and_replay`, `test_requester_cannot_accept_own_rematch`, `test_rematch_cannot_pull_opponent_from_new_match`. |
| GAME-05 / P1 | `play.py:224–227`: случайный PvP отправляет поле только пользователю текущего update, первый игрок не получает стартовый экран. | Создать профили и отправить поле обоим. `test_world_pvp_sends_board_to_both`, `test_complete_world_pvp_sizes`. |
| GAME-06 / P1 | `queues.py:27–31,43`: очередь допускает только raw 3/4/5, а UI предлагает encoded 10304/10305/10404/10505/10606. На этих размерах выводится ложное «уже в очереди». `main.py:90`: pattern требует двоеточие после `cq`, хотя генератор возвращает `cq`. | Поддержать все предлагаемые коды и legacy 3/4/5/6; исправить routing cancel. `test_world_queue_supports_offered_sizes`, `test_complete_world_pvp_sizes`, `test_queue_cancel_is_routed`. |
| GAME-07 / P1 | `cleanup.py:49–54`: очистка старой completed-комнаты безусловно обнуляет профиль игрока, уже находящегося в новом матче. Аналогичная поздняя очистка в `game.py:1049–1050` выполняется после await уведомления. | `delete_room` освобождает профиль только при совпадении room ID; убрать поздний безусловный сброс. `test_cleanup_does_not_clear_newer_match`, `test_leave_notification_cannot_clear_replacement_room`. |
| GAME-08 / P2 | `callback_parser.py:96–108,145–167`: `e:h:bad:1` бросает ValueError; неправильная чётность координат округляется в действительную грань, любая ориентация кроме h трактуется как v. | Проверять тип, знак, ориентацию, чётность и существование грани; плохой callback не меняет поле. `test_malformed_coordinates_are_rejected`. |
| GAME-09 / P2 | `game.py:79–96`: PAGE без проверки участников, версии, режима и диапазона сохраняет произвольный индекс; keyboard лишь визуально ограничивает его. | Серверные границы из того же greedy packing; пагинация не меняет версию хода. `test_page_bounds_and_stale_page`, `test_pagination_covers_all_edges`. |
| GAME-10 / P2 | `start.py:27–72`: /start всегда показывает приветствие, не восстанавливает активный экран или потерянный результат. В `play.py` повторный setup может перезаписать связь с живым матчем. Приглашение объявлено действующим 10 минут, но cleanup не подключён. | Восстановление текущего матча/результата и прерванного AI; отмена pending через /start; запрет второго live-матча; opportunistic TTL cleanup и проверка владельца invite. `test_start_resumes_same_board`, `test_start_can_cancel_pending_invite`, `test_start_restores_finished_result_after_delivery_failure`, `test_no_second_match_and_invite_replay`, `test_pending_invite_cancel_and_expiry`. |
| GAME-11 / P1 | `game.py:212–215`: ошибка ACK прерывает процесс между применением линии и переходом хода; delivery failure оставляет устаревший экран. В более раннем локальном варианте фикса ACK ещё мог прервать PvE перед ходом AI. | Полная синхронная фиксация, TelegramError при ACK не прерывает уже принятый ход; delivery failure видим вызывающему коду, /start восстанавливает экран/AI. `test_failed_ack_does_not_strand_pve`, `test_failed_delivery_does_not_allow_duplicate_move`, `test_start_recovers_interrupted_bot_turn`. |
| GAME-12 / P2, latent | `turn_timer.py:81–103`: timeout не проверяет состояние, дедлайн или идентификатор хода, повторно начисляет штраф. Runtime scheduler отсутствует, поэтому это дефект утилиты, не активный таймерный инцидент. | Обязательный expected_version, ACTIVE/наличие комнаты/истёкший срок/однократность. `test_stale_duplicate_early_and_terminal_timers`. Новых правил пропуска хода не вводилось. |

AFK: `game.py:1008–1014` содержит TODO/pass, но поиск по всем активным `.py` не обнаружил отправителя AFK-клавиатуры или вызова timeout. Неработающие выборы убраны из helper-клавиатуры; forged актуальный AFK callback сообщает о недоступности без изменения матча. Проверка: `test_afk_unavailable_does_not_change_match`. Это не реализация bot takeover или surrender.

## 5. Матрица PR #4 против v1.5

Решения изучены по полному diff, истории и исходникам. Код из PR целиком не переносился.

| Файлы / решение PR #4 | Классификация | Итог в новой ветке |
| --- | --- | --- |
| `state/engine.py`: централизованный синхронный command path | Полезно частично; новый engine на 391 строку избыточен для минимального исправления | Компактный `Room.apply_move`; исходные правила сохранены |
| `state/rooms.py`: версии и новые CREATED/WAITING/FINISHED/ABORTED | Версии полезны; полное переименование lifecycle неоправданно сейчас | Оставлены PENDING/ACTIVE/COMPLETED/ABANDONED, добавлены version и lock |
| `callback_parser.py`, `keyboards.py`: versioned move/num/page/AFK | Полезно, требует переработки | Версии дополнены room ID, защита распространяется также на leave/rematch. Одна версия без room ID допускает совпадение начальных версий разных матчей |
| `bot/handlers/game.py`: engine routing и обновление UI | Конфликтует с v1.5 | Не потеряны v1.5 PvP-реванши и message editing; исправлен их реальный baseline. Удалена только затенённая повторная функция numbered handler в этом же файле |
| `bot/handlers/start.py` | Конфликтует с v1.5 | Сохранены persistent menu, обе формы invite deep link; добавлен resume |
| `bot/handlers/play.py`: start через engine | Полезно частично | Своя небольшая интеграция; дополнительно устранены пропущенные PR #4 дефекты очередей и отправки старта обоим |
| `game/lines_pagination.py` | Полезно | Эквивалентный небольшой helper рядом с существующим keyboard renderer; пагинация не инвалидирует ход другого игрока |
| `timers/turn_timer.py`: expected_version | Полезно, недостаточно само по себе | Дополнены deadline, lifecycle, identity и защита от дубля. Scheduler не добавлен |
| `state/cleanup.py`: новые TTL, в т.ч. active 30 минут | Часть полезна, часть требует решения продукта | Существующие 10/5 минут сохранены; исправлено условное освобождение профилей. В PR #4 старый безусловный сброс всё ещё присутствует. Принудительный active TTL не вводился |
| `state/logging_utils.py`, `telegram_pkg/ux.py`, `messages.py`, `toasts.py` | Структурированное логирование полезно; массовый перенос текстов не нужен для P1 | Не переносились отдельные слои; пользовательские тексты v1.5 сохранены |
| `CRITICAL_QUESTIONS.md`, `docs/HARDENING.md` | Полезная постановка вопросов, не доказательство работающей реализации | Заменены этим отчётом и отдельным roadmap. AFK "continue" не превращён произвольно в abort |
| `bot/main.py` | Параллельные изменения требуют сверки с v1.5 | Сохранены команды и reply menu; точечно исправлен cq-router |

Рекомендация: заменить PR #4 данным узким PR после ревью владельца, затем отдельно решить его закрытие. Пока PR #4 оставлен открытым; ни комментариев, ни изменений статуса, ветки или описания в нём не делалось.

## 6. Изменения и альтернативы

- Production-код изменён только в 10 существующих файлах: `bot/handlers/{game,play,start}.py`, `bot/main.py`, `state/{rooms,cleanup,queues}.py`, `telegram_pkg/{callback_parser,keyboards}.py`, `timers/turn_timer.py`.
- Добавлены `.gitignore`, `pytest.ini`, `requirements-dev.txt`, `tests/conftest.py`, `tests/test_regression.py` и документы `docs/work/`.
- Отдельный engine, новые базы/Redis, миграции, WebApp, статистика и реорганизация каталогов не вводились. Исторические файлы и tracked bytecode оставлены.
- Raw callbacks setup/menus сохранены. Все игровые отправители оборачивают stateful кнопки `bind_game_keyboard`; старые неверсированные игровые клавиатуры отклоняются с подсказкой /start. Ссылка партнёра v1.5, темы и bottom menu сохранены.
- Чистый core уже правильно отвергал occupied/out-of-turn и давал захваты/extra turn. Его не переписывали. Исправлялась интеграция с Room и Telegram.

## 7. Проверки и честные результаты

Среда: Python 3.12.14; python-telegram-bot 22.8; Pillow 13.0.0; python-dotenv 1.2.4; pytest 9.1.1; pytest-asyncio 1.4.1; Ruff 0.17.3. Requirements проекта имеют нижние границы, это не полная матрица всех старых версий.

| Проверка | Результат |
| --- | --- |
| Исходный compileall | PASS |
| Исходный pytest до создания suite | NOT RUN — тестов не было, exit 5 |
| Первый набор из 25 regression cases на исходном v1.5 | **13 FAIL / 12 PASS**; параметры размеров считаются отдельными cases, не отдельными причинами |
| Ruff F821/F811 по исходному game handler | FAIL: затенённый numbered handler и два обращения к undefined clear_player_room |
| Промежуточные локальные версии | Исправлена собственная ошибка отступов при правке setup; затем 25 PASS; расширение дало 3 FAIL/63 PASS (resume/ACK), затем 66 PASS; ещё два соседних случая воспроизвели поздний сброс и отсутствие result resume, затем 68 PASS |
| Финальный pytest | **68 PASS / 0 FAIL** |
| Финальный compileall и entry-point import с fake token | PASS; `main()` и polling не вызывались |
| Ruff F821/F811 по активным пакетам и tests | PASS; это целевая проверка undefined/redefinition, не полный style lint |
| pip check, git diff --check | PASS |
| Реальная Telegram-доставка, вид на устройствах, production smoke | NOT RUN — запрещены условиями ТЗ |
| Автоматический пропуск хода / AFK bot takeover / surrender | NOT RUN — нет реализованного runtime-пути; это явно оставшаяся функциональность |

Соответствие 14 обязательным сценариям:

1. Допустимая линия, 2. occupied — core tests и полные handler-матчи.
3. Один/два квадрата, 4. extra turn — `test_turn_core_capture_one_and_extra_turn`, `test_turn_core_capture_two_and_winner`, `test_capture_rejects_second_old_button_even_with_extra_turn`.
5. Чужая очередь — `test_out_of_turn_and_non_member`.
6. Старая кнопка — stale/old-room/legacy tests.
7. Двойное нажатие — numbered и concurrent разные кнопки.
8. Завершение/победитель — core score и полные партии.
9. Реванш — PvE/PvP yes/no/replay/requester/opponent-new-room.
10. PvE — реальные Easy/Medium/Hard, seed 41, полная 3×3 партия каждой сложности; не оценка силы AI.
11. PvP — friend deep link и полные world-партии всех шести предлагаемых размеров.
12. 4×4/5×5/6×6 — покрытие граней обеих страниц lines, bounds, 18 проверок PNG/клавиатур всех размеров × трёх тем. Classic 4×4 сохранён как в v1.5, без визуального разламывания сетки.
13. Старый таймер — expiry/version/duplicate/terminal test.
14. Выход/очистка — leave, pending cancel, TTL, условное освобождение новой комнаты.

Все Telegram-объекты — AsyncMock, сетевые socket connect/connect_ex/create_connection заблокированы autouse fixture. Картинки создавались настоящим renderer; в части долгих игровых прогонов отключена только повторная доставка/отрисовка, правила и AI настоящие. Тесты не содержат реальных токенов, имён, телефонов или player IDs.

Воспроизведение в новом изолированном окружении, из корня репозитория:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q bot game state timers telegram_pkg ai render tests
.venv/bin/python -m pip check
git diff --check
# Необязательная целевая статика:
.venv/bin/python -m pip install ruff
.venv/bin/ruff check --select F821,F811 bot game state timers telegram_pkg ai render tests
```

В Windows: `.venv\Scripts\python.exe` вместо `.venv/bin/python`. Fixture задаёт вымышленный BOT_TOKEN перед импортами. Не запускать `python -m bot.main` для офлайн-тестов.

## 8. Оставшиеся ограничения и риски

- **P0 не закрыт автоматически:** ротация секрета требует владельца. Не считать этот PR полной security-очисткой репозитория.
- In-memory комнаты, очереди и профили теряются при перезапуске. Resume действует только в том же процессе. Персистентность намеренно не добавлена.
- Таймеры не запланированы, AFK не реализован. `handle_timeout` теперь требует captured `expected_version`; будущему scheduler нужен отдельный обзор правил и тест реального жизненного цикла.
- Очистка opportunistic; без новых событий объекты остаются в памяти. Нет согласованного TTL активного матча или matchmaking queue. Завершённый матч доступен для реванша до прежнего TTL 5 минут.
- Lock удерживается и во время доставки; это упрощает порядок UI, но медленный Telegram может задержать комнату. Многопроцессный deployment с общим state здесь не поддерживается.
- Ошибка отправки фото не запускает автоматический abort всего матча. Состояние сохраняется; /start позволяет повторить доставку. Нет retry/notification очереди или измеренного production SLA.
- Classic 4×4 имеет исходную сетку из 9 столбцов. Никаких новых утверждений об успешном отображении этого layout на Telegram-клиентах не делается: нужна ручная проверка. Нумерованные/lines layouts проверены офлайн.
- Последовательные double taps и старые кнопки воспроизведены; реальные задержки/дубли Telegram не измерялись. Параллельные handlers тестировались искусственно и сильнее штатной последовательной конфигурации PTB.
- Произвольные forged setup-параметры/нагрузка, XSS/Markdown всего пользовательского профиля, rate limits и все ветви ошибок провайдера не входят в доказанное покрытие. Основной scope — целостность матчей.
- Новая suite не является доказательством отсутствия иных дефектов и не заменяет ручной smoke на отдельном тестовом боте после ревью.

## 9. Ручная проверка владельцем и откат

1. Проверить diff нового PR и этот отчёт. PR #4 не сливать автоматически.
2. Через BotFather самостоятельно отозвать потенциально раскрытый токен. Для smoke создать отдельного тестового бота; не использовать значение из Git и не подключать игроков production.
3. На локальной тестовой машине поставить зависимости и запустить офлайн-suite. Только затем по своему решению выполнить отдельный Telegram smoke с тестовым токеном.
4. Проверить PvE каждой сложности; 3×3, прямоугольники, classic 4×4, lines 5×5/6×6; смену страницы; double tap; старую кнопку после возврата очереди; /start; выход.
5. Двумя тестовыми аккаунтами проверить friend/world, доставку обоим, yes/no реванша, повторное согласие, выход и попытку реванша после новой партии.
6. Проверить persistent menu, оформление/темы, партнёрскую кнопку и фактический вид classic 4×4.
7. Проверить /start после имитации сетевого сбоя. Перезапуск сознательно обнуляет матчи; ожидать их сохранения нельзя.

До merge откат — закрыть новый PR без слияния. После отдельного решения владельца о deployment откат — восстановить предыдущую версию приложения штатным способом; эта работа не меняет БД/инфраструктуру. Любой restart потеряет in-memory матчи, поэтому заранее согласовать окно. Автоматического deployment или merge в этой задаче нет.

Дальнейшее развитие: [dots-roadmap.md](dots-roadmap.md).
