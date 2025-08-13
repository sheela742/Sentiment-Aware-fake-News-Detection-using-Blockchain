from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import pickle
from datetime import datetime
from blockchain import Blockchain
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['DATABASE'] = 'database.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Initialize blockchain
blockchain = Blockchain()

# Load ML models
with open('ml_models/sentiment_model.pkl', 'rb') as f:
    sentiment_model, sentiment_vectorizer = pickle.load(f)

with open('ml_models/fake_news_model.pkl', 'rb') as f:
    fake_news_model, fake_news_vectorizer = pickle.load(f)

# Database connection
def get_db():
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    return db

# Initialize database
def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                reporter_id INTEGER NOT NULL,
                sentiment TEXT,
                is_fake BOOLEAN,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                blockchain_hash TEXT,
                FOREIGN KEY (reporter_id) REFERENCES users (id)
            )
        ''')
        db.commit()

# Helper functions
def analyze_sentiment(text):
    processed_text = text.lower()
    vectorized = sentiment_vectorizer.transform([processed_text])
    prediction = sentiment_model.predict(vectorized)[0]
    
    # Handle different prediction formats
    if isinstance(prediction, str):
        return prediction.lower()
    elif isinstance(prediction, (int, float)):
        return 'positive' if prediction == 1 else 'negative'
    else:
        # Default to negative if uncertain
        return 'negative'

def detect_fake_news(text):
    processed_text = text.lower()
    vectorized = fake_news_vectorizer.transform([processed_text])
    prediction = fake_news_model.predict(vectorized)[0]
    return prediction == 'fake'

def add_to_blockchain(news_id, title, content):
    data = f"{news_id}:{title}:{content}"
    return blockchain.add_block(data)

# Routes
@app.route('/')
def index():
    db = get_db()
    news = db.execute('''
        SELECT news.*, users.username 
        FROM news 
        JOIN users ON news.reporter_id = users.id 
        WHERE status = 'approved'
        ORDER BY created_at DESC
        LIMIT 10
    ''').fetchall()
    return render_template('index.html', news=news)

@app.route('/news/<int:news_id>')
def news_detail(news_id):
    db = get_db()
    article = db.execute('''
        SELECT news.*, users.username 
        FROM news 
        JOIN users ON news.reporter_id = users.id 
        WHERE news.id = ?
    ''', (news_id,)).fetchone()
    
    # Verify blockchain
    is_verified = False
    if article['blockchain_hash']:
        block = blockchain.get_block_by_hash(article['blockchain_hash'])
        if block:
            stored_data = f"{article['id']}:{article['title']}:{article['content']}"
            is_verified = (block.data == stored_data)
    
    return render_template('news_detail.html', article=article, is_verified=is_verified)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        db = get_db()
        try:
            db.execute(
                'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                (username, generate_password_hash(password), role)
            )
            db.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.', 'danger')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        user = db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Login successful!', 'success')
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'reporter':
                return redirect(url_for('reporter_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    db = get_db()
    pending_news = db.execute('''
        SELECT news.*, users.username 
        FROM news 
        JOIN users ON news.reporter_id = users.id 
        WHERE status = 'pending'
        ORDER BY created_at DESC
    ''').fetchall()
    
    return render_template('admin.html', pending_news=pending_news)

@app.route('/admin/approve/<int:news_id>')
def approve_news(news_id):
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    db = get_db()
    news = db.execute('SELECT * FROM news WHERE id = ?', (news_id,)).fetchone()
    
    if news:
        # Only add to blockchain if not fake or if admin explicitly approves fake news
        block_hash = add_to_blockchain(news['id'], news['title'], news['content'])
        
        db.execute(
            'UPDATE news SET status = "approved", blockchain_hash = ?, is_fake = 0 WHERE id = ?',
            (block_hash, news_id)
        )
        db.commit()
        flash('News approved and added to blockchain!', 'success')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject/<int:news_id>')
def reject_news(news_id):
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    db = get_db()
    db.execute('UPDATE news SET status = "rejected" WHERE id = ?', (news_id,))
    db.commit()
    flash('News rejected.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/reporter/dashboard')
def reporter_dashboard():
    if 'user_id' not in session or session['role'] != 'reporter':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    db = get_db()
    my_news = db.execute('''
        SELECT * FROM news 
        WHERE reporter_id = ?
        ORDER BY created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    return render_template('reporter.html', news=my_news)
@app.route('/reporter/submit', methods=['GET', 'POST'])
def submit_news():
    if 'user_id' not in session or session['role'] != 'reporter':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        # Analyze with ML models
        sentiment = analyze_sentiment(content)
        is_fake = detect_fake_news(content)
        
        # Always set status to pending if news is fake, regardless of sentiment
        status = 'pending' if is_fake else ('auto_approved' if sentiment == 'positive' else 'pending')
        
        db = get_db()
        db.execute(
            'INSERT INTO news (title, content, reporter_id, sentiment, is_fake, status) VALUES (?, ?, ?, ?, ?, ?)',
            (title, content, session['user_id'], sentiment, is_fake, status)
        )
        db.commit()
        
        if status == 'auto_approved':
            news_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
            block_hash = add_to_blockchain(news_id, title, content)
            db.execute(
                'UPDATE news SET status = "approved", blockchain_hash = ? WHERE id = ?',
                (block_hash, news_id)
            )
            db.commit()
            flash('News automatically approved and added to blockchain!', 'success')
        else:
            if is_fake:
                flash('Potential fake news detected - submitted for admin review.', 'warning')
            else:
                flash('News submitted for admin review.', 'info')
        
        return redirect(url_for('reporter_dashboard'))
    
    return render_template('submit_news.html')
@app.route('/blockchain')
def view_blockchain():
    if 'user_id' not in session or session['role'] != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))
    
    blockchain_data = []
    for block in blockchain.chain:
        blockchain_data.append({
            'index': block.index,
            'timestamp': datetime.fromtimestamp(block.timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            'data': block.data,
            'previous_hash': block.previous_hash,
            'hash': block.hash
        })
    
    # Pass both the blockchain object and the data list
    return render_template('blockchain.html', 
                         blockchain=blockchain_data,
                         blockchain_obj=blockchain)  # Add this line
if __name__ == '__main__':
    init_db()
    app.run(debug=True)