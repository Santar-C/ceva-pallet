import os
import io
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from datetime import datetime
import qrcode
import psycopg2
import psycopg2.extras

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ceva_secret_key_2026')
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    # เชื่อมต่อฐานข้อมูล PostgreSQL
    return psycopg2.connect(DATABASE_URL)

def dict_fetchall(cursor):
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def dict_fetchone(cursor):
    columns = [desc[0] for desc in cursor.description]
    row = cursor.fetchone()
    return dict(zip(columns, row)) if row else None

@app.route('/')
def index():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # 1. ดึงข้อมูลสถิติ (KPI) ไปโชว์ที่การ์ดด้านบน
    cur.execute("""
        SELECT 
            COUNT(*) AS total_loans,
            SUM(CASE WHEN tx_type='IN' THEN 1 ELSE 0 END) AS total_in,
            SUM(CASE WHEN tx_type='OUT' THEN 1 ELSE 0 END) AS total_out,
            COUNT(DISTINCT user_name) AS active_users,
            COUNT(DISTINCT country) AS countries_served
        FROM transactions;
    """)
    kpi_data = dict_fetchone(cur)
    
    # 2. ดึงข้อมูลประวัติย้อนหลัง 14 วัน
    cur.execute("""
        SELECT TO_CHAR(timestamp, 'YYYY-MM-DD') AS day, COUNT(*) AS cnt
        FROM transactions WHERE timestamp >= NOW() - INTERVAL '14 days'
        GROUP BY day ORDER BY day;
    """)
    daily = dict_fetchall(cur)
    
    # 3. จัดอันดับคนกดบันทึกข้อมูลสูงสุด 5 อันดับ
    cur.execute("""
        SELECT user_name, COUNT(*) AS cnt FROM transactions GROUP BY user_name ORDER BY cnt DESC LIMIT 5;
    """)
    top_users = dict_fetchall(cur)
    
    # 4. ดึงยอดสต็อกคงเหลือปัจจุบัน (คำนวณจาก IN ลบด้วย OUT)
    cur.execute("""
        SELECT 
            country AS variety_name,
            SUM(CASE WHEN tx_type = 'IN' THEN base_qty ELSE -base_qty END) as available_base,
            SUM(CASE WHEN tx_type = 'IN' THEN lid_qty ELSE -lid_qty END) as available_lid,
            SUM(CASE WHEN tx_type = 'IN' THEN collar_qty ELSE -collar_qty END) as available_collar
        FROM transactions GROUP BY country ORDER BY country;
    """)
    stock_data = dict_fetchall(cur)
    
    # 5. ดึงรายการบันทึกประวัติทั้งหมดมาโชว์ในตาราง Logs
    cur.execute("SELECT * FROM transactions ORDER BY timestamp DESC;")
    log_rows = dict_fetchall(cur)
    
    cur.close()
    conn.close()
    
    # ส่งข้อมูลทั้งหมดไปที่หน้ากาก HTML ชื่อ app.html
    return render_template('app.html', kpi=kpi_data, daily=daily, top_users=top_users, stock=stock_data, log_rows=log_rows)

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    # ลอจิกการรับเข้า/เบิกจ่ายสินค้า
    tx_type = request.form.get('tx_type')
    doc_number = request.form.get('doc_number')
    country = request.form.get('country')
    quantity = int(request.form.get('quantity', 1))
    
    if tx_type == 'IN':
        po_number = int(request.form.get('po_number', 0))
        base_qty = quantity
        lid_qty = quantity
        collar_qty = po_number * quantity
    else:
        base_qty = int(request.form.get('base_qty', 0))
        lid_qty = int(request.form.get('lid_qty', 0))
        collar_qty = int(request.form.get('collar_qty', 0))
        po_number = 0

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO transactions (tx_type, doc_number, country, po_number, quantity, base_qty, lid_qty, collar_qty, user_name, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW());
        """, (tx_type, doc_number, country, po_number, quantity, base_qty, lid_qty, collar_qty, 'CEVA Operator'))
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))

@app.route('/generate_qr/<doc_number>')
def generate_qr(doc_number):
    qr = qrcode.make(f"DOC-REF: {doc_number}")
    img_io = io.BytesIO()
    qr.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
