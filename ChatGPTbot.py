import logging
from flask import Flask, request
import random
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.helpers import escape_markdown
import re  # Import thêm để dùng regex kiểm tra định dạng ví Solana
import os
from dotenv import load_dotenv
import json

load_dotenv()

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "Hello, your bot is live!"

@app.route("/", methods=["POST"])
def webhook():
    # Xử lý webhook của Telegram
    return "Webhook received", 200
    data = request.get_json()
    # Thêm logic xử lý dữ liệu từ Telegram tại đây
    print(data)
    return "OK", 200

# Khởi tạo bot Telegram
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Thay bằng token của bạn
application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

# Định nghĩa hàm /start
async def start(update: Update, context):
    await update.message.reply_text("🤖 Welcome to the ELON Rewards Bot!")

application.add_handler(CommandHandler("start", start))

# Endpoint nhận webhook từ Telegram
@app.route('/another_webhook', methods=['POST'])
def another_webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.update_queue.put_nowait(update)
        return "OK", 200

def initialize_google_sheet(sheet):
    """
    Ensure all required columns are in the Google Sheet.
    """
    headers = [
        "User ID",
        "Username",
        "ELON Balance",
        "Boxes Owned",
        "Referrals",
        "ELON Withdrawn",
        "Transaction History",
        "Error Logs",
    ]

    # Kiểm tra xem bảng đã có các cột chưa
    current_headers = sheet.row_values(1)
    if current_headers != headers:
        sheet.clear()
        sheet.append_row(headers)
        logging.info("Google Sheet headers initialized.")
    else:
        logging.info("Google Sheet already initialized.")

# Ensure user data exists before operations
def ensure_user_data(user_id, username="Anonymous"):
    if user_id not in user_data:
        user_data[user_id] = {"elon": 0, "boxes": 1, "referrals": 0, "history": []}
        add_user_to_sheet(user_id, username)
# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
def load_data_from_sheet():
    """
    Load user data from Google Sheets into memory at bot startup.
    """
    global user_data
    user_data = {}  # Reset user_data

    try:
        records = sheet.get_all_records()
        for record in records:
            user_id = str(record["User ID"])
            user_data[user_id] = {
                "elon": int(record["ELON Balance"]),
                "boxes": int(record["Boxes Owned"]),
                "referrals": int(record["Referrals"]),
                "history": record["Transaction History"].split("\n") if record["Transaction History"] else [],
            }
        logging.info("User data successfully loaded from Google Sheets.")
    except Exception as e:
        logging.error(f"Error loading data from Google Sheets: {e}")

# Telegram Bot Token
TELEGRAM_TOKEN = "7423111101:AAG6oYWIdUg_ONZsICSZn88B3ERk8C3PZWQ"

import os
from dotenv import load_dotenv

# Tải các biến môi trường từ file .env
load_dotenv()

# Sử dụng các biến môi trường
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
HELIUS_API_URL = os.getenv("HELIUS_API_URL")
CONTRACT_USDC = os.getenv("CONTRACT_USDC")
BOX_WALLET_ADDRESS = os.getenv("BOX_WALLET_ADDRESS")
BOT_WALLET_PRIVATE_KEY = os.getenv("BOT_WALLET_PRIVATE_KEY")
ELON_MINT_ADDRESS = os.getenv("ELON_MINT_ADDRESS")

if not HELIUS_API_KEY:
    raise ValueError("HELIUS_API_KEY is not set in .env file")

# Google Sheets Config
GOOGLE_SHEET_NAME = "ELON"
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE")
if not GOOGLE_CREDENTIALS_FILE:
    raise ValueError("GOOGLE_CREDENTIALS_FILE is not set in the .env file")

print(f"Using Google credentials file: {GOOGLE_CREDENTIALS_FILE}")
GOOGLE_CREDENTIALS_ENV = "GOOGLE_CREDENTIALS_JSON"

