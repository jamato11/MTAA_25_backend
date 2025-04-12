from flask import Flask, request, jsonify
from dotenv import load_dotenv
import psycopg2
import os
import hashlib
from flask import send_from_directory
import uuid

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

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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

@app.route('/chats', methods=['POST'])
def create_chat():
    data = request.get_json()

    chat_name = data.get('chat_name')
    image = data.get('image')  # This could be a URL or base64 encoded image
    creator_id = data.get('creator_id')  # User who's creating the chat

    if not chat_name or not creator_id:
        return jsonify({"message": "Chat name and creator ID are required"}), 400

    try:
        with connection:
            with connection.cursor() as cursor:
                # Create new chat
                cursor.execute("""
                    INSERT INTO chats (chat_name, image)
                    VALUES (%s, %s)
                    RETURNING chat_id
                """, (chat_name, image))

                chat_id = cursor.fetchone()[0]

                # Add creator as the first member
                cursor.execute("""
                    INSERT INTO chat_members (chat_id, member_id)
                    VALUES (%s, %s)
                """, (chat_id, creator_id))

                return jsonify({
                    "message": "Chat created successfully",
                    "chat": {
                        "chat_id": chat_id,
                        "chat_name": chat_name,
                        "image": image
                    }
                }), 201

    except Exception as error:
        return jsonify({"message": f"Failed to create chat: {str(error)}"}), 500

@app.route('/users/<int:user_id>/chats', methods=['GET'])
def get_user_chats(user_id):
    try:
        with connection:
            with connection.cursor() as cursor:
                # Get all chats that the user is a member of
                cursor.execute("""
                    SELECT c.chat_id, c.chat_name, c.image
                    FROM chats c
                    JOIN chat_members cm ON c.chat_id = cm.chat_id
                    WHERE cm.member_id = %s
                """, (user_id,))

                rows = cursor.fetchall()
                chats = [{"chat_id": row[0], "chat_name": row[1], "image": row[2]} for row in rows]

                return jsonify({"chats": chats}), 200

    except Exception as error:
        return jsonify({"message": f"Failed to retrieve chats: {str(error)}"}), 500

@app.route('/chats/<int:chat_id>', methods=['GET'])
def get_chat(chat_id):
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT chat_id, chat_name, image
                    FROM chats
                    WHERE chat_id = %s
                """, (chat_id,))

                chat = cursor.fetchone()

                if not chat:
                    return jsonify({"message": "Chat not found"}), 404

                chat_data = {"chat_id": chat[0], "chat_name": chat[1], "image": chat[2]}

                return jsonify(chat_data), 200

    except Exception as error:
        return jsonify({"message": f"Failed to retrieve chat: {str(error)}"}), 500

@app.route('/chats/<int:chat_id>', methods=['PUT'])
def update_chat(chat_id):
    data = request.get_json()

    chat_name = data.get('chat_name')
    image = data.get('image')

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE chats
                    SET chat_name = %s, image = %s
                    WHERE chat_id = %s
                    RETURNING chat_id, chat_name, image
                """, (chat_name, image, chat_id))

                updated_chat = cursor.fetchone()

                if not updated_chat:
                    return jsonify({"message": "Chat not found"}), 404

                return jsonify({
                    "message": "Chat updated successfully",
                    "chat": {
                        "chat_id": updated_chat[0],
                        "chat_name": updated_chat[1],
                        "image": updated_chat[2]
                    }
                }), 200

    except Exception as error:
        return jsonify({"message": f"Failed to update chat: {str(error)}"}), 500

