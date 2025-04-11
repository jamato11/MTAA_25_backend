from flask import Flask, request, jsonify
from dotenv import load_dotenv
import psycopg2
import os
import hashlib

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

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({"message": "Name, email and password are required"}), 400

    hashed_password = hash_password(password)

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    return jsonify({"message": "Email already registered"}), 409

                cursor.execute("""
                    INSERT INTO users (name, email, password)
                    VALUES (%s, %s, %s)
                    RETURNING user_id, name, email
                """, (name, email, hashed_password))

                user_id, name, email = cursor.fetchone()

                return jsonify({
                    "message": "User registered successfully",
                    "user": {
                        "user_id": user_id,
                        "name": name,
                        "email": email
                    }
                }), 201

    except Exception as error:
        return jsonify({"message": f"Registration failed: {str(error)}"}), 500
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    hashed_password = hash_password(password)

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT user_id, name, email
                    FROM users
                    WHERE email = %s AND password = %s
                """, (email, hashed_password))

                user = cursor.fetchone()

                if not user:
                    return jsonify({"message": "Invalid email or password"}), 401

                user_id, name, user_email = user

                return jsonify({
                    "message": "Login successful",
                    "user": {
                        "user_id": user_id,
                        "name": name,
                        "email": user_email
                    }
                }), 200

    except Exception as error:
        return jsonify({"message": f"Login failed: {str(error)}"}), 500

@app.route('/tasks', methods=['POST'])
def create_task(): # iba jeden zaznam buď pre chat_id alebo pre owner_user_id
    data = request.get_json()

    title = data.get('title')
    description = data.get('description')
    date = data.get('date')
    time = data.get('time')
    owner_user_id = data.get('owner_user_id')
    chat_id = data.get('chat_id')

    with connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO tasks (title, description, date, time, owner_user_id, chat_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING task_id
            """, (title, description, date, time, owner_user_id, chat_id))
            task_id = cursor.fetchone()[0]

    return jsonify({"message": "Task created", "task_id": task_id}), 201

@app.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id): #ktokoľvek môže upraviť úlohu, ak je členom chatu alebo je vlastníkom úlohy
    data = request.get_json()

    title = data.get('title')
    description = data.get('description')
    date = data.get('date')
    time = data.get('time')
    chat_id = data.get('chat_id')

    with connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE tasks
                SET title = %s,
                    description = %s,
                    date = %s,
                    time = %s,
                    chat_id = %s
                WHERE task_id = %s
            """, (title, description, date, time, chat_id, task_id))

    return jsonify({"message": "Task updated"})

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id): #ktokoľvek môže zmazať úlohu, ak je členom chatu alebo je vlastníkom úlohy
    with connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM tasks WHERE task_id = %s", (task_id,))

    return jsonify({"message": "Task deleted"})

@app.route('/tasks/<int:user_id>', methods=['GET'])
def get_user_tasks(user_id):
    with connection:
        with connection.cursor() as cursor:
            # všetky chat_id, kde je user členom
            cursor.execute("""
                SELECT chat_id FROM chat_members
                WHERE member_id = %s
            """, (user_id,))
            chat_ids = [row[0] for row in cursor.fetchall()]

            chat_filter = ""
            if chat_ids:
                chat_placeholders = ','.join(['%s'] * len(chat_ids))
                chat_filter = f"OR (chat_id IN ({chat_placeholders}))"
                values = [user_id] + chat_ids
            else:
                values = [user_id]
            #všetky ulohy pre owner_user_id
            query = f""" 
                SELECT * FROM tasks
                WHERE owner_user_id = %s
                {chat_filter}
                ORDER BY date, time
            """

            cursor.execute(query, values)
            rows = cursor.fetchall()

            columns = [desc[0] for desc in cursor.description]
            tasks = [dict(zip(columns, row)) for row in rows]

    return jsonify(tasks)