# Initialize Google Sheets
def init_google_sheet():
    try:
        # Phạm vi truy cập Google Sheets API
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

        # Kiểm tra xem có sử dụng biến môi trường hay không
        google_credentials_json = os.getenv(GOOGLE_CREDENTIALS_ENV)
        if google_credentials_json:
            # Tạo credentials từ JSON trong biến môi trường
            logging.info("Initializing Google Sheets using environment variable.")
            credentials = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(google_credentials_json), scope)
        elif os.path.exists(GOOGLE_CREDENTIALS_FILE):
            # Sử dụng tệp JSON nếu có
            logging.info(f"Initializing Google Sheets using file: {GOOGLE_CREDENTIALS_FILE}")
            credentials = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)
        else:
            raise ValueError("Google credentials are not provided. Set GOOGLE_CREDENTIALS_JSON or GOOGLE_CREDENTIALS_FILE.")

        # Kết nối với Google Sheets
        gc = gspread.authorize(credentials)
        sheet = gc.open(GOOGLE_SHEET_NAME).sheet1
        logging.info("Google Sheets connected successfully!")
        return sheet

    except Exception as e:
        logging.error(f"Error initializing Google Sheets: {e}")
        raise

# Khởi tạo kết nối với Google Sheets
try:
    sheet = init_google_sheet()
except ValueError as ve:
    logging.error(f"Configuration Error: {ve}")
except Exception as e:
    logging.error(f"Initialization Failed: {e}")

# User Data (Stored in Memory)
user_data = {}  # {user_id: {"elon": int, "boxes": int, "referrals": int, "history": []}}

def update_user_data(user_id, field, delta):
    """
    Update a specific field (e.g., elon, boxes) for a user by adding delta.
    """
    try:
        cell = sheet.find(str(user_id))
        col = {"elon": 3, "boxes": 4, "referrals": 5, "history": 6}[field]
        current_value = int(sheet.cell(cell.row, col).value or 0)
        new_value = current_value + delta

        # Không cho phép giá trị âm cho ELON hoặc Boxes
        if field in ["elon", "boxes"] and new_value < 0:
            new_value = 0

        sheet.update_cell(cell.row, col, new_value)
        logging.info(f"Updated {field} for User ID {user_id}: {new_value}")
        return new_value
    except Exception as e:
        logging.error(f"Error updating {field} for User ID {user_id}: {e}")
        return None

# Function: Fetch USDC Transactions from Helius
def fetch_usdc_transactions(wallet_address):
    try:
        url = f"{HELIUS_API_URL}/v0/addresses/{wallet_address}/transactions?api-key={HELIUS_API_KEY}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"Helius API Error: {response.text}")
            return []
    except Exception as e:
        logging.error(f"Error fetching transactions: {e}")
        return []

# Function: Validate USDC Payment
def validate_usdc_payment(wallet_address, amount):
    """
    Validate a USDC transaction using Helius API.
    """
    try:
        url = f"{HELIUS_API_URL}/v0/addresses/{wallet_address}/transactions?api-key={HELIUS_API_KEY}"
        response = requests.get(url)
        if response.status_code == 200:
            transactions = response.json()
            for tx in transactions:
                if "tokenTransfers" in tx:
                    for transfer in tx["tokenTransfers"]:
                        if (
                            transfer["toUserAccount"] == wallet_address and
                            transfer["mint"] == CONTRACT_USDC and
                            float(transfer["amount"]) >= amount
                        ):
                            return True
        logging.error(f"Invalid transaction response: {response.text}")
        return False
    except Exception as e:
        logging.error(f"Error validating transaction: {e}")
        return False

# Function: Add User to Google Sheets
def add_user_to_sheet(user_id, username):
    try:
        user_row = [user_id, username, 0, 1, 0, ""]  # ID, Username, ELON, Boxes, Referrals, History
        existing_user = sheet.find(str(user_id))
        if not existing_user:
            sheet.append_row(user_row)
    except Exception as e:
        logging.error(f"Error adding user to Google Sheets: {e}")

# Function: Update User in Google Sheets
def update_user_in_sheet(user_id, field, value):
    """
    Update user data in Google Sheets.
    """
    try:
        cell = sheet.find(str(user_id))
        col = {"elon": 3, "boxes": 4, "referrals": 5, "history": 6}[field]
        current_value = sheet.cell(cell.row, col).value

        # Cộng dồn giá trị nếu cần thiết
        if field == "elon" or field == "boxes":
            value = int(current_value or 0) + value

        sheet.update_cell(cell.row, col, value)
    except Exception as e:
        logging.error(f"Error updating user in Google Sheets: {e}")
