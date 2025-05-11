from flask import Flask, request, jsonify
from dotenv import load_dotenv
import psycopg2
import os
import hashlib
import datetime
from flask import Response
from flasgger import Swagger

#vytvaranie tabuliek
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
    dateDeadline DATE,
    timeDeadline TIME,
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
    file_data BYTEA,
    file_name TEXT,
    file_mimetype TEXT,
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
swagger = Swagger(app)

#vytvorenie tabuliek pri spusteni
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
    """Registrácia nového používateľa
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
              description: Meno používateľa
            email:
              type: string
              format: email
              description: Email používateľa
            password:
              type: string
              description: Heslo používateľa
    responses:
      201:
        description: Úspešne registrovaný používateľ
        schema:
          type: object
          properties:
            message:
              type: string
              example: "User registered successfully"
            user:
              type: object
              properties:
                user_id:
                  type: integer
                  example: 1
                name:
                  type: string
                  example: "Meno Používateľa"
                email:
                  type: string
                  example: "email@priklad.sk"
      400:
        description: Chýbajúce povinné polia
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Meno, email a heslo sú povinné"
      409:
        description: Zadaný email je už registrovaný
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Zadaný email je už registrovaný"
      500:
        description: Chyba na pri registrácii
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chyba pri registrácii"
    """
    data = request.get_json()

    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({"message": "Meno, email a heslo sú povinné"}), 400

    hashed_password = hash_password(password)

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    return jsonify({"message": "Zadaný email je už registrovaný"}), 409

                cursor.execute("""
                    INSERT INTO users (name, email, password)
                    VALUES (%s, %s, %s)
                    RETURNING user_id, name, email
                """, (name, email, hashed_password))

                user_id, name, email = cursor.fetchone()

                return jsonify({
                    "message": "Úspešne registrovaný používateľ",
                    "user": {
                        "user_id": user_id,
                        "name": name,
                        "email": email
                    }
                }), 201

    except Exception as error:
        return jsonify({"message": f"Chyba pri registrácii: {str(error)}"}), 500

@app.route('/login', methods=['POST'])
def login():
    """Prihlásenie existujúceho používateľa
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            email:
              type: string
              format: email
              description: Email používateľa
            password:
              type: string
              description: Heslo používateľa
    responses:
      200:
        description: Úspešné prihlásenie
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Úspešné prihlásenie"
            user:
              type: object
              properties:
                user_id:
                  type: integer
                  example: 1
                name:
                  type: string
                  example: "Meno Používateľa"
                email:
                  type: string
                  example: "email@priklad.sk"
      400:
        description: Chýbajúce povinné polia
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Email a heslo sú povinné"
      401:
        description: Nesprávný email alebo heslo
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Nesprávny email alebo heslo"
      500:
        description: Chyba na pri prihlásení
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chyba pri prihlásení"
    """
    data = request.get_json()

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Email a heslo sú povinné"}), 400

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
                    return jsonify({"message": "Nesprávny email alebo heslo"}), 401

                user_id, name, user_email = user

                return jsonify({
                    "message": "Úspešné prihlásenie",
                    "user": {
                        "user_id": user_id,
                        "name": name,
                        "email": user_email
                    }
                }), 200

    except Exception as error:
        return jsonify({"message": f"Chyba pri prihlásení: {str(error)}"}), 500

