"""
Telegram Business-бот: /cried <ссылка на NFT> <сумма> <stars|ton> <ru|en>
Установка: pip install httpx
Запуск:    python bot.py
"""
import asyncio
import html
import json
import os
import httpx

# ===================== НАСТРОЙКИ =====================
BOT_TOKEN = "9293560168:AAGOXd4Ekj0_vJaiJYC3T2_7TflryEVaD4c"          # токен от @BotFather

# ID премиум-эмодзи (как получить - см. туториал; пока бот можно
# запустить и прислать ему эмодзи в личку - он ответит ID)
EMOJI_STAR   = "5368324170671202286"  # ⭐️ (замени на свой)
EMOJI_CHECK  = "5368324170671202286"  # ✅ (замени на свой)
EMOJI_CROSS  = "5368324170671202286"  # ❌ (замени на свой)

# Ссылка на кнопке после "Принять". {username} = твой @username.
ACCEPT_URL = "tg://send_gift?to={username}"
# Если Telegram не примет tg:// в кнопке - бот сам подставит этот вариант:
ACCEPT_URL_FALLBACK = "https://t.me/{username}"
# =====================================================

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
STATE_FILE = "state.json"

connections: dict[str, dict] = {}   # business_connection_id -> {user_id, username}
state: dict[str, dict] = {}         # "chat_id:message_id" -> данные оффера

if os.path.exists(STATE_FILE):
    state = json.load(open(STATE_FILE, encoding="utf-8"))


def save_state():
    json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False)


