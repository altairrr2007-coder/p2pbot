import asyncio
import sqlite3
from datetime import datetime, date, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)

API_TOKEN = '8881234170:AAFsxkINgznqtFt4k5HlCmtnWOoOlowKvTg'

bot = Bot(token=API_TOKEN)
dp  = Dispatcher()

# ══════════════════════════════════════════════════
#  База данных
# ══════════════════════════════════════════════════
conn = sqlite3.connect('p2p_journal.db')
db   = conn.cursor()

db.executescript('''
    CREATE TABLE IF NOT EXISTS trades (
        id          INTEGER PRIMARY KEY,
        trade_date  TEXT,
        trade_type  TEXT,
        from_cur    TEXT,
        to_cur      TEXT,
        amount      REAL,
        price       REAL,
        total       REAL,
        fee         REAL DEFAULT 0,
        platform    TEXT,
        notes       TEXT
    );
    CREATE TABLE IF NOT EXISTS settings (
        user_id     INTEGER PRIMARY KEY,
        currency    TEXT    DEFAULT "RUB",
        daily_goal  REAL    DEFAULT 0,
        username    TEXT    DEFAULT ""
    );
''')
conn.commit()

# ══════════════════════════════════════════════════
#  Константы
# ══════════════════════════════════════════════════
CURRENCIES = ["USDT", "BTC", "ETH", "RUB", "KZT", "EUR", "USD", "BUSD"]
PLATFORMS  = ["Binance", "Bybit", "OKX", "Huobi", "Gate.io", "КриптоБанк"]

# ══════════════════════════════════════════════════
#  Состояния  user_id -> dict
# ══════════════════════════════════════════════════
user_state: dict = {}

def st(uid: int) -> dict:
    if uid not in user_state:
        user_state[uid] = {}
    return user_state[uid]

def reset(uid: int):
    user_state.pop(uid, None)

# ══════════════════════════════════════════════════
#  Настройки пользователя
# ══════════════════════════════════════════════════
def get_settings(uid: int) -> dict:
    db.execute("INSERT OR IGNORE INTO settings (user_id) VALUES (?)", (uid,))
    conn.commit()
    row = db.execute(
        "SELECT currency, daily_goal, username FROM settings WHERE user_id=?", (uid,)
    ).fetchone()
    return {"currency": row[0], "daily_goal": row[1], "username": row[2]}

# ══════════════════════════════════════════════════
#  ── REPLY-клавиатура (кнопки у поля ввода) ──
# ══════════════════════════════════════════════════
def reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📥 Buy"),   KeyboardButton(text="📤 Sell")],
            [KeyboardButton(text="📔 Журнал"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="📈 Аналитика"), KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
        persistent=True,
    )

# ══════════════════════════════════════════════════
#  Inline-клавиатуры
# ══════════════════════════════════════════════════
def main_inline():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📥 Buy",  callback_data="add_buy"),
            InlineKeyboardButton(text="📤 Sell", callback_data="add_sell"),
        ],
        [
            InlineKeyboardButton(text="📔 Сегодня",    callback_data="today"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
        ],
        [
            InlineKeyboardButton(text="👤 Профиль",    callback_data="profile"),
            InlineKeyboardButton(text="⚙️ Настройки",  callback_data="settings"),
        ],
        [
            InlineKeyboardButton(text="📈 Аналитика",  callback_data="analytics"),
            InlineKeyboardButton(text="🗑 Очистить",   callback_data="clear_confirm"),
        ],
    ])

def currency_keyboard(exclude=None):
    buttons, row = [], []
    for c in CURRENCIES:
        if c == exclude:
            continue
        row.append(InlineKeyboardButton(text=c, callback_data=f"cur_{c}"))
        if len(row) == 3:
            buttons.append(row); row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="◀️ Меню", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def platform_keyboard():
    buttons, row = [], []
    for p in PLATFORMS:
        row.append(InlineKeyboardButton(text=p, callback_data=f"plat_{p}"))
        if len(row) == 3:
            buttons.append(row); row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="◀️ Меню", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ В меню", callback_data="back_main")]
    ])