@app.route('/tasks', methods=['POST'])
def create_task(): # iba jeden zaznam buď pre chat_id alebo pre owner_user_id
    """Vytvorenie novej úlohy
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            title:
              type: string
              description: Názov úlohy
            description:
              type: string
              description: Popis úlohy
            date:
              type: string
              format: date
              description: Dátum splnenia úlohy (YYYY-MM-DD)
            time:
              type: string
              format: time
              description: Čas splnenia úlohy (HH:MM:SS)
            owner_user_id:
              type: integer
              description: ID vlastníka úlohy (pre osobnú úlohu)
            chat_id:
              type: integer
              description: ID chatu, do ktorého úloha patrí
          required:
            - title
    responses:
      201:
        description: Úloha úspešne vytvorená
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Úloha úspešne vytvorená"
            task_id:
              type: integer
              example: 1
      400:
        description: Chýbajúci názov alebo dátum
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chýbajúci názov alebo dátum"
      500:
        description: Chyba pri vytváraní úlohy
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Failed to create task"
    """
    data = request.get_json()

    title = data.get('title')
    description = data.get('description')
    date = data.get('date')
    time = data.get('time')
    owner_user_id = data.get('owner_user_id')
    chat_id = data.get('chat_id')

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO tasks (title, description, date, time, owner_user_id, chat_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING task_id
                """, (title, description, date, time, owner_user_id, chat_id))
                task_id = cursor.fetchone()[0]

                if not title or not date:
                    return jsonify({"message": "Chýbajúci názov alebo dátum"}), 401

                return jsonify({"message": "Úloha úspešne vytvorená", "task_id": task_id}), 201

    except Exception as error:
        return jsonify({"message": f"Chyba pri vytváraní úlohy: {str(error)}"}), 500


@app.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id): #ktokoľvek môže upraviť úlohu, ak je členom chatu alebo je vlastníkom úlohy
    """Úprava existujúcej úlohy
    ---
    parameters:
      - name: task_id
        in: path
        type: integer
        required: true
        description: ID úlohy na úpravu
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            title:
              type: string
              description: Nový názov úlohy
            description:
              type: string
              description: Nový popis úlohy
            date:
              type: string
              format: date
              description: Nový dátum splnenia úlohy (YYYY-MM-DD)
            time:
              type: string
              format: time
              description: Nový čas splnenia úlohy (HH:MM:SS)
            chat_id:
              type: integer
              description: ID chatu, do ktorého úloha patrí
    responses:
      200:
        description: Úloha úspešne upravená
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Úloha úspešne upravená"
      500:
        description: Chyba pri úprave úlohy
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chyba pri úprave úlohy"
    """
    data = request.get_json()

    title = data.get('title')
    description = data.get('description')
    date = data.get('date')
    time = data.get('time')
    chat_id = data.get('chat_id')

    try:
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

        return jsonify({"message": "Úloha úspešne aktualizovaná"})

    except Exception as error:
        return jsonify({"message": f"Chyba pri úprave úlohy: {str(error)}"}), 500

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id): #ktokoľvek môže zmazať úlohu, ak je členom chatu alebo je vlastníkom úlohy
    """Odstránenie úlohy
    ---
    parameters:
      - name: task_id
        in: path
        type: integer
        required: true
        description: ID úlohy na odstránenie
    responses:
      200:
        description: Úloha úspešne odstránená
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Úloha úspešne odstránená"
      500:
        description: Chyba pri odstraňovaní úlohy
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chyba pri odstraňovaní úlohy"
    """
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM tasks WHERE task_id = %s", (task_id,))

        return jsonify({"message": "Úloha úspešne odstránená"})

    except Exception as error:
        return jsonify({"message": f"Chyba pri odstraňovaní úlohy: {str(error)}"}), 500

@app.route('/tasks/<int:user_id>', methods=['GET'])
def get_user_tasks(user_id):
    """Získanie úloh pre daného používateľa
    ---
    parameters:
      - name: user_id
        in: path
        type: integer
        required: true
        description: ID používateľa
    responses:
      200:
        description: Zoznam úloh používateľa
        schema:
          type: array
          items:
            type: object
            properties:
              task_id:
                type: integer
                example: 1
              title:
                type: string
                example: "Názov úlohy"
              description:
                type: string
                example: "Popis úlohy"
              date:
                type: string
                format: date
                example: "2025-04-15"
              time:
                type: string
                format: time
                example: "10:00:00"
              owner_user_id:
                type: integer
                example: 1
              chat_id:
                type: integer
                example: null
      500:
        description: Chyba pri získavaní úloh
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chyba pri získavaní úloh"
    """

    try:
        with connection:
            with connection.cursor() as cursor:
                # všetky chat_id, kde je user členom
                cursor.execute("""
                    SELECT chat_id FROM chat_members
                    WHERE member_id = %s
                """, (user_id,))
                chat_ids = [row[0] for row in cursor.fetchall()]

                chat_filter = ""
                values = [user_id]
                if chat_ids:
                    placeholders = ','.join(['%s'] * len(chat_ids))
                    chat_filter = f" OR (chat_id IN ({placeholders}))"
                    values += chat_ids

                query = f"""
                    SELECT * FROM tasks
                    WHERE owner_user_id = %s
                    {chat_filter}
                    ORDER BY date, time
                """

                cursor.execute(query, values)
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                tasks = []
                for row in rows:
                    task = dict(zip(columns, row))
                    if isinstance(task.get('date'), (datetime.date,)):
                        task['date'] = task['date'].isoformat()
                    if isinstance(task.get('time'), (datetime.time,)):
                        task['time'] = task['time'].strftime('%H:%M:%S')
                    tasks.append(task)

        return jsonify(tasks), 200

    except Exception as error:
        return jsonify({"message": f"Chyba pri získavaní úloh: {str(error)}"}), 500

@app.route('/chats', methods=['POST'])
def create_chat():
    """Vytvorenie nového chatu
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            chat_name:
              type: string
              description: Názov chatu
            image:
              type: string
              description: URL alebo base64 kód obrázka chatu
            creator_id:
              type: integer
              description: ID používateľa, ktorý chat vytvára
          required:
            - chat_name
            - creator_id
    responses:
      201:
        description: Chat úspešne vytvorený
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chat úspešne vytvorený"
            chat:
              type: object
              properties:
                chat_id:
                  type: integer
                  example: 1
                chat_name:
                  type: string
                  example: "Názov chatu"
                image:
                  type: string
                  example: "URL_obrazku_alebo_base64"
      500:
        description: Chyba pri vytváraní chatu
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chyba pri vytváraní chatu"
    """
    data = request.get_json()

    chat_name = data.get('chat_name')
    image = data.get('image')
    creator_id = data.get('creator_id')

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO chats (chat_name, image)
                    VALUES (%s, %s)
                    RETURNING chat_id
                """, (chat_name, image))

                chat_id = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO chat_members (chat_id, member_id)
                    VALUES (%s, %s)
                """, (chat_id, creator_id))

                return jsonify({
                    "message": "Chat úspešne vytvorený",
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
    """Získanie všetkých chatov, ktorých je daný používateľ členom
    ---
    parameters:
      - name: user_id
        in: path
        type: integer
        required: true
        description: ID používateľa
    responses:
      200:
        description: Zoznam chatov používateľa
        schema:
          type: object
          properties:
            chats:
              type: array
              items:
                type: object
                properties:
                  chat_id:
                    type: integer
                    example: 1
                  chat_name:
                    type: string
                    example: "Názov chatu"
                  image:
                    type: string
                    example: "URL_obrazku_alebo_base64"
      500:
        description: Chyba pri získavaní chatov
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chyba pri získavaní chatov"
    """
    try:
        with connection:
            with connection.cursor() as cursor:
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
        return jsonify({"message": f"Chyba pri získavaní chatov: {str(error)}"}), 500

@app.route('/chats/<int:chat_id>', methods=['GET'])
def get_chat(chat_id):
    """Získanie informácií o konkrétnom chate
    ---
    parameters:
      - name: chat_id
        in: path
        type: integer
        required: true
        description: ID chatu
    responses:
      200:
        description: Informácie o chate
        schema:
          type: object
          properties:
            chat_id:
              type: integer
              example: 1
            chat_name:
              type: string
              example: "Názov chatu"
            image:
              type: string
              example: "URL_obrazku_alebo_base64"
      500:
        description: Chyba pri získavaní chatu
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chyba pri získavaní chatu"
    """
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT chat_id, chat_name, image
                    FROM chats
                    WHERE chat_id = %s
                """, (chat_id,))

                chat = cursor.fetchone()

                chat_data = {"chat_id": chat[0], "chat_name": chat[1], "image": chat[2]}

                return jsonify(chat_data), 200

    except Exception as error:
        return jsonify({"message": f"Chyba pri získavaní chatu: {str(error)}"}), 500