def em(emoji_id: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


# ---------- тексты ----------
# порядок: offer, accept, decline, declined, accepted, go
_L = {
    "ru": ("Пользователь (@{user}) предлагает вам\n{amount} {cur} за подарок {gift}.",
           "ПРИНЯТЬ", "ОТКЛОНИТЬ", "Предложение отклонено", "Предложение принято!", "Перейти к подарку"),
    "en": ("User (@{user}) offers you\n{amount} {cur} for the gift {gift}.",
           "ACCEPT", "DECLINE", "Offer declined", "Offer accepted!", "Go to gift"),
    "uk": ("Користувач (@{user}) пропонує вам\n{amount} {cur} за подарунок {gift}.",
           "ПРИЙНЯТИ", "ВІДХИЛИТИ", "Пропозицію відхилено", "Пропозицію прийнято!", "Перейти до подарунка"),
    "be": ("Карыстальнік (@{user}) прапануе вам\n{amount} {cur} за падарунак {gift}.",
           "ПРЫНЯЦЬ", "АДХІЛІЦЬ", "Прапанову адхілена", "Прапанову прынята!", "Перайсці да падарунка"),
    "zh": ("用户 (@{user}) 向您报价\n{amount} {cur} 购买礼物 {gift}。",
           "接受", "拒绝", "报价已拒绝", "报价已接受！", "前往礼物"),
    "ar": ("المستخدم (@{user}) يعرض عليك\n{amount} {cur} مقابل الهدية {gift}.",
           "قبول", "رفض", "تم رفض العرض", "تم قبول العرض!", "الذهاب إلى الهدية"),
    "es": ("El usuario (@{user}) te ofrece\n{amount} {cur} por el regalo {gift}.",
           "ACEPTAR", "RECHAZAR", "Oferta rechazada", "¡Oferta aceptada!", "Ir al regalo"),
    "de": ("Nutzer (@{user}) bietet dir\n{amount} {cur} für das Geschenk {gift}.",
           "ANNEHMEN", "ABLEHNEN", "Angebot abgelehnt", "Angebot angenommen!", "Zum Geschenk"),
    "fr": ("L'utilisateur (@{user}) vous propose\n{amount} {cur} pour le cadeau {gift}.",
           "ACCEPTER", "REFUSER", "Offre refusée", "Offre acceptée !", "Aller au cadeau"),
    "pt": ("O usuário (@{user}) oferece a você\n{amount} {cur} pelo presente {gift}.",
           "ACEITAR", "RECUSAR", "Oferta recusada", "Oferta aceita!", "Ir ao presente"),
    "it": ("L'utente (@{user}) ti offre\n{amount} {cur} per il regalo {gift}.",
           "ACCETTA", "RIFIUTA", "Offerta rifiutata", "Offerta accettata!", "Vai al regalo"),
    "tr": ("Kullanıcı (@{user}) size\n{gift} hediyesi için {amount} {cur} teklif ediyor.",
           "KABUL ET", "REDDET", "Teklif reddedildi", "Teklif kabul edildi!", "Hediyeye git"),
    "pl": ("Użytkownik (@{user}) proponuje Ci\n{amount} {cur} za prezent {gift}.",
           "PRZYJMIJ", "ODRZUĆ", "Oferta odrzucona", "Oferta przyjęta!", "Przejdź do prezentu"),
    "kk": ("Пайдаланушы (@{user}) сізге\n{gift} сыйлығы үшін {amount} {cur} ұсынады.",
           "ҚАБЫЛДАУ", "БАС ТАРТУ", "Ұсыныстан бас тартылды", "Ұсыныс қабылданды!", "Сыйлыққа өту"),
    "uz": ("Foydalanuvchi (@{user}) sizga\n{gift} sovg'asi uchun {amount} {cur} taklif qilmoqda.",
           "QABUL QILISH", "RAD ETISH", "Taklif rad etildi", "Taklif qabul qilindi!", "Sovg'aga o'tish"),
    "hi": ("यूज़र (@{user}) आपको\n{gift} गिफ़्ट के लिए {amount} {cur} का ऑफ़र देता है।",
           "स्वीकार करें", "अस्वीकार करें", "ऑफ़र अस्वीकृत", "ऑफ़र स्वीकृत!", "गिफ़्ट पर जाएं"),
    "id": ("Pengguna (@{user}) menawarkan Anda\n{amount} {cur} untuk hadiah {gift}.",
           "TERIMA", "TOLAK", "Penawaran ditolak", "Penawaran diterima!", "Buka hadiah"),
    "ja": ("ユーザー (@{user}) から\nギフト {gift} に {amount} {cur} のオファーです。",
           "承諾", "拒否", "オファーは拒否されました", "オファーが承諾されました！", "ギフトを開く"),
    "ko": ("사용자 (@{user})님이\n선물 {gift}에 대해 {amount} {cur}를 제안합니다.",
           "수락", "거절", "제안이 거절되었습니다", "제안이 수락되었습니다!", "선물로 이동"),
    "fa": ("کاربر (@{user}) به شما\n{amount} {cur} برای هدیه {gift} پیشنهاد می‌دهد.",
           "پذیرفتن", "رد کردن", "پیشنهاد رد شد", "پیشنهاد پذیرفته شد!", "رفتن به هدیه"),
}
TEXTS = {}
for _k, (_o, _a, _d, _dec, _acc, _go) in _L.items():
    TEXTS[_k] = {
        "offer": _o, "accept_btn": _a, "decline_btn": _d,
        "declined": "{cross} <b>" + _dec + "</b>",
        "accepted": "{check} <b>" + _acc + "</b>\n" + _o.split("\n", 1)[1],
        "go_btn": _go,
    }

# псевдонимы кодов языков
LANG_ALIASES = {"ua": "uk", "by": "be", "cn": "zh", "zh-cn": "zh", "ch": "zh",
                "ae": "ar", "ir": "fa", "jp": "ja", "kr": "ko", "kz": "kk",
                "in": "hi", "br": "pt", "ru-ru": "ru", "us": "en", "gb": "en"}


def cur_html(cur: str) -> str:
    if cur == "stars":
        return em(EMOJI_STAR, "⭐️")
    return html.escape(cur.upper())  # ton и т.д. - просто текстом


def gift_html(link: str) -> str:
    slug = link.rstrip("/").split("/")[-1]            # InstantRamen-224458
    if "-" in slug:
        n, i = slug.rsplit("-", 1)
        name = f"{n} #{i}"
    else:
        name = slug
    return f'<a href="{html.escape(link)}">{html.escape(name)}</a>'


def preview(link: str) -> dict:
    # картинка ПЕРЕД текстом (над сообщением)
    return {"url": link, "show_above_text": True, "prefer_large_media": True}


# ---------- вызов Bot API ----------
async def call(client: httpx.AsyncClient, method: str, **params):
    r = await client.post(f"{API}/{method}", json=params, timeout=70)
    data = r.json()
    if not data.get("ok"):
        print(f"[API ERROR] {method}: {data}")
    return data


def offer_keyboard(t: dict, with_icons: bool = True) -> dict:
    if with_icons:
        return {"inline_keyboard": [[
            {"text": t["accept_btn"], "callback_data": "ok",
             "icon_custom_emoji_id": EMOJI_CHECK},
            {"text": t["decline_btn"], "callback_data": "no",
             "icon_custom_emoji_id": EMOJI_CROSS},
        ]]}
    return {"inline_keyboard": [[
        {"text": "✅ " + t["accept_btn"], "callback_data": "ok"},
        {"text": "❌ " + t["decline_btn"], "callback_data": "no"},
    ]]}


async def get_connection(client, bc_id: str) -> dict:
    if bc_id not in connections:
        res = await call(client, "getBusinessConnection", business_connection_id=bc_id)
        if res.get("ok"):
            u = res["result"]["user"]
            connections[bc_id] = {"user_id": u["id"], "username": u.get("username", "user")}
    return connections.get(bc_id, {})


# ---------- обработка команды ----------
async def handle_business_message(client, msg: dict):
    bc_id = msg.get("business_connection_id")
    text = msg.get("text") or ""
    if not bc_id or not text.startswith("/cried"):
        return

    conn = await get_connection(client, bc_id)
    # реагируем только на сообщения самого владельца аккаунта
    if not conn or msg.get("from", {}).get("id") != conn["user_id"]:
        return

    parts = text.split()
    if len(parts) < 3 or parts[0].split("@")[0].lower() != "/cried":
        return
    link = parts[1]
    amount = parts[2]
    cur = parts[3].lower() if len(parts) > 3 else "stars"
    lang = parts[4].lower() if len(parts) > 4 else "ru"
    lang = LANG_ALIASES.get(lang, lang)
    if lang not in TEXTS:
        lang = "ru"
    if not link.startswith("https://t.me/nft/"):
        return

    chat_id = msg["chat"]["id"]
    t = TEXTS[lang]

    # 1) удаляем команду
    await call(client, "deleteBusinessMessages",
               business_connection_id=bc_id, message_ids=[msg["message_id"]])

    # 2) отправляем оффер от лица владельца
    body = t["offer"].format(user=html.escape(conn["username"]),
                             amount=html.escape(amount),
                             cur=cur_html(cur), gift=gift_html(link))
    params = dict(business_connection_id=bc_id, chat_id=chat_id, text=body,
                  parse_mode="HTML", link_preview_options=preview(link))
    res = await call(client, "sendMessage", **params, reply_markup=offer_keyboard(t, True))
    if not res.get("ok"):  # вдруг иконки в кнопках недоступны - шлём обычные эмодзи
        res = await call(client, "sendMessage", **params, reply_markup=offer_keyboard(t, False))
    if res.get("ok"):
        mid = res["result"]["message_id"]
        state[f"{chat_id}:{mid}"] = dict(bc=bc_id, link=link, amount=amount,
                                          cur=cur, lang=lang, owner=conn["user_id"],
                                          username=conn["username"])
        save_state()


# ---------- нажатия на кнопки ----------
async def handle_callback(client, cq: dict):
    msg = cq.get("message") or {}
    chat_id = msg.get("chat", {}).get("id")
    mid = msg.get("message_id")
    key = f"{chat_id}:{mid}"
    st = state.get(key)
    if not st:
        await call(client, "answerCallbackQuery", callback_query_id=cq["id"])
        return

    # владелец не может нажимать свои же кнопки
    if cq["from"]["id"] == st["owner"]:
        await call(client, "answerCallbackQuery", callback_query_id=cq["id"],
                   text="Это предложение для собеседника")
        return

    t = TEXTS[st["lang"]]
    link = st["link"]
    gift = gift_html(link)
    cur = cur_html(st["cur"])
    amount = html.escape(st["amount"])

    declined = cq["data"] == "no"
    if declined:
        new_text = t["declined"].format(cross=em(EMOJI_CROSS, "❌"))
        markup = {"inline_keyboard": []}
    else:
        new_text = t["accepted"].format(check=em(EMOJI_CHECK, "✅"),
                                        amount=amount, cur=cur, gift=gift)
        url = ACCEPT_URL.format(username=st["username"])
        markup = {"inline_keyboard": [[{"text": t["go_btn"], "url": url}]]}

    await call(client, "answerCallbackQuery", callback_query_id=cq["id"])
    edit = dict(business_connection_id=msg.get("business_connection_id") or st["bc"],
                chat_id=chat_id, message_id=mid, text=new_text, parse_mode="HTML",
                link_preview_options=preview(link))
    res = await call(client, "editMessageText", **edit, reply_markup=markup)
    if not res.get("ok") and not declined:
        # tg:// мог не пройти - пробуем https-ссылку
        url = ACCEPT_URL_FALLBACK.format(username=st["username"])
        markup = {"inline_keyboard": [[{"text": t["go_btn"], "url": url}]]}
        await call(client, "editMessageText", **edit, reply_markup=markup)
    state.pop(key, None)
    save_state()


# ---------- помощник: узнать ID премиум-эмодзи ----------
async def handle_private(client, msg: dict):
    ents = [e for e in msg.get("entities", []) if e["type"] == "custom_emoji"]
    if not ents:
        if msg.get("text", "").startswith("/start"):
            await call(client, "sendMessage", chat_id=msg["chat"]["id"],
                       text="Пришли мне премиум-эмодзи - я скажу его ID.")
        return
    lines = [f"<code>{e['custom_emoji_id']}</code>" for e in ents]
    await call(client, "sendMessage", chat_id=msg["chat"]["id"],
               parse_mode="HTML", text="ID эмодзи:\n" + "\n".join(lines))


async def main():
    offset = 0
    async with httpx.AsyncClient() as client:
        print("Бот запущен")
        while True:
            res = await call(client, "getUpdates", offset=offset, timeout=50,
                             allowed_updates=["message", "callback_query",
                                              "business_connection", "business_message"])
            for u in res.get("result", []):
                offset = u["update_id"] + 1
                try:
                    if "business_connection" in u:
                        bc = u["business_connection"]
                        connections[bc["id"]] = {"user_id": bc["user"]["id"],
                                                 "username": bc["user"].get("username", "user")}
                    elif "business_message" in u:
                        await handle_business_message(client, u["business_message"])
                    elif "callback_query" in u:
                        await handle_callback(client, u["callback_query"])
                    elif "message" in u:
                        await handle_private(client, u["message"])
                except Exception as e:
                    print("ERR:", repr(e))


if __name__ == "__main__":
    asyncio.run(main())