def load_user_data_from_sheet(user_id):
    """
    Tải dữ liệu người dùng từ Google Sheets dựa trên ID người dùng.
    """
    try:
        # Tìm hàng chứa thông tin của người dùng trong Google Sheets
        cell = sheet.find(str(user_id))  
        row = sheet.row_values(cell.row)  

        # Trả về thông tin dưới dạng dictionary
        return {
            "elon": int(row[2]),  # Số dư ELON
            "boxes": int(row[3]),  # Số box người dùng sở hữu
            "referrals": int(row[4]),  # Số lượt giới thiệu
            "history": row[5].split("\n") if row[5] else [],  # Lịch sử giao dịch
        }
    except Exception as e:
        logging.error(f"Lỗi khi tải dữ liệu cho user ID {user_id}: {e}")
        # Nếu xảy ra lỗi, trả về giá trị mặc định
        return {"elon": 0, "boxes": 0, "referrals": 0, "history": []}

# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    username = update.message.from_user.username or "Anonymous"
    referrer_username = None

    # Kiểm tra liên kết ref
    if context.args:
        referrer_username = context.args[0]

    # Kiểm tra người dùng có tồn tại không, nếu không thì thêm
    user_data = load_user_data_from_sheet(user_id)
    if user_data["elon"] == 0 and user_data["boxes"] == 0:
        # Người dùng mới -> Thưởng 1 box miễn phí
        update_user_data(user_id, "boxes", 1)
        add_user_to_sheet(user_id, username)
        log_transaction(user_id, "Received 1 free box as a new user")

    # Ghi nhận ref nếu có
    if referrer_username:
        try:
            referrer_row = sheet.find(referrer_username)
            referrer_id = sheet.cell(referrer_row.row, 1).value
            update_user_data(referrer_id, "referrals", 1)
            update_user_data(referrer_id, "boxes", 1)
            log_transaction(referrer_id, f"Earned 1 box from referral by {username}")
        except Exception as e:
            logging.error(f"Error processing referral for {referrer_username}: {e}")

    # Lấy lại dữ liệu để hiển thị
    user_data = load_user_data_from_sheet(user_id)
    boxes = user_data["boxes"]
    elon_balance = user_data["elon"]

    # Tạo menu chính
    referral_link = f"https://t.me/GPTChatAI_bot?start={escape_markdown(username)}"
    keyboard = [
        [InlineKeyboardButton("🎁 Open Box", callback_data="open_box")],
        [InlineKeyboardButton("💸 Buy Box", callback_data="buy_box")],
        [InlineKeyboardButton("🔗 Referral Program", callback_data="referral_program")],
        [InlineKeyboardButton("📤 Withdraw ELON", callback_data="withdraw_elon")],
        [InlineKeyboardButton("📜 View History", callback_data="view_history")],
        [InlineKeyboardButton("🏆 View Top Users", callback_data="view_top_users")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🤖 *Welcome to the ELON Rewards Bot!*\n\n"
        f"💰 *ELON Balance*: {elon_balance} ELON\n"
        f"📦 *Box Count*: {boxes}\n\n"
        f"🔗 *Your Referral Link*: [https://t.me/GPTChatAI_bot?start={escape_markdown(username)}](https://t.me/GPTChatAI_bot?start={escape_markdown(username)})\n\n"
        f"🎉 *Open boxes and win rewards up to 100,000 ELON!*\n"
        f"📦 *Each box is a chance for massive rewards!*\n\n"
        f"🚀 Refer friends to earn 1 free box per referral!",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

# Function: Open Box
async def open_box(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)

    # Lấy dữ liệu người dùng từ Google Sheets
    user_row = sheet.find(user_id)
    user_data = sheet.row_values(user_row.row)
    boxes = int(user_data[3])  # Số lượng box
    elon_balance = int(user_data[2])  # Số dư ELON

    if boxes <= 0:
        await query.answer("❌ You don't have any boxes left. Refer friends or buy more!")
        return

    # Tỉ lệ phần thưởng
    reward = None
    random_chance = random.random()
    if random_chance <= 0.5:  # 50%: 1-100
        reward = random.randint(1, 100)
    elif random_chance <= 0.6:  # 10%: 101-200
        reward = random.randint(101, 200)
    elif random_chance <= 0.65:  # 5%: 201-400
        reward = random.randint(201, 400)
    elif random_chance <= 0.67:  # 2%: 401-600
        reward = random.randint(401, 600)
    elif random_chance <= 0.675:  # 0.5%: 601-1000
        reward = random.randint(601, 1000)
    elif random_chance <= 0.0000001:  # Jackpot: 100,000 ELON với xác suất 0.00000001%
        reward = 100_000
    else:
        reward = 1  # Trường hợp không trúng

    # Trừ box, cộng thưởng và ghi nhận lịch sử
    boxes -= 1
    elon_balance += reward
    history = user_data[5] if len(user_data) > 5 else ""
    new_history = f"{history}\nOpened box: Won {reward} ELON"

    # Giới hạn lịch sử tối đa 30 dòng
    history_lines = new_history.split("\n")
    if len(history_lines) > 30:
        new_history = "\n".join(history_lines[-30:])

    # Cập nhật Google Sheet
    sheet.update_cell(user_row.row, 3, elon_balance)  # Cập nhật số dư ELON
    sheet.update_cell(user_row.row, 4, boxes)  # Cập nhật số box
    sheet.update_cell(user_row.row, 6, new_history)  # Cập nhật lịch sử

    # Tạo nút mở box tiếp theo nếu còn box
    keyboard = []
    if boxes > 0:
        keyboard.append([InlineKeyboardButton("🎁 Open Another Box", callback_data="open_box")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"🎉 *Congratulations!*\n\n"
        f"🎁 You opened a box and won *{reward} ELON*!\n\n"
        f"💰 *Your new balance*: {elon_balance} ELON\n"
        f"📦 *Remaining boxes*: {boxes}",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

# Function: Buy Box
async def buy_box(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)

    keyboard = [
        [InlineKeyboardButton("✅ Confirm Payment", callback_data="confirm_payment")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "💸 *How to Buy a Box*:\n\n"
        "1️⃣ Send 20 USDC to the wallet below:\n"
        "`B2LZH48izgSUvkH2MCeSE4gxRqzi8HUyRDmzzhajdU6R`\n\n"
        "2️⃣ After sending, click *Confirm Payment* below to complete your purchase.\n\n"
        "🎁 You’ll receive 1 box for each transaction!",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )

# Function: Confirm Payment
async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)

    # Kiểm tra giao dịch qua API
    is_valid = validate_usdc_payment("B2LZH48izgSUvkH2MCeSE4gxRqzi8HUyRDmzzhajdU6R", 1)
    if is_valid:
        # Cộng thêm 1 box và ghi nhận lịch sử
        new_boxes = update_user_data(user_id, "boxes", 1)
        log_transaction(user_id, "Bought 1 box with 20 USDC")

        await query.edit_message_text(
            f"✅ *Payment confirmed!*\n\n"
            f"🎁 You’ve received 1 box.\n"
            f"📦 *Your new box count*: {new_boxes}.",
            parse_mode="Markdown",
        )
    else:
        await query.edit_message_text(
            "❌ *Payment not found.*\n\n"
            "Please ensure you’ve sent 20 USDC to the correct wallet:\n"
            "`B2LZH48izgSUvkH2MCeSE4gxRqzi8HUyRDmzzhajdU6R`\n\n"
            "Then try again by clicking *Confirm Payment*.",
            parse_mode="Markdown",
        )

# Function: Referral Program
async def referral_program(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    username = query.from_user.username or "Anonymous"

    ensure_user_data(user_id, username)  # Ensure user data exists

    referral_link = f"https://t.me/GPTChatAI_bot?start={escape_markdown(username)}"
    referrals = user_data[user_id]["referrals"]

    await query.edit_message_text(
        f"🔗 *Referral Program*\n\n"
        f"👥 Invite your friends to earn *1 free box per referral!*\n\n"
        f"✅ *Your Referral Link*: [https://t.me/GPTChatAI_bot?start={escape_markdown(username)}](https://t.me/GPTChatAI_bot?start={escape_markdown(username)})\n"
        f"📦 *Boxes Earned from Referrals*: {referrals}\n\n"
        f"🚀 Share your referral link now!",
        parse_mode="Markdown"
    )


def log_error(user_id, error_message):
    """
    Log an error to the Google Sheet for the user.
    """
    try:
        cell = sheet.find(str(user_id))
        row = cell.row
        current_errors = sheet.cell(row, 8).value  # Cột "Error Logs"
        updated_errors = f"{current_errors}\n{error_message}" if current_errors else error_message
        sheet.update_cell(row, 8, updated_errors)
        logging.error(f"Error logged for User ID {user_id}: {error_message}")
    except Exception as e:
        logging.error(f"Error logging error for User ID {user_id}: {e}")

# Function: Withdraw ELON
async def withdraw_elon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)

    # Lấy dữ liệu người dùng từ Google Sheets
    user_data = load_user_data_from_sheet(user_id)
    elon_balance = user_data["elon"]

    if elon_balance <= 0:
        await query.edit_message_text(
            "❌ *You don't have enough ELON to withdraw.*",
            parse_mode="Markdown"
        )
        log_error(user_id, "Attempted withdrawal with insufficient balance.")
        return

    await query.edit_message_text(
        "📤 *Withdraw ELON*\n\n"
        "Please send your Solana wallet address to withdraw your ELON.",
        parse_mode="Markdown"
    )

    # Lưu dữ liệu rút vào context
    context.user_data["awaiting_wallet"] = True
    context.user_data["withdraw_amount"] = elon_balance


def send_elon(to_address, amount):
    """
    Sends ELON from the bot wallet to the user's wallet using Helius API.
    """
    try:
        url = f"{HELIUS_API_URL}/v0/transactions?api-key={HELIUS_API_KEY}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "fromPrivateKey": BOT_WALLET_PRIVATE_KEY,
            "toPublicKey": to_address,
            "amount": str(amount),
            "tokenAddress": ELON_MINT_ADDRESS,
            "network": "mainnet-beta",
        }

        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            tx_signature = response.json().get("signature")
            logging.info(f"Transaction successful: {tx_signature}")
            return tx_signature
        else:
            logging.error(f"Transaction failed: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Error sending ELON: {e}")
        return None
async def handle_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    wallet_address = update.message.text.strip()

    # Kiểm tra nếu không có yêu cầu rút trước đó
    if "awaiting_wallet" not in context.user_data or not context.user_data["awaiting_wallet"]:
        await update.message.reply_text("❌ Invalid request. Please start the process again.")
        return

    # Kiểm tra định dạng ví Solana bằng regex
    if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', wallet_address):
        await update.message.reply_text(
            "❌ *Invalid wallet address.*\n\n"
            "A valid Solana wallet address should:\n"
            "- Be 32 to 44 characters long.\n"
            "- Contain only alphanumeric characters excluding `0`, `I`, `O`, and `l`.\n\n"
            "Please try again.",
            parse_mode="Markdown"
        )
        # Ghi log lỗi vào Google Sheets
        log_error(user_id, f"Invalid wallet address provided: {wallet_address}")
        return

    # Lấy số dư rút
    withdraw_amount = context.user_data.get("withdraw_amount", 0)

    if withdraw_amount <= 0:
        await update.message.reply_text(
            "❌ *You don't have enough ELON to withdraw.*",
            parse_mode="Markdown"
        )
        return

    # Tiến hành gửi ELON
    tx_signature = send_elon(wallet_address, withdraw_amount)
    if tx_signature:
        # Cập nhật dữ liệu sau khi rút thành công
        context.user_data["awaiting_wallet"] = False
        context.user_data["withdraw_amount"] = 0

        # Cập nhật Google Sheets
        user_row = sheet.find(user_id)
        sheet.update_cell(user_row.row, 3, 0)  # Đặt số dư ELON về 0
        log_transaction(user_id, f"Withdrew {withdraw_amount} ELON to {wallet_address} (Tx: {tx_signature})")

        await update.message.reply_text(
            f"✅ *Withdrawal successful!*\n\n"
            f"You’ve withdrawn *{withdraw_amount} ELON* to `{wallet_address}`.\n"
            f"Transaction ID: `{tx_signature}`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ *Withdrawal failed.*\n\nPlease try again later.",
            parse_mode="Markdown"
        )         
# Function: View History
async def view_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)

    # Lấy lịch sử từ Google Sheets
    user_row = sheet.find(user_id)
    user_data = sheet.row_values(user_row.row)
    history = user_data[5].split("\n") if len(user_data) > 5 and user_data[5] else []

    if not history:
        await query.edit_message_text("📜 *Your History:*\n\nNo history available yet.", parse_mode="Markdown")
        return

    history_text = "\n".join(history)
    await query.edit_message_text(
        f"📜 *Your History:*\n\n{history_text}",
        parse_mode="Markdown",
    )
async def display_top_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Lấy toàn bộ dữ liệu từ Google Sheets
        records = sheet.get_all_records()

        # Sắp xếp danh sách theo số lượng ELON nhận được (cột "ELON Balance")
        sorted_users = sorted(records, key=lambda x: x["ELON Balance"], reverse=True)

        # Lấy top 10 người dùng
        top_users = sorted_users[:10]

        # Tạo nội dung hiển thị
        leaderboard = "🏆 *Top 10 Users by ELON Balance:*\n\n"
        for rank, user in enumerate(top_users, start=1):
            username = user["Username"] or "Anonymous"
            elon_balance = user["ELON Balance"]
            leaderboard += f"{rank}. {username}: {elon_balance} ELON\n"

        # Gửi thông báo đến người dùng
        await update.message.reply_text(
            leaderboard,
            parse_mode="Markdown",
        )

    except Exception as e:
        logging.error(f"Error displaying top users: {e}")
        await update.message.reply_text(
            "❌ Unable to fetch leaderboard at the moment. Please try again later."
        )
async def view_top_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Trả lời tương tác nút để tránh trạng thái "chờ"

    try:
        # Lấy toàn bộ dữ liệu từ Google Sheets
        records = sheet.get_all_records()

        # Sắp xếp danh sách theo số lượng ELON nhận được
        sorted_users = sorted(records, key=lambda x: x["ELON Balance"], reverse=True)

        # Lấy top 10 người dùng
        top_users = sorted_users[:10]

        # Tạo nội dung hiển thị
        leaderboard = "🏆 *Top 10 Users by ELON Balance:*\n\n"
        for rank, user in enumerate(top_users, start=1):
            username = user["Username"] or "Anonymous"
            elon_balance = user["ELON Balance"]
            leaderboard += f"{rank}. {username}: {elon_balance} ELON\n"

        # Hiển thị bảng xếp hạng
        await query.edit_message_text(
            leaderboard,
            parse_mode="Markdown",
        )
    except Exception as e:
        logging.error(f"Error displaying top users: {e}")
        await query.edit_message_text(
            "❌ Unable to fetch leaderboard at the moment. Please try again later."
        )

def log_transaction(user_id, description):
    """
    Log a transaction for the user in Google Sheets.
    """
    try:
        cell = sheet.find(str(user_id))
        row = cell.row
        current_history = sheet.cell(row, 6).value or ""
        updated_history = f"{current_history}\n{description}".strip()

        # Giới hạn lịch sử tối đa 30 dòng
        history_lines = updated_history.split("\n")
        if len(history_lines) > 30:
            updated_history = "\n".join(history_lines[-30:])

        sheet.update_cell(row, 6, updated_history)
        logging.info(f"Transaction logged for User ID {user_id}: {description}")
    except Exception as e:
        logging.error(f"Error logging transaction for User ID {user_id}: {e}")

def update_missing_usernames():
    """
    Cập nhật username còn thiếu trong Google Sheets.
    """
    try:
        records = sheet.get_all_records()
        for idx, record in enumerate(records, start=2):  # Bỏ qua tiêu đề
            user_id = record["User ID"]
            username = record["Username"]
            if not username:
                sheet.update_cell(idx, 2, "Anonymous")
                logging.info(f"Updated missing username for User ID {user_id}")
    except Exception as e:
        logging.error(f"Error updating missing usernames: {e}")


# Main Function
def main():
    # Khởi tạo Google Sheets
    initialize_google_sheet(sheet)

    # Tải dữ liệu từ Google Sheets
    load_data_from_sheet()

    # Khởi động bot
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(open_box, pattern="open_box"))
    application.add_handler(CallbackQueryHandler(buy_box, pattern="buy_box"))
    application.add_handler(CallbackQueryHandler(confirm_payment, pattern="confirm_payment"))
    application.add_handler(CallbackQueryHandler(view_history, pattern="view_history"))
    application.add_handler(CallbackQueryHandler(referral_program, pattern="referral_program"))
    application.add_handler(CallbackQueryHandler(withdraw_elon, pattern="withdraw_elon"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_address))
    application.add_handler(CallbackQueryHandler(view_top_users, pattern="view_top_users"))

    application.run_polling()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