@app.route('/chats/<int:chat_id>', methods=['PUT'])
def update_chat(chat_id):
    """Aktualizácia informácií o chate
    ---
    parameters:
      - name: chat_id
        in: path
        type: integer
        required: true
        description: ID chatu na aktualizáciu
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            chat_name:
              type: string
              description: Nový názov chatu
            image:
              type: string
              description: Nová URL alebo base64 kód obrázka chatu
    responses:
      200:
        description: Chat úspešne upravený
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chat úspešne upravený"
            chat:
              type: object
              properties:
                chat_id:
                  type: integer
                  example: 1
                chat_name:
                  type: string
                  example: "Nový názov chatu"
                image:
                  type: string
                  example: "Nová_URL_alebo_base64"
      500:
        description: Chyba pri upravení chatu
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chyba pri upravení chatu"
    """
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

                return jsonify({
                    "message": "Chat úspešne upravený",
                    "chat": {
                        "chat_id": updated_chat[0],
                        "chat_name": updated_chat[1],
                        "image": updated_chat[2]
                    }
                }), 200

    except Exception as error:
        return jsonify({"message": f"Chyba pri upravení chatu: {str(error)}"}), 500

@app.route('/chats/<int:chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    """Odstránenie chatu
    ---
    parameters:
      - name: chat_id
        in: path
        type: integer
        required: true
        description: ID chatu na odstránenie
    responses:
      200:
        description: Chat úspešne odstránený
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chat úspešne odstránený"
      500:
        description: Chyba pri odstraňovaní chatu
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chyba pri odstraňovaní chatu"
    """
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM chats
                    WHERE chat_id = %s
                    RETURNING chat_id
                """, (chat_id,))

                return jsonify({"message": "Chat úspešne odstránený"}), 200

    except Exception as error:
        return jsonify({"message": f"Chyba pri odstraňovaní chatu: {str(error)}"}), 500