def confirm_clear_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data="clear_yes"),
            InlineKeyboardButton(text="❌ Отмена",      callback_data="back_main"),
        ]
    ])

def stats_period_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Сегодня",    callback_data="stats_today"),
            InlineKeyboardButton(text="7 дней",     callback_data="stats_7"),
            InlineKeyboardButton(text="30 дней",    callback_data="stats_30"),
        ],
        [
            InlineKeyboardButton(text="Все время",  callback_data="stats_all"),
        ],
        [InlineKeyboardButton(text="◀️ Меню", callback_data="back_main")],
    ])

def settings_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💱 Базовая валюта",  callback_data="set_currency")],
        [InlineKeyboardButton(text="🎯 Дневная цель",    callback_data="set_goal")],
        [InlineKeyboardButton(text="✏️ Имя профиля",     callback_data="set_name")],
        [InlineKeyboardButton(text="◀️ Меню",            callback_data="back_main")],
    ])

def analytics_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 По дням",      callback_data="an_days"),
            InlineKeyboardButton(text="🏦 По платформам",callback_data="an_platforms"),
        ],
        [
            InlineKeyboardButton(text="💱 По парам",     callback_data="an_pairs"),
            InlineKeyboardButton(text="📊 Средний спред",callback_data="an_spread"),
        ],
        [InlineKeyboardButton(text="◀️ Меню", callback_data="back_main")],
    ])

# ══════════════════════════════════════════════════
#  Утилиты
# ══════════════════════════════════════════════════
async def edt(cb: types.CallbackQuery, text: str, markup=None):
    try:
        await cb.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await cb.message.answer(text, reply_markup=markup, parse_mode="HTML")

