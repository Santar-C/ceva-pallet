# 🏭 CEVA Pallet Stock Management System

ระบบจัดการสต็อกพาเลท Base / Lid / Collar พร้อมระบบ Login, Dashboard, และพิมพ์ QR Code

---

## 📁 โครงสร้างไฟล์

```
pallet-app/
├── app.py                  ← โค้ดหลัก Flask
├── requirements.txt        ← library ที่ใช้
├── render.yaml             ← config สำหรับ Render.com
├── .gitignore              ← ไฟล์ที่ซ่อนจาก GitHub
├── README.md               ← ไฟล์นี้
└── templates/
    ├── login.html
    ├── index.html
    ├── dashboard.html
    ├── master_data.html
    ├── users.html
    └── slip.html
└── static/
    └── logo.png
```

---

## 🚀 วิธี Deploy บน Render.com (ฟรี ข้อมูลไม่หาย)

### ขั้นตอนที่ 1 — เตรียม GitHub

```bash
# 1. สร้างโฟลเดอร์โปรเจคและย้ายไฟล์ทั้งหมดเข้ามา
# 2. เปิด Terminal / Command Prompt ที่โฟลเดอร์นั้น

git init
git add .
git commit -m "first commit: CEVA pallet system"

# 3. ไปสร้าง repository ใหม่บน github.com (ตั้งชื่อ เช่น ceva-pallet)
# 4. แล้ว copy คำสั่งจาก GitHub มาวาง เช่น:
git remote add origin https://github.com/YOUR_USERNAME/ceva-pallet.git
git push -u origin main
```

> ✅ ตรวจสอบว่าไม่มีไฟล์ `.db` ขึ้น GitHub (ดูที่ .gitignore)

---

### ขั้นตอนที่ 2 — สร้าง Database บน Render

1. ไปที่ **https://render.com** → สมัครฟรี (ใช้ Google ได้)
2. คลิก **New +** → เลือก **PostgreSQL**
3. ตั้งค่าดังนี้:

| ช่อง | ค่า |
|------|-----|
| Name | `ceva-pallet-db` |
| Database | `pallet_stock` |
| User | `ceva_admin` |
| Region | Singapore (ใกล้ที่สุด) |
| Plan | **Free** |

4. คลิก **Create Database**
5. รอสักครู่ แล้ว **copy "Internal Database URL"** เก็บไว้

> ⚠️ **สำคัญมาก**: Database ฟรีของ Render **ไม่หมดอายุ** และข้อมูลอยู่ถาวรตลอดไป

---

### ขั้นตอนที่ 3 — Deploy Web App

1. คลิก **New +** → เลือก **Web Service**
2. เลือก **Connect a repository** → เลือก repo ที่ push ไป
3. ตั้งค่าดังนี้:

| ช่อง | ค่า |
|------|-----|
| Name | `ceva-pallet` |
| Region | Singapore |
| Branch | `main` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |
| Plan | **Free** |

4. เลื่อนลงมาที่ **Environment Variables** → คลิก **Add Environment Variable**

| Key | Value |
|-----|-------|
| `DATABASE_URL` | วาง Internal Database URL ที่ copy ไว้ในขั้นตอนที่ 2 |
| `SECRET_KEY` | พิมพ์ข้อความสุ่มอะไรก็ได้ เช่น `ceva-secret-2024-xyz` |

5. คลิก **Create Web Service**
6. รอ Build เสร็จ (~3-5 นาที) → ได้ URL เช่น `https://ceva-pallet.onrender.com`

---

### ขั้นตอนที่ 4 — เข้าใช้งาน

เปิด URL ที่ได้จาก Render แล้ว login ด้วย:

- **Username**: `admin`
- **Password**: `admin123`

> 🔒 **เปลี่ยนรหัสผ่านทันที** หลังเข้าครั้งแรก โดยลบ user admin แล้วสร้างใหม่ที่หน้า "จัดการผู้ใช้งาน"

---

## 🔄 วิธีอัปเดตโค้ด (ครั้งต่อไป)

เมื่อแก้ไขโค้ดแล้วต้องการอัปเดต ทำแค่นี้:

```bash
git add .
git commit -m "update: อธิบายสิ่งที่เปลี่ยน"
git push
```

Render จะ deploy ให้อัตโนมัติทันที ข้อมูลใน Database ไม่หายเลย

---

## 🛡️ ความปลอดภัยของข้อมูล

| สิ่งที่เกิดขึ้น | ผลกับข้อมูล |
|----------------|-------------|
| แก้โค้ด + push GitHub | ✅ ข้อมูลอยู่ครบ |
| Web Service restart | ✅ ข้อมูลอยู่ครบ |
| Web Service sleep (ฟรี) | ✅ ข้อมูลอยู่ครบ |
| ลบ Web Service | ✅ ข้อมูลอยู่ครบ (อยู่ใน DB) |
| ลบ PostgreSQL Database | ❌ ข้อมูลหายถาวร — ห้ามทำ! |

> ✅ PostgreSQL Database เป็นคนละส่วนกับ Web Service ข้อมูลจึงปลอดภัยเสมอ

---

## 💾 วิธี Backup ข้อมูล (แนะนำทำสัปดาห์ละครั้ง)

เปิดโปรแกรม แล้วคลิกปุ่ม **Export Excel** ที่หน้าประวัติรายการ ไฟล์จะดาวน์โหลดมาเก็บไว้ที่เครื่องคุณ

---

## ⚡ ข้อจำกัดของ Render ฟรี

- Web App **หยุดทำงาน** หลังไม่มีคนใช้ 15 นาที
- เปิดครั้งแรกของวันอาจรอ **20-30 วินาที** (กำลัง wake up)
- ข้อมูลใน Database **ไม่ได้รับผลกระทบ** จากการ sleep เลย

---

## 🆘 ปัญหาที่พบบ่อย

**Q: เปิดแล้วหน้าจอขาว หรือ Error 500**
A: ไปที่ Render Dashboard → คลิกที่ service → ดู Logs ว่า error อะไร มักเกิดจาก DATABASE_URL ไม่ถูกต้อง

**Q: Login ไม่ได้ / ลืมรหัสผ่าน**
A: ไปที่ Render Dashboard → Shell → พิมพ์ `python` แล้วรัน:
```python
from app import *
conn = get_db()
cur = conn.cursor()
cur.execute("UPDATE users SET password=%s WHERE username='admin'", (generate_password_hash('newpassword'),))
conn.commit()
```

**Q: Web app ช้า ครั้งแรก**
A: ปกติครับ Render ฟรีจะ sleep — รอ 30 วินาทีแล้วจะเร็วปกติ

---

## 📞 ข้อมูลระบบ

- **Framework**: Flask (Python)
- **Database**: PostgreSQL (Render Free Tier)
- **Hosting**: Render.com (Free Tier)
- **ค่าใช้จ่าย**: ฟรีทั้งหมด ตลอดไป