@app.route('/chats/<int:chat_id>/members', methods=['POST'])
def add_chat_member(chat_id):
    """Pridanie používateľa do chatu
    ---
    parameters:
      - name: chat_id
        in: path
        type: integer
        required: true
        description: ID chatu, do ktorého sa pridáva člen
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            member_id:
              type: integer
              description: ID používateľa, ktorý sa má pridať do chatu
          required:
            - member_id
    responses:
      201:
        description: Používateľ úspešne pridaný do chatu
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Member added to chat successfully"
            membership_id:
              type: integer
              example: 3
      409:
        description: Používateľ je už členom tohto chatu
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Používateľ je už členom tohto chatu"
      500:
        description: Chyba na strane servera pri pridávaní člena do chatu
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chyba na strane servera pri pridávaní člena do chatu"
    """
    data = request.get_json()

    member_id = data.get('member_id')

    if not member_id:
        return jsonify({"message": "Member ID is required"}), 400

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (member_id,))

                cursor.execute("""
                    SELECT membership_id FROM chat_members
                    WHERE chat_id = %s AND member_id = %s
                """, (chat_id, member_id))

                if cursor.fetchone():
                    return jsonify({"message": "Používateľ je už členom tohto chatu"}), 409

                cursor.execute("""
                    INSERT INTO chat_members (chat_id, member_id)
                    VALUES (%s, %s)
                    RETURNING membership_id
                """, (chat_id, member_id))

                membership_id = cursor.fetchone()[0]

                return jsonify({
                    "message": "Používateľ úspešne pridaný do chatu",
                    "membership_id": membership_id
                }), 201

    except Exception as error:
        return jsonify({"message": f"Chyba na strane servera pri pridávaní člena do chatu: {str(error)}"}), 500

@app.route('/chats/<int:chat_id>/members', methods=['GET'])
def get_chat_members(chat_id):
    """Získanie zoznamu členov daného chatu
    ---
    parameters:
      - name: chat_id
        in: path
        type: integer
        required: true
        description: ID chatu
    responses:
      200:
        description: Zoznam členov chatu
        schema:
          type: object
          properties:
            members:
              type: array
              items:
                type: object
                properties:
                  user_id:
                    type: integer
                    example: 1
                  name:
                    type: string
                    example: "Meno Používateľa"
                  email:
                    type: string
                    example: "email@priklad.sk"
                  membership_id:
                    type: integer
                    example: 3
      500:
        description: Chyba pri získavaní členov chatu
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chyba pri získavaní členov chatu"
    """
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
        return jsonify({"message": f"Chyba pri získavaní členov chatu: {str(error)}"}), 500

