import os
import io
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
import pandas as pd
from datetime import datetime
import qrcode
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_key_ceva_enterprise_v4')

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def dict_fetchall(cursor):
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def dict_fetchone(cursor):
    columns = [desc[0] for desc in cursor.description]
    row = cursor.fetchone()
    return dict(zip(columns, row)) if row else None

def log_audit(action, detail, user):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO audit_log (action, detail, user_name) VALUES (%s, %s, %s)", (action, detail, user))
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY,
        tx_type TEXT NOT NULL,
        doc_number TEXT NOT NULL,
        country TEXT NOT NULL,
        po_number INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        base_qty INTEGER NOT NULL,
        lid_qty INTEGER NOT NULL,
        collar_qty INTEGER NOT NULL,
        user_name TEXT DEFAULT 'Unknown',
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cur.execute('''CREATE TABLE IF NOT EXISTS master_countries (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE
    )''')

    cur.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        action TEXT,
        detail TEXT,
        user_name TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cur.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )''')

    cur.execute("SELECT COUNT(*) as c FROM users")
    if cur.fetchone()[0] == 0:
        hashed_pw = generate_password_hash('admin123')
        cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", ('admin', hashed_pw, 'admin'))

    cur.execute("SELECT COUNT(*) as c FROM master_countries")
    if cur.fetchone()[0] == 0:
        for c in ['Japan', 'Thailand', 'China', 'USA']:
            cur.execute("INSERT INTO master_countries (name) VALUES (%s) ON CONFLICT DO NOTHING", (c,))

    conn.commit()
    cur.close()
    conn.close()

def get_stock_data():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN tx_type='IN'  THEN base_qty   ELSE 0 END), 0) AS in_base,
            COALESCE(SUM(CASE WHEN tx_type='OUT' THEN base_qty   ELSE 0 END), 0) AS out_base,
            COALESCE(SUM(CASE WHEN tx_type='IN'  THEN lid_qty    ELSE 0 END), 0) AS in_lid,
            COALESCE(SUM(CASE WHEN tx_type='OUT' THEN lid_qty    ELSE 0 END), 0) AS out_lid,
            COALESCE(SUM(CASE WHEN tx_type='IN'  THEN collar_qty ELSE 0 END), 0) AS in_collar,
            COALESCE(SUM(CASE WHEN tx_type='OUT' THEN collar_qty ELSE 0 END), 0) AS out_collar
        FROM transactions
    """)
    row = dict_fetchone(cur)
    cur.close()
    conn.close()
    row['total_base']   = row['in_base']   - row['out_base']
    row['total_lid']    = row['in_lid']    - row['out_lid']
    row['total_collar'] = row['in_collar'] - row['out_collar']
    return row

# ==========================================
# Login / Logout
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = dict_fetchone(cur)
        cur.close()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            session['role'] = user['role']
            log_audit('LOGIN', 'User logged in', username)
            return redirect(url_for('index'))
        else:
            flash("ชื่อผู้ใช้งาน หรือ รหัสผ่าน ไม่ถูกต้อง!", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    log_audit('LOGOUT', 'User logged out', session.get('username', 'Unknown'))
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# User Management
# ==========================================
@app.route('/users')
def manage_users():
    if 'username' not in session: return redirect(url_for('login'))
    if session.get('role') != 'admin':
        flash("เฉพาะ Admin เท่านั้น!", "error"); return redirect(url_for('index'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, role FROM users ORDER BY role, username")
    users = dict_fetchall(cur)
    cur.close(); conn.close()
    return render_template('users.html', users=users)

@app.route('/add_user', methods=['POST'])
def add_user():
    if session.get('role') != 'admin': return redirect(url_for('index'))
    username = request.form.get('username').strip()
    password = request.form.get('password').strip()
    role = request.form.get('role')
    if username and password:
        try:
            hashed_pw = generate_password_hash(password)
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (username, hashed_pw, role))
            conn.commit(); cur.close(); conn.close()
            log_audit('ADD_USER', f"Created user: {username} ({role})", session['username'])
            flash(f"สร้างบัญชี '{username}' สำเร็จ!", "success")
        except psycopg2.IntegrityError:
            flash(f"ชื่อผู้ใช้ '{username}' มีอยู่ในระบบแล้ว!", "error")
    return redirect(url_for('manage_users'))

@app.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    if session.get('role') != 'admin': return redirect(url_for('index'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = dict_fetchone(cur)
    if user['username'] == session['username']:
        flash("คุณไม่สามารถลบบัญชีที่กำลังใช้งานอยู่ได้!", "error")
    else:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        log_audit('DELETE_USER', f"Deleted user: {user['username']}", session['username'])
        flash(f"ลบบัญชี '{user['username']}' เรียบร้อยแล้ว", "success")
    cur.close(); conn.close()
    return redirect(url_for('manage_users'))

# ==========================================
# Main Pages
# ==========================================
@app.route('/')
def index():
    if 'username' not in session: return redirect(url_for('login'))
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    query = "SELECT * FROM transactions WHERE 1=1"
    params = []
    if start_date: query += " AND DATE(timestamp) >= %s"; params.append(start_date)
    if end_date:   query += " AND DATE(timestamp) <= %s"; params.append(end_date)
    query += " ORDER BY timestamp DESC"
    conn = get_db()
    cur = conn.cursor()
    cur.execute(query, params)
    log_rows = dict_fetchall(cur)
    cur.execute("SELECT name FROM master_countries ORDER BY name")
    countries = dict_fetchall(cur)
    cur.close(); conn.close()
    return render_template('index.html', stock_data=get_stock_data(), log_rows=log_rows,
                           countries=countries, start_date=start_date, end_date=end_date)

@app.route('/dashboard')
def dashboard():
    if 'username' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', stock_data=get_stock_data())

@app.route('/master_data')
def master_data():
    if 'username' not in session: return redirect(url_for('login'))
    if session.get('role') != 'admin':
        flash("เฉพาะ Admin เท่านั้น!", "error"); return redirect(url_for('index'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM master_countries ORDER BY name")
    countries = dict_fetchall(cur)
    cur.close(); conn.close()
    return render_template('master_data.html', countries=countries)

@app.route('/add_country', methods=['POST'])
def add_country():
    if session.get('role') != 'admin': return redirect(url_for('index'))
    country_name = request.form.get('country_name').strip()
    if country_name:
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO master_countries (name) VALUES (%s)", (country_name,))
            conn.commit(); cur.close(); conn.close()
            log_audit('ADD_MASTER', f"Added country: {country_name}", session['username'])
            flash(f"เพิ่ม '{country_name}' ลงในระบบสำเร็จ!", "success")
        except psycopg2.IntegrityError:
            flash(f"ประเทศ '{country_name}' มีอยู่แล้ว", "error")
    return redirect(url_for('master_data'))

@app.route('/delete_country/<int:c_id>')
def delete_country(c_id):
    if session.get('role') != 'admin': return redirect(url_for('index'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name FROM master_countries WHERE id = %s", (c_id,))
    country = dict_fetchone(cur)
    if country:
        cur.execute("DELETE FROM master_countries WHERE id = %s", (c_id,))
        conn.commit()
        log_audit('DELETE_MASTER', f"Deleted country: {country['name']}", session['username'])
        flash(f"ลบ '{country['name']}' ออกจากระบบสำเร็จ!", "success")
    cur.close(); conn.close()
    return redirect(url_for('master_data'))

@app.route('/process_transaction', methods=['POST'])
def process_transaction():
    if 'username' not in session: return redirect(url_for('login'))
    try:
        tx_type    = request.form['tx_type']
        doc_number = request.form['doc_number'].strip().upper()
        country    = request.form['country'].strip()
        po_number  = int(request.form['po_number'])
        quantity   = int(request.form['quantity'])
        user_name  = session['username']
        calc_base    = 1 * quantity
        calc_lid     = 1 * quantity
        calc_collar  = po_number * quantity
        if tx_type == 'OUT':
            current = get_stock_data()
            errors = [k for k, req, cur in [
                ('Base',   calc_base,   current['total_base']),
                ('Lid',    calc_lid,    current['total_lid']),
                ('Collar', calc_collar, current['total_collar'])
            ] if cur < req]
            if errors:
                flash(f"สต็อกไม่พอ: {', '.join(errors)}", "error")
                return redirect(url_for('index'))
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""INSERT INTO transactions
            (tx_type, doc_number, country, po_number, quantity, base_qty, lid_qty, collar_qty, user_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (tx_type, doc_number, country, po_number, quantity, calc_base, calc_lid, calc_collar, user_name))
        conn.commit(); cur.close(); conn.close()
        log_audit('INSERT', f"Added {tx_type} Doc:{doc_number} PO{po_number} Qty:{quantity}", user_name)
        flash(f"บันทึก {'รับเข้า' if tx_type == 'IN' else 'เบิกออก'} สำเร็จ!", "success")
    except Exception as e:
        flash(f"ข้อผิดพลาด: {e}", "error")
    return redirect(url_for('index'))

@app.route('/delete/<int:tx_id>')
def delete_tx(tx_id):
    if session.get('role') != 'admin':
        flash("เฉพาะ Admin เท่านั้น!", "error"); return redirect(url_for('index'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions WHERE id = %s", (tx_id,))
    tx = dict_fetchone(cur)
    cur.execute("DELETE FROM transactions WHERE id = %s", (tx_id,))
    conn.commit(); cur.close(); conn.close()
    log_audit('DELETE', f"Deleted Tx ID:{tx_id} Doc:{tx['doc_number']}", session['username'])
    flash("ลบรายการสำเร็จ!", "success")
    return redirect(url_for('index'))

@app.route('/print_slip/<doc_number>')
def print_slip(doc_number):
    if 'username' not in session: return redirect(url_for('login'))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions WHERE doc_number = %s", (doc_number,))
    items = dict_fetchall(cur)
    cur.close(); conn.close()
    if not items: return "ไม่พบเอกสาร", 404
    return render_template('slip.html', doc_number=doc_number, items=items,
                           date=datetime.now().strftime('%d/%m/%Y %H:%M'), user=session['username'])

@app.route('/qr/<path:text>')
def generate_qr(text):
    img = qrcode.make(text)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/export_excel')
def export_excel():
    if 'username' not in session: return redirect(url_for('login'))
    conn = get_db()
    log_df = pd.read_sql_query("SELECT * FROM transactions ORDER BY timestamp DESC", conn)
    conn.close()
    log_df['tx_type'] = log_df['tx_type'].replace({'IN': 'รับเข้า', 'OUT': 'เบิกออก'})
    log_df.rename(columns={'user_name': 'ผู้ทำรายการ', 'doc_number': 'เอกสาร',
                            'country': 'ประเทศ', 'po_number': 'PO', 'quantity': 'Set'}, inplace=True)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        log_df.to_excel(writer, index=False)
    output.seek(0)
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=f'Report_{datetime.now().strftime("%Y%m%d")}.xlsx')

with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=False)
