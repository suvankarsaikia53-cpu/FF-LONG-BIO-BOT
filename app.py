import asyncio
import json
import logging
import os
from datetime import datetime
from threading import Thread

import requests
from flask import Flask, jsonify
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)

WAITING_UID, WAITING_PASSWORD, WAITING_ACCESS_TOKEN, WAITING_JWT, WAITING_BIO, WAITING_REGION = range(6)
BAN_USER_STATE = 10
UNBAN_USER_STATE = 11

USERS_DATA_FILE = 'users_data.json'
BANNED_USERS_FILE = 'banned_users.json'
BROADCAST_HISTORY_FILE = 'broadcast_history.json'

BOTTOKEN = os.getenv('BOTTOKEN', '').strip()
BOTUSERNAME = os.getenv('BOTUSERNAME', 'your_bot_username').strip()
BOTDISPLAYNAME = os.getenv('BOTDISPLAYNAME', 'LONG BIO BOT').strip()
API_URL = os.getenv('API_URL', 'https://loing-io.vercel.app/bio_upload').strip()

try:
    ADMINID = int(os.getenv('ADMINID', '0').strip())
except ValueError:
    ADMINID = 0

SUBSCRIPTION_ENTITIES = [
    {"id": -1003564583501, "name": "ð•ð€ðð™ðŽã€†ð‚ðˆð™ð˜", "type": "channel", "link": "https://t.me/+Kp4wwNKJKp42MmQ1"},
    {"id": -1003360548513, "name": "ð„ð—ð” ð‚ðŽðƒð„ð‘ âš¡", "type": "channel", "link": "https://t.me/exucoder1"},
    {"id": -1003645019104, "name": "á´¡á´‡Ê™êœ±Éªá´›á´‡ã€†êœ°ÉªÊŸá´‡", "type": "channel", "link": "https://t.me/+hsxmKaYRjRA2Mzk9"},
    {"id": -1003669933791, "name": "ð„ð—ð”ã€†ðð‘ðˆðŒð„", "type": "channel", "link": "https://t.me/exucodex"},
    {"id": -1003744504956, "name": "ð™¹ðš„ðš‚ðšƒ ð™µðš„ð™½ âš¡", "type": "channel", "link": "https://t.me/funcodex"},
]
TOTAL_SUBSCRIPTIONS = len(SUBSCRIPTION_ENTITIES)

REGIONS = {
    "ðŸ‡®ðŸ‡³ ðˆððƒ": "IND",
    "ðŸ‡¦ðŸ‡ª ðŒð„": "ME",
    "ðŸ‡»ðŸ‡³ ð•ð": "VN",
    "ðŸ‡§ðŸ‡© ððƒ": "BD",
    "ðŸ‡µðŸ‡° ððŠ": "PK",
    "ðŸ‡¸ðŸ‡¬ ð’ð†": "SG",
    "ðŸ‡§ðŸ‡· ðð‘": "BR",
    "ðŸ‡ºðŸ‡¸ ðð€": "NA",
    "ðŸ‡®ðŸ‡© ðˆðƒ": "ID",
    "ðŸ‡·ðŸ‡º ð‘ð”": "RU",
    "ðŸ‡¹ðŸ‡­ ð“ð‡": "TH",
}

USER_SUBSCRIPTION_STATUS = {}


def load_json_file(filename, default_data):
    try:
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning('Failed to load %s: %s', filename, e)
    return default_data


def save_json_file(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_users_data():
    return load_json_file(USERS_DATA_FILE, {})


def save_users_data(data):
    save_json_file(USERS_DATA_FILE, data)


def load_banned_users():
    return load_json_file(BANNED_USERS_FILE, [])


def save_banned_users(data):
    save_json_file(BANNED_USERS_FILE, data)


def load_broadcast_history():
    return load_json_file(BROADCAST_HISTORY_FILE, [])


def save_broadcast_history(data):
    save_json_file(BROADCAST_HISTORY_FILE, data)


users_data = load_users_data()
banned_users = load_banned_users()
broadcast_history = load_broadcast_history()


@flask_app.route('/')
def home():
    return jsonify({
        'status': 'running',
        'bot': BOTDISPLAYNAME,
        'username': BOTUSERNAME,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stats': {
            'total_users': len(users_data),
            'total_channels': TOTAL_SUBSCRIPTIONS,
            'banned_users': len(banned_users),
        },
    })


