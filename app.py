import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template_string, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super_tajny_kluczyk_systemu_pos")
print(os.getcwd())

# Konfiguracja Połączenia z Bazą Danych (Supabase / PostgreSQL lub fallback do SQLite)
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    if DATABASE_URL:
        # Połączenie z Supabase (PostgreSQL)
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        # Połączenie lokalne (SQLite)
        conn = sqlite3.connect("sklep.db")
        conn.row_factory = sqlite3.Row
        return conn

def execute_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = get_db_connection()
    is_postgres = DATABASE_URL is not None
    
    # Zamiana składni SQL ze stylu SQLite (?) na Postgres (%s)
    if is_postgres:
        query = query.replace("?", "%s")

    cursor = conn.cursor()
    cursor.execute(query, params)
    
    result = None
    if fetchone:
        result = cursor.fetchone()
    elif fetchall:
        result = cursor.fetchall()
        
    if commit or not is_postgres:
        conn.commit()
        
    cursor.close()
    conn.close()
    return result

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    is_postgres = DATABASE_URL is not None

    auto_inc = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    dt_default = "CURRENT_TIMESTAMP"

    # Tabela produktów
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS produkty (
            id {auto_inc},
            nazwa TEXT NOT NULL,
            kod_kreskowy TEXT UNIQUE NOT NULL,
            cena REAL NOT NULL,
            kategoria TEXT NOT NULL
        )
    """)

    # Tabela transakcji
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS transakcje (
            id {auto_inc},
            data_czas TIMESTAMP DEFAULT {dt_default},
            suma REAL NOT NULL,
            metoda_platnosci TEXT NOT NULL,
            wplacono REAL DEFAULT 0,
            reszta REAL DEFAULT 0
        )
    """)

    # Tabela pozycji transakcji
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS transakcje_pozycje (
            id {auto_inc},
            transakcja_id INTEGER NOT NULL,
            nazwa_produktu TEXT NOT NULL,
            cena_jednostkowa REAL NOT NULL,
            ilosc INTEGER NOT NULL,
            wartosc REAL NOT NULL,
            FOREIGN KEY (transakcja_id) REFERENCES transakcje(id)
        )
    """)

    # Tabela ustawień (przechowywanie hasła admina)
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS ustawienia (
            klucz TEXT PRIMARY KEY,
            wartosc TEXT NOT NULL
        )
    """)

    # Inicjalizacja domyślnego hasła admina (Poprawione zapytanie)
    sql_check_pass = "SELECT wartosc FROM ustawienia WHERE klucz = %s" if is_postgres else "SELECT wartosc FROM ustawienia WHERE klucz = ?"
    cursor.execute(sql_check_pass, ('admin_password',))
    
    if not cursor.fetchone():
        sql_insert_pass = "INSERT INTO ustawienia (klucz, wartosc) VALUES (%s, %s)" if is_postgres else "INSERT INTO ustawienia (klucz, wartosc) VALUES (?, ?)"
        cursor.execute(sql_insert_pass, ('admin_password', '13990'))

    # Przykładowe dane początkowe
    cursor.execute("SELECT COUNT(*) FROM produkty")
    count = cursor.fetchone()
    total_prod = count['count'] if is_postgres else count[0]

    if total_prod == 0:
        przykładowe_produkty = [
            ("Mleko 3.2%", "5901234567890", 3.99, "Nabiał"),
            ("Chleb Wiejski", "5909876543210", 4.50, "Pieczywo"),
            ("Woda Mineralna 1.5L", "5905555444333", 2.20, "Napoje"),
            ("Kawa Mielona 500g", "5901111222333", 24.99, "Artykuły spożywcze"),
            ("Czekolada Mleczna", "5907777888999", 5.49, "Słodycze")
        ]
        sql_insert_prod = "INSERT INTO produkty (nazwa, kod_kreskowy, cena, kategoria) VALUES (%s, %s, %s, %s)" if is_postgres else "INSERT INTO produkty (nazwa, kod_kreskowy, cena, kategoria) VALUES (?, ?, ?, ?)"
        for p in przykładowe_produkty:
            cursor.execute(sql_insert_prod, p)

    conn.commit()
    cursor.close()
    conn.close()

init_db()