@app.route('/chats/<int:chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM chats
                    WHERE chat_id = %s
                    RETURNING chat_id
                """, (chat_id,))

                deleted_chat = cursor.fetchone()

                if not deleted_chat:
                    return jsonify({"message": "Chat not found"}), 404

                return jsonify({"message": "Chat deleted successfully"}), 200

    except Exception as error:
        return jsonify({"message": f"Failed to delete chat: {str(error)}"}), 500

@app.route('/chats/<int:chat_id>/members', methods=['POST'])
def add_chat_member(chat_id):
    data = request.get_json()

    member_id = data.get('member_id')

    if not member_id:
        return jsonify({"message": "Member ID is required"}), 400

    try:
        with connection:
            with connection.cursor() as cursor:
                # Check if user exists
                cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (member_id,))
                if not cursor.fetchone():
                    return jsonify({"message": "User not found"}), 404

                # Check if member already exists in the chat
                cursor.execute("""
                    SELECT membership_id FROM chat_members
                    WHERE chat_id = %s AND member_id = %s
                """, (chat_id, member_id))

                if cursor.fetchone():
                    return jsonify({"message": "User is already a member of this chat"}), 409

                # Add member to the chat
                cursor.execute("""
                    INSERT INTO chat_members (chat_id, member_id)
                    VALUES (%s, %s)
                    RETURNING membership_id
                """, (chat_id, member_id))

                membership_id = cursor.fetchone()[0]

                return jsonify({
                    "message": "Member added to chat successfully",
                    "membership_id": membership_id
                }), 201

    except Exception as error:
        return jsonify({"message": f"Failed to add member to chat: {str(error)}"}), 500

@app.route('/chats/<int:chat_id>/members', methods=['GET'])
def get_chat_members(chat_id):
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT u.user_id, u.name, u.email, cm.membership_id
                    FROM users u
                    JOIN chat_members cm ON u.user_id = cm.member_id
                    WHERE cm.chat_id = %s
                """, (chat_id,))

                rows = cursor.fetchall()
                members = [{
                    "user_id": row[0],
                    "name": row[1],
                    "email": row[2],
                    "membership_id": row[3]
                } for row in rows]

                return jsonify({"members": members}), 200

    except Exception as error:
        return jsonify({"message": f"Failed to retrieve chat members: {str(error)}"}), 500

@app.route('/chats/members/<int:membership_id>', methods=['DELETE'])
def remove_chat_member(membership_id):
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM chat_members
                    WHERE membership_id = %s
                    RETURNING membership_id
                """, (membership_id,))

                deleted_membership = cursor.fetchone()

                if not deleted_membership:
                    return jsonify({"message": "Membership not found"}), 404

                return jsonify({"message": "Member removed from chat successfully"}), 200

    except Exception as error:
        return jsonify({"message": f"Failed to remove member from chat: {str(error)}"}), 500

def save_file(file):
    filename = str(uuid.uuid4()) + '-' + file.filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    return filepath

@app.route('/messages', methods=['POST'])
def create_message():
    message_type = request.form.get('message_type', 'text')
    sender_user_id = request.form.get('sender_user_id')
    recipient_chat_id = request.form.get('recipient_chat_id')
    content = request.form.get('content')

    if not sender_user_id or not recipient_chat_id:
        return jsonify({"message": "Sender ID and recipient chat ID are required"}), 400

    file_path = None

    try:
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            file_path = save_file(file)

        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT membership_id FROM chat_members
                    WHERE chat_id = %s AND member_id = %s
                """, (recipient_chat_id, sender_user_id))

                if not cursor.fetchone():
                    return jsonify({"message": "User is not a member of this chat"}), 403

                cursor.execute("""
                    INSERT INTO messages (sender_user_id, recipient_chat_id, message_type, content, file_path)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING message_id
                """, (sender_user_id, recipient_chat_id, message_type, content, file_path))

                message_id = cursor.fetchone()[0]

                return jsonify({
                    "message": "Message sent successfully",
                    "message_id": message_id
                }), 201

    except Exception as error:
        return jsonify({"message": f"Failed to send message: {str(error)}"}), 500

@app.route('/chats/<int:chat_id>/messages', methods=['GET'])
def get_chat_messages(chat_id):
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT m.message_id, m.sender_user_id, u.name as sender_name, 
                           m.message_type, m.content, m.file_path
                    FROM messages m
                    JOIN users u ON m.sender_user_id = u.user_id
                    WHERE m.recipient_chat_id = %s
                    ORDER BY m.message_id
                """, (chat_id,))

                rows = cursor.fetchall()
                messages = [{
                    "message_id": row[0],
                    "sender_user_id": row[1],
                    "sender_name": row[2],
                    "message_type": row[3],
                    "content": row[4],
                    "file_path": row[5]
                } for row in rows]

                return jsonify({"messages": messages}), 200

    except Exception as error:
        return jsonify({"message": f"Failed to retrieve messages: {str(error)}"}), 500

@app.route('/uploads/<path:filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