@flask_app.route('/health')
def health():
    return jsonify({'status': 'healthy'})


def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)), debug=False, use_reloader=False)


def get_admin_panel():
    keyboard = [
        [KeyboardButton('ðŸ“Š ð’ð­ðšð­ð¬'), KeyboardButton('ðŸ‘¥ ð”ð¬ðžð«ð¬')],
        [KeyboardButton('ðŸ“¢ ðð«ð¨ðšððœðšð¬ð­'), KeyboardButton('ðŸ”„ ð…ð¨ð«ð°ðšð«ð')],
        [KeyboardButton('ðŸš« ððšð§ ð”ð¬ðžð«'), KeyboardButton('âœ… ð”ð§ð›ðšð§ ð”ð¬ðžð«')],
        [KeyboardButton('ðŸ“œ ððšð§ð§ðžð ð‹ð¢ð¬ð­'), KeyboardButton('ðŸ“‹ ðð«ð¨ðšððœðšð¬ð­ ð‹ð¨ð ')],
        [KeyboardButton('ðŸ—‘ï¸ ð‚ð¥ðžðšð« ðƒðšð­ðš'), KeyboardButton('âš™ï¸ ð‚ð¡ðžðœð¤ ð€ððˆ')],
        [KeyboardButton('â“ ð‡ðžð¥ð©')],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_user_keyboard():
    keyboard = [
        [KeyboardButton('ðŸ” ð”ðˆðƒ + ðð€ð’ð’ð–ðŽð‘ðƒ')],
        [KeyboardButton('ðŸŽ« ð€ð‚ð‚ð„ð’ð’ ð“ðŽðŠð„ð')],
        [KeyboardButton('ðŸ”‘ ð‰ð–ð“ ð“ðŽðŠð„ð')],
        [KeyboardButton('â“ ð‡ðžð¥ð©')],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton('âŒ ð‚ðšð§ðœðžð¥')]], resize_keyboard=True)


def get_region_keyboard():
    keyboard = []
    row = []
    for flag in REGIONS.keys():
        row.append(KeyboardButton(flag))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([KeyboardButton('ðŸŒ ð€ð”ð“ðŽ-ðƒð„ð“ð„ð‚ð“')])
    keyboard.append([KeyboardButton('âŒ ð‚ðšð§ðœðžð¥')])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def safe_reply(update: Update, text: str, **kwargs):
    if update.message:
        return await update.message.reply_text(text, **kwargs)
    if update.callback_query and update.callback_query.message:
        return await update.callback_query.message.reply_text(text, **kwargs)
    return None


async def check_subscription_change(user_id: int, username: str, first_name: str, context: ContextTypes.DEFAULT_TYPE):
    current_status = []
    unjoined = []

    for entity in SUBSCRIPTION_ENTITIES:
        try:
            chat_member = await context.bot.get_chat_member(chat_id=entity['id'], user_id=user_id)
            if chat_member.status in ['left', 'kicked']:
                current_status.append(f"âŒ {entity['name']}")
                unjoined.append(entity)
            else:
                current_status.append(f"âœ… {entity['name']}")
        except Exception as e:
            logger.error('Error checking %s: %s', entity['name'], e)
            current_status.append(f"âŒ {entity['name']} (Error)")
            unjoined.append(entity)

    old_status = USER_SUBSCRIPTION_STATUS.get(str(user_id))
    if old_status is not None and old_status != current_status and ADMINID:
        notification = (
            'ðŸ”” Subscription change detected!\n\n'
            f'User: {first_name}\n'
            f'User ID: {user_id}\n'
            f"Username: @{username if username else 'not set'}\n\n"
            'Current status:\n' + '\n'.join(current_status)
        )
        try:
            await context.bot.send_message(chat_id=ADMINID, text=notification)
        except Exception as e:
            logger.error('Error notifying admin: %s', e)

    USER_SUBSCRIPTION_STATUS[str(user_id)] = current_status
    return unjoined


