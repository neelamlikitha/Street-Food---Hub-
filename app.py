from flask import Flask, render_template, request, redirect, url_for, session
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secret_key_here'

# In-memory storage for demo purposes
messages = []
users = []  # For demo only; in real apps, use a database

class Message:
    def __init__(self, sender, receiver, content, timestamp=None):
        self.sender = sender
        self.receiver = receiver
        self.content = content
        self.timestamp = timestamp or datetime.now()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form.get('role')
        username = request.form.get('username')
        password = request.form.get('password')

        # Simple check to avoid duplicate usernames (for demo)
        if any(user['username'] == username for user in users):
            return "Username already exists. Try another one."

        users.append({'role': role, 'username': username, 'password': password})
        session['role'] = role
        session['username'] = username
        return redirect(url_for('chat'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        role = request.form.get('role')
        # Password check skipped (insecure, for demo only)

        session['role'] = role
        session['username'] = username
        return redirect(url_for('chat'))

    return render_template('login.html')

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        sender = session['username']
        receiver = request.form.get('receiver')
        content = request.form.get('message')
        new_msg = Message(sender, receiver, content)
        messages.append(new_msg)
        return redirect(url_for('chat'))

    return render_template('chat.html', messages=messages, username=session['username'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)