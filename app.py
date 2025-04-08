from flask import Flask
from dotenv import load_dotenv
import psycopg2
import os


CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
);
"""

CREATE_CHATS_TABLE = """
CREATE TABLE IF NOT EXISTS chats (
    chat_id SERIAL PRIMARY KEY,
    chat_name TEXT NOT NULL,
    image TEXT
);
"""

CREATE_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    date DATE,
    time TIME,
    owner_user_id INTEGER NOT NULL,
    chat_id INTEGER,
    FOREIGN KEY (owner_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE SET NULL
);
"""

CREATE_CHAT_MEMBERS_TABLE = """
CREATE TABLE IF NOT EXISTS chat_members (
    membership_id SERIAL PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES users(user_id) ON DELETE CASCADE
);
"""

CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    message_id SERIAL PRIMARY KEY,
    sender_user_id INTEGER NOT NULL,
    recipient_chat_id INTEGER NOT NULL,
    message_type TEXT,
    content TEXT,
    file_path TEXT,
    FOREIGN KEY (sender_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (recipient_chat_id) REFERENCES chats(chat_id) ON DELETE CASCADE
);
"""

load_dotenv()

url = os.environ.get("DATABASE_URL")
if not url:
    raise ValueError("DATABASE_URL nie je nastavena. Skontrolujte .env súbor")

connection = psycopg2.connect(url)

app = Flask(__name__)

def init_db():
    with connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_USERS_TABLE)
            cursor.execute(CREATE_CHATS_TABLE)
            cursor.execute(CREATE_TASKS_TABLE)
            cursor.execute(CREATE_CHAT_MEMBERS_TABLE)
            cursor.execute(CREATE_MESSAGES_TABLE)
    print("Databáza a tabuľky boli úspešne vytvorené.")

with app.app_context():
    init_db()