async def force_subscription_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False

    user_id = user.id
    if user_id == ADMINID:
        return True

    if user_id in banned_users:
        await safe_reply(update, 'ðŸš« You are banned from using this bot.')
        return False

    if update.message is None:
        return True

    unjoined_entities = await check_subscription_change(user_id, user.username, user.first_name, context)
    if unjoined_entities:
        keyboard = []
        for entity in unjoined_entities:
            if entity.get('link'):
                keyboard.append([InlineKeyboardButton(f"ðŸ“¢ Join {entity['name']}", url=entity['link'])])
        keyboard.append([InlineKeyboardButton('âœ… Verify Subscription', callback_data='verify_subscription')])
        await update.message.reply_text(
            f'ðŸš« Access denied.\n\nProgress: {TOTAL_SUBSCRIPTIONS - len(unjoined_entities)}/{TOTAL_SUBSCRIPTIONS} joined\n\nJoin all required channels first.',
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return False

    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return

    user_id = user.id
    if user_id in banned_users:
        await safe_reply(update, 'ðŸš« You are banned!')
        return

    if str(user_id) not in users_data and user_id != ADMINID:
        users_data[str(user_id)] = {
            'first_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'total_bio_changes': 0,
        }
        save_users_data(users_data)

    if not await force_subscription_check(update, context):
        return

    current_hour = datetime.now().hour
    greeting = 'Good Morning' if current_hour < 12 else 'Good Afternoon' if current_hour < 17 else 'Good Evening'
    reply_markup = get_admin_panel() if user_id == ADMINID else get_user_keyboard()

    await safe_reply(
        update,
        f"ðŸŽ‰ {greeting}, {user.first_name}!\n\nUser ID: {user_id}\nStatus: {'Administrator' if user_id == ADMINID else 'Valued User'}\n\nWelcome to {BOTDISPLAYNAME}.\nChoose a login method below to continue.",
        reply_markup=reply_markup,
    )


async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    unjoined_entities = await check_subscription_change(user.id, user.username, user.first_name, context)
    if not unjoined_entities:
        await query.edit_message_text('âœ… Subscription verified. Use /start to continue.')
        return

    text = 'âŒ Verification failed. Join these first:\n\n' + '\n'.join(f"- {entity['name']}" for entity in unjoined_entities)
    await query.edit_message_text(text)


async def bio_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id in banned_users:
        await update.message.reply_text('ðŸš« You are banned!')
        return ConversationHandler.END

    if text == 'ðŸ” ð”ðˆðƒ + ðð€ð’ð’ð–ðŽð‘ðƒ':
        context.user_data['method'] = 'uid'
        await update.message.reply_text('Send your UID:', reply_markup=get_cancel_keyboard())
        return WAITING_UID
    if text == 'ðŸŽ« ð€ð‚ð‚ð„ð’ð’ ð“ðŽðŠð„ð':
        context.user_data['method'] = 'access'
        await update.message.reply_text('Send your access token:', reply_markup=get_cancel_keyboard())
        return WAITING_ACCESS_TOKEN
    if text == 'ðŸ”‘ ð‰ð–ð“ ð“ðŽðŠð„ð':
        context.user_data['method'] = 'jwt'
        await update.message.reply_text('Send your JWT token:', reply_markup=get_cancel_keyboard())
        return WAITING_JWT
    return ConversationHandler.END


async def get_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == 'âŒ ð‚ðšð§ðœðžð¥':
        await update.message.reply_text('Cancelled.', reply_markup=get_user_keyboard())
        return ConversationHandler.END
    context.user_data['uid'] = update.message.text.strip()
    await update.message.reply_text('Send your password:', reply_markup=get_cancel_keyboard())
    return WAITING_PASSWORD


async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == 'âŒ ð‚ðšð§ðœðžð¥':
        await update.message.reply_text('Cancelled.', reply_markup=get_user_keyboard())
        return ConversationHandler.END
    context.user_data['password'] = update.message.text.strip()
    await update.message.reply_text('Send your bio text:', reply_markup=get_cancel_keyboard())
    return WAITING_BIO


async def get_access_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == 'âŒ ð‚ðšð§ðœðžð¥':
        await update.message.reply_text('Cancelled.', reply_markup=get_user_keyboard())
        return ConversationHandler.END
    context.user_data['access_token'] = update.message.text.strip()
    await update.message.reply_text('Send your bio text:', reply_markup=get_cancel_keyboard())
    return WAITING_BIO


async def get_jwt_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == 'âŒ ð‚ðšð§ðœðžð¥':
        await update.message.reply_text('Cancelled.', reply_markup=get_user_keyboard())
        return ConversationHandler.END
    context.user_data['jwt_token'] = update.message.text.strip()
    await update.message.reply_text('Send your bio text:', reply_markup=get_cancel_keyboard())
    return WAITING_BIO


async def get_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == 'âŒ ð‚ðšð§ðœðžð¥':
        await update.message.reply_text('Cancelled.', reply_markup=get_user_keyboard())
        return ConversationHandler.END

    context.user_data['bio'] = update.message.text.strip()
    if context.user_data.get('method') == 'uid':
        await update.message.reply_text('Choose region:', reply_markup=get_region_keyboard())
        return WAITING_REGION

    await process_bio_upload(update, context, region=None)
    return ConversationHandler.END


async def get_region(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == 'âŒ ð‚ðšð§ðœðžð¥':
        await update.message.reply_text('Cancelled.', reply_markup=get_user_keyboard())
        return ConversationHandler.END
    region = None if update.message.text == 'ðŸŒ ð€ð”ð“ðŽ-ðƒð„ð“ð„ð‚ð“' else REGIONS.get(update.message.text)
    await process_bio_upload(update, context, region)
    return ConversationHandler.END


async def process_bio_upload(update: Update, context: ContextTypes.DEFAULT_TYPE, region=None):
    method = context.user_data.get('method')
    bio = context.user_data.get('bio')
    params = {'bio': bio}

    if method == 'uid':
        params['uid'] = context.user_data.get('uid')
        params['pass'] = context.user_data.get('password')
    elif method == 'access':
        params['access'] = context.user_data.get('access_token')
    elif method == 'jwt':
        params['jwt'] = context.user_data.get('jwt_token')

    if region:
        params['region'] = region

    await update.message.reply_text('â³ Processing your request...')

    try:
        response = requests.get(API_URL, params=params, timeout=30)
        response.raise_for_status()
        result = response.json()

        user_id = str(update.effective_user.id)
        if user_id in users_data:
            users_data[user_id]['total_bio_changes'] = users_data[user_id].get('total_bio_changes', 0) + 1
            save_users_data(users_data)

        if result.get('code') == 200:
            reply = (
                'âœ… SUCCESS\n\n'
                f"Bio: {result.get('bio', bio)}\n"
                f"UID: {result.get('uid', 'N/A')}\n"
                f"Region: {result.get('selected_region', region or 'Auto')}\n"
                f"Bot: {BOTDISPLAYNAME}"
            )
        else:
            reply = (
                'âŒ FAILED\n\n'
                f"Status: {result.get('status', 'Unknown')}\n"
                f"Code: {result.get('code', 'N/A')}\n"
                f"Bot: {BOTDISPLAYNAME}"
            )
    except Exception as e:
        logger.exception('API request failed')
        reply = f'âŒ ERROR\n\n{e}'

    reply_markup = get_admin_panel() if update.effective_user.id == ADMINID else get_user_keyboard()
    await update.message.reply_text(reply, reply_markup=reply_markup)
    context.user_data.clear()


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMINID:
        await update.message.reply_text('âŒ You are not authorized!')
        return
    total_bio_changes = sum(user.get('total_bio_changes', 0) for user in users_data.values())
    stats_text = (
        f'ðŸ“ˆ Bot Statistics\n\nUsers: {len(users_data)}\nBanned: {len(banned_users)}\n'
        f'Channels: {TOTAL_SUBSCRIPTIONS}\nBio Changes: {total_bio_changes}\nBroadcasts: {len(broadcast_history)}\nBot: {BOTDISPLAYNAME}'
    )
    await update.message.reply_text(stats_text, reply_markup=get_admin_panel())


async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMINID:
        await update.message.reply_text('âŒ You are not authorized!')
        return
    if not users_data:
        await update.message.reply_text('No users found.', reply_markup=get_admin_panel())
        return
    users_list = 'ðŸ‘¥ Users List:\n\n'
    for i, (uid, data) in enumerate(list(users_data.items())[:20], 1):
        users_list += f"{i}. {data.get('first_name', 'Unknown')}\n"
        users_list += f"   ID: {uid}\n"
        users_list += f"   First seen: {data.get('first_seen', 'Unknown')}\n"
        users_list += f"   Bio changes: {data.get('total_bio_changes', 0)}\n\n"
    if len(users_data) > 20:
        users_list += f'Total users: {len(users_data)} (showing first 20)'
    await update.message.reply_text(users_list, reply_markup=get_admin_panel())


async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMINID:
        await update.message.reply_text('âŒ You are not authorized!')
        return
    context.user_data['broadcast_mode'] = True
    context.user_data.pop('forward_mode', None)
    await update.message.reply_text('Send the message you want to broadcast. Type /cancel to abort.', reply_markup=get_cancel_keyboard())


async def admin_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMINID:
        await update.message.reply_text('âŒ You are not authorized!')
        return
    context.user_data['forward_mode'] = True
    context.user_data.pop('broadcast_mode', None)
    await update.message.reply_text('Forward a message to broadcast it. Type /cancel to abort.', reply_markup=get_cancel_keyboard())


async def process_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMINID:
        return
    if not context.user_data.get('broadcast_mode') and not context.user_data.get('forward_mode'):
        return

    message = update.message
    if message.text in ['/cancel', 'âŒ ð‚ðšð§ðœðžð¥']:
        context.user_data.pop('broadcast_mode', None)
        context.user_data.pop('forward_mode', None)
        await update.message.reply_text('Broadcast cancelled.', reply_markup=get_admin_panel())
        return

    await update.message.reply_text(f'Broadcasting to {len(users_data)} users...')
    success_count = 0
    fail_count = 0
    is_forward = context.user_data.get('forward_mode', False)

    for user_id_str in list(users_data.keys()):
        try:
            user_id_int = int(user_id_str)
            if user_id_int == ADMINID:
                continue
            if is_forward:
                await message.forward(chat_id=user_id_int)
            else:
                if message.text:
                    await context.bot.send_message(chat_id=user_id_int, text=message.text)
                elif message.photo:
                    await context.bot.send_photo(chat_id=user_id_int, photo=message.photo[-1].file_id, caption=message.caption or '')
                elif message.video:
                    await context.bot.send_video(chat_id=user_id_int, video=message.video.file_id, caption=message.caption or '')
                elif message.document:
                    await context.bot.send_document(chat_id=user_id_int, document=message.document.file_id, caption=message.caption or '')
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1

    broadcast_history.append({
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'type': 'forward' if is_forward else 'broadcast',
        'success': success_count,
        'fail': fail_count,
        'total': len(users_data),
    })
    save_broadcast_history(broadcast_history)
    context.user_data.pop('broadcast_mode', None)
    context.user_data.pop('forward_mode', None)
    await update.message.reply_text(
        f'Broadcast completed.\nSuccess: {success_count}\nFailed: {fail_count}\nTotal: {len(users_data)}',
        reply_markup=get_admin_panel(),
    )


async def admin_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMINID:
        await update.message.reply_text('âŒ You are not authorized!')
        return ConversationHandler.END
    await update.message.reply_text('Send the user ID to ban.', reply_markup=get_cancel_keyboard())
    return BAN_USER_STATE


async def process_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMINID:
        return ConversationHandler.END
    if update.message.text == 'âŒ ð‚ðšð§ðœðžð¥':
        await update.message.reply_text('Cancelled.', reply_markup=get_admin_panel())
        return ConversationHandler.END
    try:
        user_id = int(update.message.text.strip())
        if user_id == ADMINID:
            await update.message.reply_text('Cannot ban admin!', reply_markup=get_admin_panel())
            return ConversationHandler.END
        if user_id not in banned_users:
            banned_users.append(user_id)
            save_banned_users(banned_users)
            await update.message.reply_text(f'User {user_id} banned.', reply_markup=get_admin_panel())
        else:
            await update.message.reply_text(f'User {user_id} already banned.', reply_markup=get_admin_panel())
    except Exception:
        await update.message.reply_text('Invalid user ID!', reply_markup=get_admin_panel())
    return ConversationHandler.END


async def admin_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMINID:
        await update.message.reply_text('âŒ You are not authorized!')
        return ConversationHandler.END
    await update.message.reply_text('Send the user ID to unban.', reply_markup=get_cancel_keyboard())
    return UNBAN_USER_STATE


async def process_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMINID:
        return ConversationHandler.END
    if update.message.text == 'âŒ ð‚ðšð§ðœðžð¥':
        await update.message.reply_text('Cancelled.', reply_markup=get_admin_panel())
        return ConversationHandler.END
    try:
        user_id = int(update.message.text.strip())
        if user_id in banned_users:
            banned_users.remove(user_id)
            save_banned_users(banned_users)
            await update.message.reply_text(f'User {user_id} unbanned.', reply_markup=get_admin_panel())
        else:
            await update.message.reply_text(f'User {user_id} is not banned.', reply_markup=get_admin_panel())
    except Exception:
        await update.message.reply_text('Invalid user ID!', reply_markup=get_admin_panel())
    return ConversationHandler.END


async def admin_banned_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMINID:
        await update.message.reply_text('âŒ You are not authorized!')
        return
    if not banned_users:
        await update.message.reply_text('No banned users.', reply_markup=get_admin_panel())
        return
    await update.message.reply_text('ðŸš« Banned Users:\n\n' + '\n'.join(str(uid) for uid in banned_users), reply_markup=get_admin_panel())


async def admin_broadcast_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMINID:
        await update.message.reply_text('âŒ You are not authorized!')
        return
    if not broadcast_history:
        await update.message.reply_text('No broadcast history.', reply_markup=get_admin_panel())
        return
    lines = ['ðŸ“‹ Broadcast History:\n']
    for i, record in enumerate(broadcast_history[-10:], 1):
        lines.append(f"{i}. {record['timestamp']} | {record['type']} | success {record['success']} | fail {record['fail']}")
    await update.message.reply_text('\n'.join(lines), reply_markup=get_admin_panel())


async def admin_clear_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMINID:
        await update.message.reply_text('âŒ You are not authorized!')
        return
    keyboard = [
        [InlineKeyboardButton('ðŸ—‘ï¸ Clear Users', callback_data='clear_users')],
        [InlineKeyboardButton('ðŸ—‘ï¸ Clear Banned', callback_data='clear_banned')],
        [InlineKeyboardButton('ðŸ—‘ï¸ Clear All', callback_data='clear_all')],
        [InlineKeyboardButton('âŒ Cancel', callback_data='clear_cancel')],
    ]
    await update.message.reply_text('Select what to clear:', reply_markup=InlineKeyboardMarkup(keyboard))


async def clear_data_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'clear_users':
        users_data.clear()
        save_users_data(users_data)
        await query.edit_message_text('User data cleared.')
    elif query.data == 'clear_banned':
        banned_users.clear()
        save_banned_users(banned_users)
        await query.edit_message_text('Banned list cleared.')
    elif query.data == 'clear_all':
        users_data.clear()
        banned_users.clear()
        broadcast_history.clear()
        save_users_data(users_data)
        save_banned_users(banned_users)
        save_broadcast_history(broadcast_history)
        await query.edit_message_text('All data cleared.')
    else:
        await query.edit_message_text('Clear cancelled.')


async def admin_check_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMINID:
        await update.message.reply_text('âŒ You are not authorized!')
        return
    try:
        response = requests.get('https://loing-io.vercel.app/', timeout=10)
        api_status = 'Online' if response.status_code == 200 else f'Status {response.status_code}'
    except Exception:
        api_status = 'Offline'
    await update.message.reply_text(f'API URL: {API_URL}\nStatus: {api_status}', reply_markup=get_admin_panel())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await force_subscription_check(update, context):
        return
    user_id = update.effective_user.id
    if user_id == ADMINID:
        text = 'Admin Help\n\nStats\nUsers\nBroadcast\nForward\nBan User\nUnban User\nBanned List\nBroadcast Log\nClear Data\nCheck API'
        reply_markup = get_admin_panel()
    else:
        text = 'User Help\n\n1. Choose login method\n2. Enter details\n3. Enter bio\n4. Select region if needed'
        reply_markup = get_user_keyboard()
    await safe_reply(update, text, reply_markup=reply_markup)


def validate_config():
    errors = []
    if not BOTTOKEN:
        errors.append('BOTTOKEN environment variable is missing')
    if not ADMINID:
        errors.append('ADMINID environment variable is missing or invalid')
    return errors


def main():
    errors = validate_config()
    if errors:
        raise RuntimeError('; '.join(errors))

    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    application = Application.builder().token(BOTTOKEN).build()

    bio_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r'^ðŸ” ð”ðˆðƒ \+ ðð€ð’ð’ð–ðŽð‘ðƒ$'), bio_menu_handler),
            MessageHandler(filters.Regex(r'^ðŸŽ« ð€ð‚ð‚ð„ð’ð’ ð“ðŽðŠð„ð$'), bio_menu_handler),
            MessageHandler(filters.Regex(r'^ðŸ”‘ ð‰ð–ð“ ð“ðŽðŠð„ð$'), bio_menu_handler),
        ],
        states={
            WAITING_UID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_uid)],
            WAITING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            WAITING_ACCESS_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_access_token)],
            WAITING_JWT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_jwt_token)],
            WAITING_BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bio)],
            WAITING_REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_region)],
        },
        fallbacks=[CommandHandler('cancel', start)],
    )

    ban_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'^ðŸš« ððšð§ ð”ð¬ðžð«$'), admin_ban_user)],
        states={BAN_USER_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_ban_user)]},
        fallbacks=[CommandHandler('cancel', start)],
    )

    unban_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'^âœ… ð”ð§ð›ðšð§ ð”ð¬ðžð«$'), admin_unban_user)],
        states={UNBAN_USER_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_unban_user)]},
        fallbacks=[CommandHandler('cancel', start)],
    )

    application.add_handler(bio_conv_handler)
    application.add_handler(ban_handler)
    application.add_handler(unban_handler)
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CallbackQueryHandler(verify_callback, pattern='^verify_subscription$'))
    application.add_handler(CallbackQueryHandler(clear_data_callback, pattern='^clear_'))
    application.add_handler(MessageHandler(filters.Regex(r'^ðŸ“Š ð’ð­ðšð­ð¬$'), admin_stats))
    application.add_handler(MessageHandler(filters.Regex(r'^ðŸ‘¥ ð”ð¬ðžð«ð¬$'), admin_users))
    application.add_handler(MessageHandler(filters.Regex(r'^ðŸ“¢ ðð«ð¨ðšððœðšð¬ð­$'), admin_broadcast))
    application.add_handler(MessageHandler(filters.Regex(r'^ðŸ”„ ð…ð¨ð«ð°ðšð«ð$'), admin_forward))
    application.add_handler(MessageHandler(filters.Regex(r'^ðŸ“œ ððšð§ð§ðžð ð‹ð¢ð¬ð­$'), admin_banned_list))
    application.add_handler(MessageHandler(filters.Regex(r'^ðŸ“‹ ðð«ð¨ðšððœðšð¬ð­ ð‹ð¨ð $'), admin_broadcast_log))
    application.add_handler(MessageHandler(filters.Regex(r'^ðŸ—‘ï¸ ð‚ð¥ðžðšð« ðƒðšð­ðš$'), admin_clear_data))
    application.add_handler(MessageHandler(filters.Regex(r'^âš™ï¸ ð‚ð¡ðžðœð¤ ð€ððˆ$'), admin_check_api))
    application.add_handler(MessageHandler(filters.Regex(r'^â“ ð‡ðžð¥ð©$'), help_command))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, process_broadcast), group=1)

    logger.info('%s is running', BOTDISPLAYNAME)
    logger.info('Admin ID: %s', ADMINID)
    logger.info('Channels: %s', TOTAL_SUBSCRIPTIONS)
    logger.info('Users: %s', len(users_data))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()