@app.route('/chats/members/<int:membership_id>', methods=['DELETE'])
def remove_chat_member(membership_id):
    """Odstránenie používateľa z chatu
    ---
    parameters:
      - name: membership_id
        in: path
        type: integer
        required: true
        description: ID členstva na odstránenie
    responses:
      200:
        description: Používateľ úspešne odstránený z chatu
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Používateľ úspešne odstránený z chatu"
      500:
        description: Chyba pri odstraňovaní člena z chatu
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Failed to remove member from chas"
    """
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM chat_members
                    WHERE membership_id = %s
                    RETURNING membership_id
                """, (membership_id,))

                return jsonify({"message": "Používateľ úspešne odstránený z chatu"}), 200

    except Exception as error:
        return jsonify({"message": f"Chyba pri odstraňovaní člena z chatu: {str(error)}"}), 500

def get_binary_file_data(file):
    return file.read()

@app.route('/messages', methods=['POST'])
def create_message():
    """Odoslanie novej správy do chatu
    ---
    parameters:
      - name: sender_user_id
        in: formData
        type: integer
        required: true
        description: ID odosielateľa
      - name: recipient_chat_id
        in: formData
        type: integer
        required: true
        description: ID cieľového chatu
      - name: message_type
        in: formData
        type: string
        description: Typ správy ('text' alebo iný pre súbor)
      - name: content
        in: formData
        type: string
        description: Text správy (vyžadované pre message_type 'text')
      - name: file
        in: formData
        type: file
        description: Súbor na odoslanie (vyžadované pre message_type iný ako 'text')
    consumes:
      - multipart/form-data
    responses:
      201:
        description: Správa úspešne odoslaná
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Správa úspešne odoslaná"
            message_id:
              type: integer
              example: 1
      500:
        description: Chyba pri odosielaní správy
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chyba pri odosielaní správy"
    """
    message_type = request.form.get('message_type', 'text')
    sender_user_id = request.form.get('sender_user_id')
    recipient_chat_id = request.form.get('recipient_chat_id')
    content = request.form.get('content')

    if not sender_user_id or not recipient_chat_id:
        return jsonify({"message": "Sender ID and recipient chat ID are required"}), 400

    file_data = None
    file_name = None
    file_mimetype = None

    try:
        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            file_data = get_binary_file_data(file)
            file_name = file.filename
            file_mimetype = file.content_type

        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT membership_id FROM chat_members
                    WHERE chat_id = %s AND member_id = %s
                """, (recipient_chat_id, sender_user_id))

                cursor.execute("""
                    INSERT INTO messages (sender_user_id, recipient_chat_id, message_type, content, file_data, file_name, file_mimetype)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING message_id
                """, (sender_user_id, recipient_chat_id, message_type, content, file_data, file_name, file_mimetype))

                message_id = cursor.fetchone()[0]

                return jsonify({
                    "message": "Správa úspešne odoslaná",
                    "message_id": message_id
                }), 201

    except Exception as error:
        return jsonify({"message": f"Chyba pri odosielaní správy: {str(error)}"}), 500

@app.route('/chats/<int:chat_id>/messages', methods=['GET'])
def get_chat_messages(chat_id):
    """Získanie všetkých správ v danom chate
    ---
    parameters:
      - name: chat_id
        in: path
        type: integer
        required: true
        description: ID chatu
    responses:
      200:
        description: Zoznam správ v chate
        schema:
          type: object
          properties:
            messages:
              type: array
              items:
                type: object
                properties:
                  message_id:
                    type: integer
                    example: 1
                  sender_user_id:
                    type: integer
                    example: 2
                  sender_name:
                    type: string
                    example: "Používateľ 2"
                  message_type:
                    type: string
                    example: "text"
                  content:
                    type: string
                    example: "Ahoj!"
                  file_path:
                    type: string
                    example: null
      500:
        description: Chyba pri získavaní správ z chatu
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chyba pri získavaní správ z chatu"
    """
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT m.message_id, m.sender_user_id, u.name as sender_name, 
                           m.message_type, m.content, m.file_name, m.file_mimetype
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
                    "file_name": row[5],
                    "file_mimetype": row[6]
                } for row in rows]

                return jsonify({"messages": messages}), 200

    except Exception as error:
        return jsonify({"message": f"Chyba pri získavaní správ z chatu: {str(error)}"}), 500
@app.route('/messages/<int:message_id>/file', methods=['GET'])
def get_file(message_id):
    """Stiahnutie súboru z konkrétnej správy
    ---
    parameters:
      - name: message_id
        in: path
        type: integer
        required: true
        description: ID správy obsahujúcej súbor
    responses:
      200:
        description: Binárny obsah súboru
        content:
          application/octet-stream:
            schema:
              type: string
              format: binary
      404:
        description: Správa alebo súbor nebol nájdený
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Správa alebo súbor nebol nájdený"
      500:
        description: Chyba pri získavaní správy/súboru
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Chyba pri získavaní správy/súboru"
    """
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT file_data, file_name, file_mimetype
                    FROM messages
                    WHERE message_id = %s AND file_data IS NOT NULL
                """, (message_id,))

                result = cursor.fetchone()
                if not result or not result[0]:
                    return jsonify({"message": "Správa alebo súbor nebol nájdený"}), 404

                file_data, file_name, file_mimetype = result

                response = Response(file_data)
                response.headers.set('Content-Type', file_mimetype or 'application/octet-stream')
                response.headers.set('Content-Disposition', f'attachment; filename="{file_name}"')
                return response

    except Exception as error:
        return jsonify({"message": f"Chyba pri získavaní správy/súboru: {str(error)}"}), 500