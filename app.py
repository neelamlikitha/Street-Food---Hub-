import os
from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

secret_key = os.environ.get('SECRET_KEY')
mongo_uri = os.environ.get('MONGO_URI')

if not secret_key or len(secret_key) < 32:
    raise RuntimeError('SECRET_KEY must be set to a random value of at least 32 characters.')
if not mongo_uri or 'YOUR_NEW_PASSWORD' in mongo_uri:
    raise RuntimeError('MONGO_URI must be set to a valid MongoDB connection URI.')

app = Flask(__name__)
app.secret_key = secret_key

try:
    mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000, tz_aware=True)
    database = mongo_client['street_food_hub']
    users_collection = database['users']
    messages_collection = database['messages']
    mongo_client.admin.command('ping')
    users_collection.create_index([('username_normalized', ASCENDING)], unique=True)
    messages_collection.create_index([('sender_username', ASCENDING), ('created_at', ASCENDING)])
    messages_collection.create_index([('receiver_username', ASCENDING), ('created_at', ASCENDING)])
except PyMongoError as error:
    app.logger.error('MongoDB initialization failed (%s).', type(error).__name__)
    raise RuntimeError('Unable to connect to or initialize MongoDB.') from None


def normalize_username(username):
    return username.strip().casefold()

class Message:
    def __init__(self, sender, receiver, content, timestamp=None):
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.timestamp = timestamp or datetime.now(timezone.utc)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form.get('role', '').strip()
        username = request.form.get('username', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not username or not password or not role or not name or not email:
            return "Name, email, username, password, and role are required.", 400
        if role not in {'vendor', 'supplier'}:
            return "Please select a valid role.", 400

        user = {
            'role': role,
            'username': username,
            'username_normalized': normalize_username(username),
            'name': name,
            'email': email,
            'password_hash': generate_password_hash(password),
            'created_at': datetime.now(timezone.utc)
        }
        try:
            result = users_collection.insert_one(user)
        except DuplicateKeyError:
            return "Username already exists. Try another one.", 409
        except PyMongoError as error:
            app.logger.error('Database error during registration (%s).', type(error).__name__)
            return "The service is temporarily unavailable. Please try again later.", 503

        session['user_id'] = str(result.inserted_id)
        session['role'] = role
        session['username'] = username
        return redirect(url_for('chat'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return "Username and password are required.", 400

        try:
            user = users_collection.find_one({'username_normalized': normalize_username(username)})
        except PyMongoError as error:
            app.logger.error('Database error during login (%s).', type(error).__name__)
            return "The service is temporarily unavailable. Please try again later.", 503

        if user is None or not check_password_hash(user['password_hash'], password):
            return "Invalid username or password."

        session['user_id'] = str(user['_id'])
        session['role'] = user['role']
        session['username'] = user['username']
        return redirect(url_for('chat'))

    return render_template('login.html')

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    normalized_username = normalize_username(username)

    if request.method == 'POST':
        receiver = request.form.get('receiver', '').strip()
        content = request.form.get('message', '').strip()
        if not receiver or not content:
            return "Recipient and message are required.", 400

        try:
            messages_collection.insert_one({
                'sender_username': normalized_username,
                'receiver_username': normalize_username(receiver),
                'sender': username,
                'receiver': receiver,
                'content': content,
                'created_at': datetime.now(timezone.utc)
            })
        except PyMongoError as error:
            app.logger.error('Database error while sending a message (%s).', type(error).__name__)
            return "The service is temporarily unavailable. Please try again later.", 503

        return redirect(url_for('chat'))

    try:
        message_documents = list(messages_collection.find({
            '$or': [
                {'sender_username': normalized_username},
                {'receiver_username': normalized_username}
            ]
        }).sort('created_at', ASCENDING))
    except PyMongoError as error:
        app.logger.error('Database error while retrieving messages (%s).', type(error).__name__)
        return "The service is temporarily unavailable. Please try again later.", 503

    messages = [
        Message(
            document['sender'],
            document['receiver'],
            document['content'],
            document['created_at']
        )
        for document in message_documents
    ]
    return render_template('chat.html', messages=messages, username=username)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=False)