def date_from_offset(days: int) -> str:
    return (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")

def calc_stats(rows):
    buy_sum = buy_cnt = sell_sum = sell_cnt = fees = 0.0
    for r in rows:
        if r[2] == "buy":
            buy_sum  += r[7]; buy_cnt  += 1; fees += r[8]
        else:
            sell_sum += r[7]; sell_cnt += 1; fees += r[8]
    profit = sell_sum - buy_sum
    return buy_sum, buy_cnt, sell_sum, sell_cnt, fees, profit

# ══════════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════════
@dp.message(Command("start"))
async def cmd_start(msg: types.Message):
    reset(msg.from_user.id)
    name = msg.from_user.first_name or "Трейдер"
    await msg.answer(
        f"👋 Привет, <b>{name}</b>!\n\n"
        f"📔 <b>P2P Торговый Журнал</b>\n\n"
        f"Используй кнопки внизу или меню ниже:",
        reply_markup=reply_kb(),
        parse_mode="HTML",
    )
    await msg.answer("Главное меню:", reply_markup=main_inline(), parse_mode="HTML")

# ══════════════════════════════════════════════════
#  Reply-кнопки → перенаправление в inline-логику
# ══════════════════════════════════════════════════
REPLY_MAP = {
    "📥 Buy":        "add_buy",
    "📤 Sell":       "add_sell",
    "📔 Журнал":     "today",
    "📊 Статистика": "stats",
    "👤 Профиль":    "profile",
    "⚙️ Настройки":  "settings",
    "📈 Аналитика":  "analytics",
    "❓ Помощь":     "help",
}

@dp.message(F.text.in_(REPLY_MAP.keys()))
async def reply_btn(msg: types.Message):
    action = REPLY_MAP[msg.text]
    uid = msg.from_user.id

    if action in ("add_buy", "add_sell"):
        reset(uid)
        trade_type = "buy" if action == "add_buy" else "sell"
        st(uid)["trade_type"] = trade_type
        st(uid)["step"] = "from_cur"
        icon = "📥" if trade_type == "buy" else "📤"
        await msg.answer(
            f"{icon} <b>{trade_type.upper()}</b>\n\nВыбери <b>исходную</b> валюту:",
            reply_markup=currency_keyboard(),
            parse_mode="HTML",
        )

    elif action == "today":
        today_str = date.today().strftime("%Y-%m-%d")
        db.execute("SELECT * FROM trades WHERE trade_date LIKE ? ORDER BY id DESC", (today_str+"%",))
        rows = db.fetchall()
        if not rows:
            text = f"📔 Сегодня ({today_str}):\n\nСделок пока нет."
        else:
            lines = []
            for r in rows:
                ico = "📥" if r[2]=="buy" else "📤"
                lines.append(f"{ico} {r[1][-5:]} | {r[3]}→{r[4]} {r[5]}×{r[6]} = <b>{r[7]}</b> [{r[9]}]")
            text = f"📔 <b>Сегодня ({today_str})</b>\n\n" + "\n".join(lines)
        await msg.answer(text, reply_markup=back_kb(), parse_mode="HTML")

    elif action == "stats":
        await msg.answer("📊 <b>Статистика</b>\n\nВыбери период:", reply_markup=stats_period_kb(), parse_mode="HTML")

    elif action == "profile":
        await _send_profile(msg, uid)

    elif action == "settings":
        cfg = get_settings(uid)
        await msg.answer(
            f"⚙️ <b>Настройки</b>\n\n"
            f"💱 Валюта: <b>{cfg['currency']}</b>\n"
            f"🎯 Цель/день: <b>{cfg['daily_goal']}</b>\n"
            f"✏️ Имя: <b>{cfg['username'] or '—'}</b>",
            reply_markup=settings_kb(),
            parse_mode="HTML",
        )

    elif action == "analytics":
        await msg.answer("📈 <b>Аналитика</b>\n\nВыбери раздел:", reply_markup=analytics_kb(), parse_mode="HTML")

    elif action == "help":
        await msg.answer(
            "❓ <b>Помощь</b>\n\n"
            "📥 <b>Buy</b> — добавить сделку покупки\n"
            "📤 <b>Sell</b> — добавить сделку продажи\n"
            "📔 <b>Журнал</b> — сделки за сегодня\n"
            "📊 <b>Статистика</b> — P&L за период\n"
            "👤 <b>Профиль</b> — ваши показатели\n"
            "⚙️ <b>Настройки</b> — валюта, цель, имя\n"
            "📈 <b>Аналитика</b> — разбивка по дням / платформам / парам\n\n"
            "<i>Ввод сделки идёт пошагово — просто следуй подсказкам бота.</i>",
            reply_markup=back_kb(),
            parse_mode="HTML",
        )

# ══════════════════════════════════════════════════
#  Меню / Назад
# ══════════════════════════════════════════════════
@dp.callback_query(F.data == "back_main")
async def back_main(cb: types.CallbackQuery):
    reset(cb.from_user.id)
    await edt(cb, "📔 <b>P2P Торговый Журнал</b>\n\nВыбери действие:", main_inline())
    await cb.answer()

# ══════════════════════════════════════════════════
#  Добавление сделки — inline-старт
# ══════════════════════════════════════════════════
@dp.callback_query(F.data.in_({"add_buy", "add_sell"}))
async def add_trade_start(cb: types.CallbackQuery):
    uid = cb.from_user.id
    trade_type = "buy" if cb.data == "add_buy" else "sell"
    st(uid)["trade_type"] = trade_type
    st(uid)["step"] = "from_cur"
    icon = "📥" if trade_type == "buy" else "📤"
    await edt(cb, f"{icon} <b>{trade_type.upper()}</b>\n\nВыбери <b>исходную</b> валюту:", currency_keyboard())
    await cb.answer()

# ══════════════════════════════════════════════════
#  Выбор валюты
# ══════════════════════════════════════════════════
@dp.callback_query(F.data.startswith("cur_"))
async def pick_currency(cb: types.CallbackQuery):
    uid = cb.from_user.id
    val = cb.data[4:]
    s = st(uid)

    if s.get("step") == "from_cur":
        s["from_cur"] = val
        s["step"] = "to_cur"
        await edt(cb, f"✅ Исходная: <b>{val}</b>\n\nВыбери <b>целевую</b> валюту:", currency_keyboard(exclude=val))

    elif s.get("step") == "to_cur":
        s["to_cur"] = val
        s["step"] = "amount"
        await edt(cb,
            f"✅ Пара: <b>{s['from_cur']} → {val}</b>\n\n"
            f"Введи <b>сумму</b>:", back_kb())

    await cb.answer()

# ══════════════════════════════════════════════════
#  Выбор платформы
# ══════════════════════════════════════════════════
@dp.callback_query(F.data.startswith("plat_"))
async def pick_platform(cb: types.CallbackQuery):
    uid = cb.from_user.id
    platform = cb.data[5:]
    s = st(uid)
    s["platform"] = platform
    s["step"] = "fee"
    await edt(cb,
        f"✅ Платформа: <b>{platform}</b>\n\n"
        f"Введи <b>комиссию</b> (0 если нет):", back_kb())
    await cb.answer()

# ══════════════════════════════════════════════════
#  Ввод чисел
# ══════════════════════════════════════════════════
@dp.message(F.text & ~F.text.in_(REPLY_MAP.keys()))
async def handle_input(msg: types.Message):
    uid = msg.from_user.id
    s = st(uid)
    step = s.get("step")

    if step not in ("amount", "price", "fee", "set_goal_input", "set_name_input"):
        await msg.answer("Используй кнопки меню 👇", reply_markup=reply_kb())
        return

    # ── настройки: ввод цели ──
    if step == "set_goal_input":
        try:
            goal = float(msg.text.strip().replace(",", "."))
        except ValueError:
            await msg.answer("❌ Введи число:", reply_markup=back_kb())
            return
        db.execute("UPDATE settings SET daily_goal=? WHERE user_id=?", (goal, uid))
        conn.commit()
        reset(uid)
        await msg.answer(f"✅ Дневная цель установлена: <b>{goal}</b>", reply_markup=main_inline(), parse_mode="HTML")
        return

    # ── настройки: ввод имени ──
    if step == "set_name_input":
        name = msg.text.strip()[:30]
        db.execute("UPDATE settings SET username=? WHERE user_id=?", (name, uid))
        conn.commit()
        reset(uid)
        await msg.answer(f"✅ Имя сохранено: <b>{name}</b>", reply_markup=main_inline(), parse_mode="HTML")
        return

    # ── торговый ввод ──
    text = msg.text.strip().replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        await msg.answer("❌ Нужно число. Попробуй ещё раз:", reply_markup=back_kb())
        return

    if step == "amount":
        s["amount"] = value
        s["step"] = "price"
        await msg.answer(f"✅ Сумма: <b>{value}</b>\n\nВведи <b>цену</b> (курс):",
                         reply_markup=back_kb(), parse_mode="HTML")

    elif step == "price":
        s["price"] = value
        s["step"] = "platform"
        await msg.answer(f"✅ Цена: <b>{value}</b>\n\nВыбери <b>платформу</b>:",
                         reply_markup=platform_keyboard(), parse_mode="HTML")

    elif step == "fee":
        s["fee"] = value
        total = round(s["amount"] * s["price"], 4)
        t_date = datetime.now().strftime("%Y-%m-%d %H:%M")

        db.execute(
            '''INSERT INTO trades (trade_date,trade_type,from_cur,to_cur,amount,price,total,fee,platform)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (t_date, s["trade_type"], s["from_cur"], s["to_cur"],
             s["amount"], s["price"], total, s["fee"], s["platform"]),
        )
        conn.commit()

        # проверяем прогресс по дневной цели
        cfg = get_settings(uid)
        today_str = date.today().strftime("%Y-%m-%d")
        db.execute("SELECT SUM(total) FROM trades WHERE trade_date LIKE ? AND trade_type='sell'", (today_str+"%",))
        earned_today = db.fetchone()[0] or 0
        goal_line = ""
        if cfg["daily_goal"] > 0:
            pct = min(int(earned_today / cfg["daily_goal"] * 100), 100)
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            goal_line = f"\n\n🎯 Цель дня: [{bar}] {pct}%  ({earned_today:.2f}/{cfg['daily_goal']:.2f})"

        icon = "📥" if s["trade_type"] == "buy" else "📤"
        reset(uid)
        await msg.answer(
            f"{icon} <b>{s['trade_type'].upper()} добавлен!</b>\n\n"
            f"Пара:      <b>{s['from_cur']} → {s['to_cur']}</b>\n"
            f"Сумма:     {s['amount']}\n"
            f"Цена:      {s['price']}\n"
            f"Итого:     <b>{total}</b>\n"
            f"Комиссия:  {s['fee']}\n"
            f"Платформа: {s['platform']}"
            f"{goal_line}",
            reply_markup=main_inline(),
            parse_mode="HTML",
        )

# ══════════════════════════════════════════════════
#  Журнал сегодня
# ══════════════════════════════════════════════════
@dp.callback_query(F.data == "today")
async def today_journal(cb: types.CallbackQuery):
    today_str = date.today().strftime("%Y-%m-%d")
    db.execute("SELECT * FROM trades WHERE trade_date LIKE ? ORDER BY id DESC", (today_str+"%",))
    rows = db.fetchall()
    if not rows:
        text = f"📔 Сегодня ({today_str}):\n\nСделок пока нет."
    else:
        lines = []
        for r in rows:
            ico = "📥" if r[2]=="buy" else "📤"
            lines.append(f"{ico} {r[1][-5:]} | {r[3]}→{r[4]} {r[5]}×{r[6]} = <b>{r[7]}</b> [{r[9]}]")
        text = f"📔 <b>Сегодня ({today_str})</b>\n\n" + "\n".join(lines)
    await edt(cb, text, main_inline())
    await cb.answer()

# ══════════════════════════════════════════════════
#  Статистика
# ══════════════════════════════════════════════════
def _stats_text(rows, label: str) -> str:
    if not rows:
        return f"📊 <b>Статистика — {label}</b>\n\nСделок нет."
    buy_sum, buy_cnt, sell_sum, sell_cnt, fees, profit = calc_stats(rows)
    total_deals = buy_cnt + sell_cnt
    return (
        f"📊 <b>Статистика — {label}</b>\n\n"
        f"📥 Куплено:   <b>{buy_sum:.2f}</b>  ({buy_cnt} сд.)\n"
        f"📤 Продано:  <b>{sell_sum:.2f}</b>  ({sell_cnt} сд.)\n"
        f"💸 Комиссии: <b>{fees:.2f}</b>\n"
        f"📋 Всего сделок: {total_deals}\n\n"
        f"{'🟢' if profit >= 0 else '🔴'} Прибыль: <b>{profit:.2f}</b>"
    )

@dp.callback_query(F.data == "stats")
async def stats_menu(cb: types.CallbackQuery):
    await edt(cb, "📊 <b>Статистика</b>\n\nВыбери период:", stats_period_kb())
    await cb.answer()

@dp.callback_query(F.data.in_({"stats_today","stats_7","stats_30","stats_all"}))
async def stats_period(cb: types.CallbackQuery):
    period = cb.data
    if period == "stats_today":
        d = date.today().strftime("%Y-%m-%d")
        db.execute("SELECT * FROM trades WHERE trade_date LIKE ?", (d+"%",))
        label = "Сегодня"
    elif period == "stats_7":
        d = date_from_offset(7)
        db.execute("SELECT * FROM trades WHERE trade_date >= ?", (d,))
        label = "7 дней"
    elif period == "stats_30":
        d = date_from_offset(30)
        db.execute("SELECT * FROM trades WHERE trade_date >= ?", (d,))
        label = "30 дней"
    else:
        db.execute("SELECT * FROM trades")
        label = "Все время"
    rows = db.fetchall()
    await edt(cb, _stats_text(rows, label), stats_period_kb())
    await cb.answer()

# ══════════════════════════════════════════════════
#  Профиль
# ══════════════════════════════════════════════════
async def _send_profile(target, uid: int):
    cfg = get_settings(uid)
    db.execute("SELECT COUNT(*), SUM(total), SUM(fee) FROM trades")
    row = db.fetchone()
    total_deals = row[0] or 0
    total_vol   = row[1] or 0
    total_fees  = row[2] or 0

    db.execute("SELECT SUM(total) FROM trades WHERE trade_type='sell'")
    sell_vol = db.fetchone()[0] or 0
    db.execute("SELECT SUM(total) FROM trades WHERE trade_type='buy'")
    buy_vol  = db.fetchone()[0] or 0
    profit   = sell_vol - buy_vol

    today_str = date.today().strftime("%Y-%m-%d")
    db.execute("SELECT COUNT(*) FROM trades WHERE trade_date LIKE ?", (today_str+"%",))
    today_cnt = db.fetchone()[0] or 0

    name = cfg["username"] or "—"
    goal = cfg["daily_goal"]
    goal_line = ""
    if goal > 0:
        db.execute("SELECT SUM(total) FROM trades WHERE trade_date LIKE ? AND trade_type='sell'", (today_str+"%",))
        earned = db.fetchone()[0] or 0
        pct = min(int(earned / goal * 100), 100)
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        goal_line = f"\n🎯 Цель дня: [{bar}] {pct}%"

    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"📛 Имя: <b>{name}</b>\n"
        f"💱 Валюта: <b>{cfg['currency']}</b>\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"📋 Всего сделок: <b>{total_deals}</b>\n"
        f"📅 Сегодня: <b>{today_cnt}</b>\n"
        f"💰 Объём: <b>{total_vol:.2f}</b>\n"
        f"💸 Комиссии: <b>{total_fees:.2f}</b>\n"
        f"{'🟢' if profit>=0 else '🔴'} Прибыль: <b>{profit:.2f}</b>"
        f"{goal_line}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton(text="◀️ Меню",       callback_data="back_main")],
    ])
    if isinstance(target, types.Message):
        await target.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await edt(target, text, kb)

@dp.callback_query(F.data == "profile")
async def profile_cb(cb: types.CallbackQuery):
    await _send_profile(cb, cb.from_user.id)
    await cb.answer()

# ══════════════════════════════════════════════════
#  Настройки
# ══════════════════════════════════════════════════
@dp.callback_query(F.data == "settings")
async def settings_cb(cb: types.CallbackQuery):
    cfg = get_settings(cb.from_user.id)
    await edt(cb,
        f"⚙️ <b>Настройки</b>\n\n"
        f"💱 Базовая валюта: <b>{cfg['currency']}</b>\n"
        f"🎯 Дневная цель:   <b>{cfg['daily_goal']}</b>\n"
        f"✏️ Имя профиля:    <b>{cfg['username'] or '—'}</b>",
        settings_kb())
    await cb.answer()

@dp.callback_query(F.data == "set_currency")
async def set_currency_cb(cb: types.CallbackQuery):
    st(cb.from_user.id)["step"] = "set_currency"
    btns = []
    row = []
    for c in ["RUB","KZT","USD","EUR","USDT"]:
        row.append(InlineKeyboardButton(text=c, callback_data=f"setcur_{c}"))
        if len(row)==3: btns.append(row); row=[]
    if row: btns.append(row)
    btns.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings")])
    await edt(cb, "💱 Выбери базовую валюту:", InlineKeyboardMarkup(inline_keyboard=btns))
    await cb.answer()

@dp.callback_query(F.data.startswith("setcur_"))
async def apply_currency(cb: types.CallbackQuery):
    val = cb.data[7:]
    db.execute("INSERT OR IGNORE INTO settings (user_id) VALUES (?)", (cb.from_user.id,))
    db.execute("UPDATE settings SET currency=? WHERE user_id=?", (val, cb.from_user.id))
    conn.commit()
    reset(cb.from_user.id)
    await edt(cb, f"✅ Базовая валюта: <b>{val}</b>", settings_kb())
    await cb.answer()

@dp.callback_query(F.data == "set_goal")
async def set_goal_cb(cb: types.CallbackQuery):
    st(cb.from_user.id)["step"] = "set_goal_input"
    await edt(cb, "🎯 Введи <b>дневную цель</b> (число):", back_kb())
    await cb.answer()

@dp.callback_query(F.data == "set_name")
async def set_name_cb(cb: types.CallbackQuery):
    st(cb.from_user.id)["step"] = "set_name_input"
    await edt(cb, "✏️ Введи <b>имя профиля</b>:", back_kb())
    await cb.answer()

# ══════════════════════════════════════════════════
#  Аналитика
# ══════════════════════════════════════════════════
@dp.callback_query(F.data == "analytics")
async def analytics_cb(cb: types.CallbackQuery):
    await edt(cb, "📈 <b>Аналитика</b>\n\nВыбери раздел:", analytics_kb())
    await cb.answer()

@dp.callback_query(F.data == "an_days")
async def an_days(cb: types.CallbackQuery):
    db.execute(
        "SELECT DATE(trade_date) as d, COUNT(*), SUM(total) "
        "FROM trades GROUP BY d ORDER BY d DESC LIMIT 7"
    )
    rows = db.fetchall()
    if not rows:
        await edt(cb, "📅 Нет данных.", analytics_kb()); await cb.answer(); return
    lines = ["📅 <b>По дням (последние 7)</b>\n"]
    for r in rows:
        lines.append(f"<b>{r[0]}</b>  — {r[1]} сд. | {r[2]:.2f}")
    await edt(cb, "\n".join(lines), analytics_kb())
    await cb.answer()

@dp.callback_query(F.data == "an_platforms")
async def an_platforms(cb: types.CallbackQuery):
    db.execute(
        "SELECT platform, COUNT(*), SUM(total), SUM(fee) "
        "FROM trades GROUP BY platform ORDER BY COUNT(*) DESC"
    )
    rows = db.fetchall()
    if not rows:
        await edt(cb, "🏦 Нет данных.", analytics_kb()); await cb.answer(); return
    lines = ["🏦 <b>По платформам</b>\n"]
    for r in rows:
        lines.append(f"<b>{r[0]}</b>  — {r[1]} сд. | объём {r[2]:.2f} | комм. {r[3]:.2f}")
    await edt(cb, "\n".join(lines), analytics_kb())
    await cb.answer()

@dp.callback_query(F.data == "an_pairs")
async def an_pairs(cb: types.CallbackQuery):
    db.execute(
        "SELECT from_cur||'→'||to_cur as pair, COUNT(*), SUM(total) "
        "FROM trades GROUP BY pair ORDER BY COUNT(*) DESC LIMIT 10"
    )
    rows = db.fetchall()
    if not rows:
        await edt(cb, "💱 Нет данных.", analytics_kb()); await cb.answer(); return
    lines = ["💱 <b>По парам (топ-10)</b>\n"]
    for r in rows:
        lines.append(f"<b>{r[0]}</b>  — {r[1]} сд. | {r[2]:.2f}")
    await edt(cb, "\n".join(lines), analytics_kb())
    await cb.answer()

@dp.callback_query(F.data == "an_spread")
async def an_spread(cb: types.CallbackQuery):
    db.execute(
        "SELECT from_cur||'→'||to_cur as pair, AVG(price), MIN(price), MAX(price), COUNT(*) "
        "FROM trades GROUP BY pair ORDER BY COUNT(*) DESC LIMIT 8"
    )
    rows = db.fetchall()
    if not rows:
        await edt(cb, "📊 Нет данных.", analytics_kb()); await cb.answer(); return
    lines = ["📊 <b>Средние цены по парам</b>\n"]
    for r in rows:
        spread = r[3] - r[2]
        lines.append(
            f"<b>{r[0]}</b>  ({r[4]} сд.)\n"
            f"  avg {r[1]:.4f}  |  min {r[2]:.4f}  |  max {r[3]:.4f}  |  спред {spread:.4f}"
        )
    await edt(cb, "\n".join(lines), analytics_kb())
    await cb.answer()

# ══════════════════════════════════════════════════
#  Очистка журнала
# ══════════════════════════════════════════════════
@dp.callback_query(F.data == "clear_confirm")
async def clear_confirm(cb: types.CallbackQuery):
    await edt(cb, "⚠️ <b>Удалить все сделки?</b>\n\nЭто действие нельзя отменить.", confirm_clear_kb())
    await cb.answer()

@dp.callback_query(F.data == "clear_yes")
async def clear_yes(cb: types.CallbackQuery):
    db.execute("DELETE FROM trades")
    conn.commit()
    await edt(cb, "✅ Журнал очищен.", main_inline())
    await cb.answer()

# ══════════════════════════════════════════════════
#  Запуск
# ══════════════════════════════════════════════════
async def main():
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