def get_admin_password():
    res = execute_query("SELECT wartosc FROM ustawienia WHERE klucz = ?", ('admin_password',), fetchone=True)
    return res['wartosc'] if res else "13990"

# Main HTML Layout Template
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System POS - Sklep Monopolowo-Spożywczy</title>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { margin: 0; padding: 0; background-color: #f4f6f9; color: #333; }
        header { background-color: #2c3e50; color: white; padding: 15px 30px; display: flex; justify-content: space-between; align-items: center; }
        header h1 { margin: 0; font-size: 1.5em; }
        nav a { color: white; text-decoration: none; margin-left: 15px; padding: 8px 12px; border-radius: 4px; background: rgba(255,255,255,0.1); }
        nav a:hover { background: rgba(255,255,255,0.2); }
        .container { padding: 30px; max-width: 1200px; margin: 0 auto; }
        .btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; font-size: 0.9em; font-weight: bold; }
        .btn-green { background-color: #2ecc71; color: white; }
        .btn-blue { background-color: #3498db; color: white; }
        .btn-red { background-color: #e74c3c; color: white; }
        .btn-gray { background-color: #95a5a6; color: white; }
        .alert { padding: 12px; margin-bottom: 20px; border-radius: 4px; }
        .alert-error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .alert-success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 20px; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f8f9fa; }
        input[type="text"], input[type="number"], input[type="password"] { padding: 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 1em; }
    </style>
</head>
<body>
    <header>
        <h1>🛒 Kasa Fiskalna / POS</h1>
        <nav>
            <a href="/">🛒 Kasa</a>
            {% if session.get('admin') %}
                <a href="/admin">⚙️ Panel Admina</a>
                <a href="/admin/transakcje">📜 Transakcje</a>
                <a href="/admin/zmien-haslo">🔑 Zmień Hasło</a>
                <a href="/admin/logout">🚪 Wyloguj</a>
            {% else %}
                <a href="/admin/login">🔒 Logowanie Admin</a>
            {% endif %}
        </nav>
    </header>
    <div class="container">
        {{ content|safe }}
    </div>
</body>
</html>
"""

# ----------------------------------------------------
# KASA / OBSŁUGA KOSZYKA
# ----------------------------------------------------
@app.route("/")
def home():
    if "koszyk" not in session:
        session["koszyk"] = []

    koszyk = session["koszyk"]
    suma = sum(item["cena"] * item["ilosc"] for item in koszyk)

    produkty = execute_query("SELECT * FROM produkty ORDER BY nazwa ASC", fetchall=True)

    pozycje_html = ""
    for i, item in enumerate(koszyk):
        pozycje_html += f"""
        <tr>
            <td>{item['nazwa']}</td>
            <td>{item['cena']:.2f} zł</td>
            <td>{item['ilosc']}</td>
            <td>{item['cena'] * item['ilosc']:.2f} zł</td>
            <td><a href="/usun_z_koszyka/{i}" class="btn btn-red">❌ Usunąć</a></td>
        </tr>
        """

    produkty_options = ""
    if produkty:
        for p in produkty:
            produkty_options += f'<option value="{p["kod_kreskowy"]}">{p["nazwa"]} - {p["cena"]:.2f} zł (Kod: {p["kod_kreskowy"]})</option>'

    formularz_platnosci = ""
    if koszyk:
        formularz_platnosci = """
        <form action="/platnosc" method="POST" style="display: flex; flex-direction: column; gap: 15px; margin-top: 20px;">
            <label>
                <b>Metoda Płatności:</b><br>
                <select name="metoda" style="width: 100%; padding: 10px; margin-top: 5px; border-radius: 4px; border: 1px solid #ccc;">
                    <option value="Karta">💳 Karta Płatnicza</option>
                    <option value="Gotówka">💵 Gotówka</option>
                    <option value="BLIK">📱 BLIK</option>
                </select>
            </label>
            <label>
                <b>Wpłacono (dla gotówki):</b><br>
                <input type="number" step="0.01" name="wplacono" placeholder="0.00" style="width: 100%; margin-top: 5px;">
            </label>
            <button type="submit" class="btn btn-green" style="padding: 15px; font-size: 1.1em;">✅ Zrealizuj Płatność</button>
        </form>
        """

    content = f"""
        <div style="display: flex; gap: 30px;">
            <div style="flex: 2;">
                <h2>🛒 Koszyk Transakcji</h2>
                <form action="/dodaj_do_koszyka" method="POST" style="margin-bottom: 20px; display: flex; gap: 10px;">
                    <input type="text" name="kod_kreskowy" placeholder="Skanuj lub wpisz kod..." style="flex: 1;" autofocus required>
                    <button type="submit" class="btn btn-blue">➕ Dodaj</button>
                </form>

                <form action="/dodaj_do_koszyka" method="POST" style="margin-bottom: 20px; display: flex; gap: 10px;">
                    <select name="kod_kreskowy" style="flex: 1; padding: 10px; border-radius: 4px; border: 1px solid #ccc;">
                        <option value="">-- Wybierz produkt z listy --</option>
                        {produkty_options}
                    </select>
                    <button type="submit" class="btn btn-blue">➕ Dodaj wybrane</button>
                </form>

                <table>
                    <thead>
                        <tr>
                            <th>Produkt</th>
                            <th>Cena</th>
                            <th>Ilość</th>
                            <th>Wartość</th>
                            <th>Akcja</th>
                        </tr>
                    </thead>
                    <tbody>
                        {pozycje_html if koszyk else '<tr><td colspan="5" style="text-align:center;">Koszyk jest pusty.</td></tr>'}
                    </tbody>
                </table>
                {f'<a href="/czysc_koszyk" class="btn btn-gray">🗑️ Wyczyść koszyk</a>' if koszyk else ''}
            </div>

            <div style="flex: 1; background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); height: fit-content;">
                <h2 style="margin-top:0;">Podsumowanie</h2>
                <h1 style="color: #2ecc71; font-size: 2.5em; margin: 10px 0;">{suma:.2f} PLN</h1>
                
                {formularz_platnosci}
            </div>
        </div>
    """
    return render_template_string(HTML_LAYOUT, content=content)

@app.route("/dodaj_do_koszyka", methods=["POST"])
def dodaj_do_koszyka():
    kod = request.form.get("kod_kreskowy", "").strip()
    if not kod:
        return redirect(url_for("home"))

    prod = execute_query("SELECT * FROM produkty WHERE kod_kreskowy = ?", (kod,), fetchone=True)

    if prod:
        koszyk = session.get("koszyk", [])
        znaleziono = False
        for item in koszyk:
            if item["kod_kreskowy"] == kod:
                item["ilosc"] += 1
                znaleziono = True
                break
        if not znaleziono:
            koszyk.append({
                "kod_kreskowy": prod["kod_kreskowy"],
                "nazwa": prod["nazwa"],
                "cena": float(prod["cena"]),
                "ilosc": 1
            })
        session["koszyk"] = koszyk
    return redirect(url_for("home"))

@app.route("/usun_z_koszyka/<int:index>")
def usun_z_koszyka(index):
    koszyk = session.get("koszyk", [])
    if 0 <= index < len(koszyk):
        koszyk.pop(index)
        session["koszyk"] = koszyk
    return redirect(url_for("home"))

@app.route("/czysc_koszyk")
def czysc_koszyk():
    session["koszyk"] = []
    return redirect(url_for("home"))

@app.route("/platnosc", methods=["POST"])
def platnosc():
    koszyk = session.get("koszyk", [])
    if not koszyk:
        return redirect(url_for("home"))

    metoda = request.form.get("metoda", "Karta")
    wplacono_raw = request.form.get("wplacono", "0").replace(",", ".")
    wplacono = float(wplacono_raw) if wplacono_raw else 0.0

    suma = sum(item["cena"] * item["ilosc"] for item in koszyk)
    reszta = wplacono - suma if metoda == "Gotówka" and wplacono >= suma else 0.0

    conn = get_db_connection()
    is_postgres = DATABASE_URL is not None
    cursor = conn.cursor()

    sql_trans = "INSERT INTO transakcje (suma, metoda_platnosci, wplacono, reszta) VALUES (%s, %s, %s, %s) RETURNING id" if is_postgres else "INSERT INTO transakcje (suma, metoda_platnosci, wplacono, reszta) VALUES (?, ?, ?, ?)"
    
    if is_postgres:
        cursor.execute(sql_trans, (suma, metoda, wplacono, reszta))
        transakcja_id = cursor.fetchone()['id']
    else:
        cursor.execute(sql_trans, (suma, metoda, wplacono, reszta))
        transakcja_id = cursor.lastrowid

    sql_item = "INSERT INTO transakcje_pozycje (transakcja_id, nazwa_produktu, cena_jednostkowa, ilosc, wartosc) VALUES (%s, %s, %s, %s, %s)" if is_postgres else "INSERT INTO transakcje_pozycje (transakcja_id, nazwa_produktu, cena_jednostkowa, ilosc, wartosc) VALUES (?, ?, ?, ?, ?)"

    for item in koszyk:
        wartosc = item["cena"] * item["ilosc"]
        cursor.execute(sql_item, (transakcja_id, item["nazwa"], item["cena"], item["ilosc"], wartosc))

    conn.commit()
    cursor.close()
    conn.close()

    session["ostatnia_transakcja"] = {"id": transakcja_id}
    session["koszyk"] = []

    return redirect(url_for("platnosc_sukces"))

# ----------------------------------------------------
# PANEL ADMINISTRATORA & ZMIANA HASŁA
# ----------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = ""
    if request.method == "POST":
        haslo = request.form.get("haslo")
        if haslo == get_admin_password():
            session["admin"] = True
            return redirect(url_for("admin_panel"))
        else:
            error = "❌ Nieprawidłowe hasło!"

    content = f"""
        <div style="max-width: 400px; margin: 50px auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h2>🔒 Logowanie Admina</h2>
            {f'<div class="alert alert-error">{error}</div>' if error else ''}
            <form method="POST">
                <div style="margin-bottom: 15px;">
                    <label><b>Hasło:</b></label><br>
                    <input type="password" name="haslo" style="width: 100%; margin-top: 5px;" required>
                </div>
                <button type="submit" class="btn btn-blue" style="width: 100%;">Zaloguj się</button>
            </form>
        </div>
    """
    return render_template_string(HTML_LAYOUT, content=content)

@app.route("/admin/zmien-haslo", methods=["GET", "POST"])
def admin_zmien_haslo():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    error = ""
    success = ""
    if request.method == "POST":
        stare_haslo = request.form.get("stare_haslo")
        nowe_haslo = request.form.get("nowe_haslo")
        powtorz_haslo = request.form.get("powtorz_haslo")

        if stare_haslo != get_admin_password():
            error = "❌ Stare hasło jest nieprawidłowe!"
        elif nowe_haslo != powtorz_haslo:
            error = "❌ Nowe hasła nie są identyczne!"
        elif len(nowe_haslo) < 3:
            error = "❌ Hasło jest za krótkie!"
        else:
            execute_query("UPDATE ustawienia SET wartosc = ? WHERE klucz = 'admin_password'", (nowe_haslo,), commit=True)
            success = "✅ Hasło zostało zmienione pomyślnie!"

    content = f"""
        <div style="max-width: 450px; margin: 30px auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            <h2>🔑 Zmiana Hasła Administratora</h2>
            {f'<div class="alert alert-error">{error}</div>' if error else ''}
            {f'<div class="alert alert-success">{success}</div>' if success else ''}
            <form method="POST">
                <div style="margin-bottom: 15px;">
                    <label><b>Obecne hasło:</b></label><br>
                    <input type="password" name="stare_haslo" style="width: 100%; margin-top: 5px;" required>
                </div>
                <div style="margin-bottom: 15px;">
                    <label><b>Nowe hasło:</b></label><br>
                    <input type="password" name="nowe_haslo" style="width: 100%; margin-top: 5px;" required>
                </div>
                <div style="margin-bottom: 20px;">
                    <label><b>Powtórz nowe hasło:</b></label><br>
                    <input type="password" name="powtorz_haslo" style="width: 100%; margin-top: 5px;" required>
                </div>
                <button type="submit" class="btn btn-green" style="width: 100%;">Zapisz Nowe Hasło</button>
            </form>
        </div>
    """
    return render_template_string(HTML_LAYOUT, content=content)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("home"))

@app.route("/admin")
def admin_panel():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    produkty = execute_query("SELECT * FROM produkty ORDER BY id ASC", fetchall=True)

    rows_html = ""
    if produkty:
        for p in produkty:
            rows_html += f"""
            <tr>
                <td>{p['id']}</td>
                <td>{p['nazwa']}</td>
                <td><code>{p['kod_kreskowy']}</code></td>
                <td>{p['cena']:.2f} zł</td>
                <td>{p['kategoria']}</td>
                <td>
                    <a href="/admin/edytuj/{p['id']}" class="btn btn-blue">✏️ Edytuj</a>
                    <a href="/admin/usun/{p['id']}" class="btn btn-red" onclick="return confirm('Czy na pewno usunąć produkt?')">🗑️ Usuń</a>
                </td>
            </tr>
            """

    content = f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h2>⚙️ Zarządzanie Asortymentem</h2>
            <a href="/admin/dodaj" class="btn btn-green">➕ Dodaj Nowy Produkt</a>
        </div>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Nazwa</th>
                    <th>Kod kreskowy</th>
                    <th>Cena</th>
                    <th>Kategoria</th>
                    <th>Akcje</th>
                </tr>
            </thead>
            <tbody>
                {rows_html if produkty else '<tr><td colspan="6" style="text-align:center;">Brak produktów w bazie.</td></tr>'}
            </tbody>
        </table>
    """
    return render_template_string(HTML_LAYOUT, content=content)

@app.route("/admin/transakcje")
def admin_transakcje():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    transakcje = execute_query("SELECT * FROM transakcje ORDER BY id DESC", fetchall=True)

    rows_html = ""
    if transakcje:
        for t in transakcje:
            rows_html += f"""
            <tr>
                <td>#{t['id']}</td>
                <td>{t['data_czas']}</td>
                <td><b>{t['suma']:.2f} zł</b></td>
                <td>{t['metoda_platnosci']}</td>
                <td><a href="/admin/transakcja/{t['id']}" class="btn btn-blue">🔍 Szczegóły</a></td>
            </tr>
            """

    content = f"""
        <h2>📜 Historia Transakcji</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Data i czas</th>
                    <th>Suma</th>
                    <th>Metoda Płatności</th>
                    <th>Szczegóły</th>
                </tr>
            </thead>
            <tbody>
                {rows_html if transakcje else '<tr><td colspan="5" style="text-align:center;">Brak zarejestrowanych transakcji.</td></tr>'}
            </tbody>
        </table>
    """
    return render_template_string(HTML_LAYOUT, content=content)

@app.route("/admin/transakcja/<int:id>")
def admin_transakcja_szczegoly(id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    transakcja = execute_query("SELECT * FROM transakcje WHERE id = ?", (id,), fetchone=True)
    pozycje = execute_query("SELECT * FROM transakcje_pozycje WHERE transakcja_id = ?", (id,), fetchall=True)

    if not transakcja:
        return redirect(url_for("admin_transakcje"))

    pozycje_html = ""
    if pozycje:
        for p in pozycje:
            pozycje_html += f"""
            <tr>
                <td>{p['nazwa_produktu']}</td>
                <td>{p['cena_jednostkowa']:.2f} zł</td>
                <td>{p['ilosc']}</td>
                <td>{p['wartosc']:.2f} zł</td>
            </tr>
            """

    content = f"""
        <h2>🔍 Szczegóły Transakcji #{transakcja['id']}</h2>
        <p><b>Data:</b> {transakcja['data_czas']} | <b>Metoda:</b> {transakcja['metoda_platnosci']} | <b>Suma:</b> {transakcja['suma']:.2f} zł</p>
        
        <table>
            <thead>
                <tr>
                    <th>Produkt</th>
                    <th>Cena jedn.</th>
                    <th>Ilość</th>
                    <th>Wartość</th>
                </tr>
            </thead>
            <tbody>
                {pozycje_html}
            </tbody>
        </table>
        <br>
        <a href="/admin/transakcje" class="btn btn-blue">← Powrót do historii</a>
    """
    return render_template_string(HTML_LAYOUT, content=content)

@app.route("/admin/dodaj", methods=["GET", "POST"])
def admin_dodaj():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    error = ""
    if request.method == "POST":
        nazwa = request.form.get("nazwa", "").strip()
        kod_kreskowy = request.form.get("kod_kreskowy", "").strip()
        cena_str = request.form.get("cena", "0").replace(",", ".")
        kategoria = request.form.get("kategoria", "Inne").strip()

        try:
            cena = float(cena_str)
            if not nazwa or not kod_kreskowy:
                error = "❌ Wypełnij wszystkie pola!"
            else:
                execute_query(
                    "INSERT INTO produkty (nazwa, kod_kreskowy, cena, kategoria) VALUES (?, ?, ?, ?)",
                    (nazwa, kod_kreskowy, cena, kategoria),
                    commit=True
                )
                return redirect(url_for("admin_panel"))
        except Exception:
            error = "❌ Błąd podczas dodawania produktu lub kod już istnieje!"

    content = f"""
        <h2>➕ Dodaj Nowy Produkt</h2>
        {f'<div class="alert alert-error">{error}</div>' if error else ''}

        <form method="POST">
            <div style="display: flex; flex-direction: column; gap: 15px; max-width: 500px;">
                <label>
                    <b>Nazwa produktu:</b><br>
                    <input type="text" name="nazwa" style="width: 100%;" required>
                </label>
                <label>
                    <b>Kod kreskowy:</b><br>
                    <input type="text" name="kod_kreskowy" style="width: 100%;" required>
                </label>
                <label>
                    <b>Cena (PLN):</b><br>
                    <input type="number" step="0.01" name="cena" style="width: 100%;" required>
                </label>
                <label>
                    <b>Kategoria:</b><br>
                    <input type="text" name="kategoria" value="Ogólna" style="width: 100%;" required>
                </label>
                <div style="margin-top: 10px;">
                    <button type="submit" class="btn btn-green">💾 Zapisz produkt</button>
                    <a href="/admin" class="btn btn-gray">Anuluj</a>
                </div>
            </div>
        </form>
    """
    return render_template_string(HTML_LAYOUT, content=content)

@app.route("/admin/edytuj/<int:id>", methods=["GET", "POST"])
def admin_edytuj(id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    prod = execute_query("SELECT * FROM produkty WHERE id = ?", (id,), fetchone=True)

    if not prod:
        return redirect(url_for("admin_panel"))

    error = ""
    if request.method == "POST":
        nazwa = request.form.get("nazwa", "").strip()
        kod_kreskowy = request.form.get("kod_kreskowy", "").strip()
        cena_str = request.form.get("cena", "0").replace(",", ".")
        kategoria = request.form.get("kategoria", "").strip()

        try:
            cena = float(cena_str)
            execute_query(
                "UPDATE produkty SET nazwa = ?, kod_kreskowy = ?, cena = ?, kategoria = ? WHERE id = ?",
                (nazwa, kod_kreskowy, cena, kategoria, id),
                commit=True
            )
            return redirect(url_for("admin_panel"))
        except Exception:
            error = "❌ Błąd edycji! Sprawdź poprawność danych."

    content = f"""
        <h2>✏️ Edytuj Produkt #{prod['id']}</h2>
        {f'<div class="alert alert-error">{error}</div>' if error else ''}

        <form method="POST">
            <div style="display: flex; flex-direction: column; gap: 15px; max-width: 500px;">
                <label>
                    <b>Nazwa produktu:</b><br>
                    <input type="text" name="nazwa" value="{prod['nazwa']}" style="width: 100%;" required>
                </label>
                <label>
                    <b>Kod kreskowy:</b><br>
                    <input type="text" name="kod_kreskowy" value="{prod['kod_kreskowy']}" style="width: 100%;" required>
                </label>
                <label>
                    <b>Cena (PLN):</b><br>
                    <input type="number" step="0.01" name="cena" value="{prod['cena']:.2f}" style="width: 100%;" required>
                </label>
                <label>
                    <b>Kategoria:</b><br>
                    <input type="text" name="kategoria" value="{prod['kategoria']}" style="width: 100%;" required>
                </label>
                <div style="margin-top: 10px;">
                    <button type="submit" class="btn btn-blue">💾 Zapisz zmiany</button>
                    <a href="/admin" class="btn btn-gray">Anuluj</a>
                </div>
            </div>
        </form>
    """
    return render_template_string(HTML_LAYOUT, content=content)

@app.route("/admin/usun/<int:id>")
def admin_usun(id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    execute_query("DELETE FROM produkty WHERE id = ?", (id,), commit=True)
    return redirect(url_for("admin_panel"))

# ----------------------------------------------------
# PODSUMOWANIE TRANSAKCJI / PARAGON
# ----------------------------------------------------
@app.route("/platnosc/sukces")
def platnosc_sukces():
    t_data = session.get("ostatnia_transakcja")
    if not t_data:
        return redirect(url_for("home"))

    transakcja = execute_query("SELECT * FROM transakcje WHERE id = ?", (t_data["id"],), fetchone=True)
    pozycje = execute_query("SELECT * FROM transakcje_pozycje WHERE transakcja_id = ?", (t_data["id"],), fetchall=True)

    pozycje_html = ""
    if pozycje:
        for p in pozycje:
            pozycje_html += f"""
            <tr>
                <td style="padding: 4px 0;">{p['nazwa_produktu']}</td>
                <td style="padding: 4px 0; text-align: center;">{p['ilosc']}</td>
                <td style="padding: 4px 0; text-align: right;">{p['wartosc']:.2f}</td>
            </tr>
            """

    content = f"""
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="color: #2ecc71; margin-bottom: 5px;">🎉 Transakcja Zakończona Sukcesem!</h2>
            <p>Dziękujemy za zakupy.</p>
        </div>

        <div id="paragon" style="max-width: 320px; margin: 0 auto; background: #fff8e7; padding: 20px; border: 1px dashed #aaa; font-family: 'Courier New', Courier, monospace; color: #000; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">
            <div style="text-align: center; border-bottom: 1px dashed #000; padding-bottom: 10px; margin-bottom: 10px;">
                <h3 style="margin: 0; font-size: 1.2em;">SKLEP MONOPOLOWO-SPOŻYWCZY</h3>
                <small>ul. Przykładowa 12, Warszawa</small><br>
                <small>NIP: 123-456-78-90</small>
            </div>

            <div style="font-size: 0.85em; margin-bottom: 10px;">
                PARAGON FISKALNY #{transakcja['id']}<br>
                Data: {transakcja['data_czas']}
            </div>

            <table style="width: 100%; font-size: 0.85em; border-collapse: collapse;">
                <thead>
                    <tr style="border-bottom: 1px solid #000;">
                        <th style="text-align: left; padding-bottom: 4px;">Nazwa</th>
                        <th style="text-align: center; padding-bottom: 4px;">Ilość</th>
                        <th style="text-align: right; padding-bottom: 4px;">Wartość</th>
                    </tr>
                </thead>
                <tbody>
                    {pozycje_html}
                </tbody>
            </table>

            <div style="border-top: 1px dashed #000; margin-top: 10px; padding-top: 10px; font-weight: bold; font-size: 1.1em; display: flex; justify-content: space-between;">
                <span>SUMA PLN:</span>
                <span>{transakcja['suma']:.2f}</span>
            </div>

            <div style="font-size: 0.85em; margin-top: 8px;">
                Forma płatności: {transakcja['metoda_platnosci']}<br>
                {"Wpłacono: " + f"{transakcja['wplacono']:.2f} zł" if transakcja['metoda_platnosci'] == "Gotówka" else ""}<br>
                {"Reszta: " + f"{transakcja['reszta']:.2f} zł" if transakcja['metoda_platnosci'] == "Gotówka" else ""}
            </div>

            <div style="text-align: center; margin-top: 15px; border-top: 1px dashed #000; padding-top: 10px; font-size: 0.8em;">
                *** DZIĘKUJEMY I ZAPRASZAMY PONOWNIE ***
            </div>
        </div>

        <div style="text-align: center; margin-top: 25px; display: flex; justify-content: center; gap: 10px;">
            <button onclick="window.print()" class="btn btn-blue">🖨️ Drukuj Paragon</button>
            <a href="/" class="btn btn-green">🛒 Nowa Transakcja</a>
        </div>
    """
    return render_template_string(HTML_LAYOUT, content=content)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
