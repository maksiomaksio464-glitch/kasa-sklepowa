from flask import Flask, render_template_string, request, redirect, url_for, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "super_tajny_klucz_kasy"

# ----------------------------------------------------
# BAZA DANYCH (SQLite)
# ----------------------------------------------------
def init_db():
    conn = sqlite3.connect("kasa.db")
    cursor = conn.cursor()
    # Tabela produktów
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produkty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nazwa TEXT NOT NULL,
            kod_kreskowy TEXT UNIQUE NOT NULL,
            cena REAL NOT NULL,
            kategoria TEXT NOT NULL
        )
    """)
    # Tabela nagłówków transakcji
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transakcje (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_czas TEXT NOT NULL,
            suma REAL NOT NULL,
            metoda_platnosci TEXT NOT NULL,
            wplacono REAL,
            reszta REAL
        )
    """)
    # Tabela pozycji w transakcjach
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transakcje_pozycje (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transakcja_id INTEGER NOT NULL,
            nazwa_produktu TEXT NOT NULL,
            cena_jedn REAL NOT NULL,
            ilosc REAL NOT NULL,
            wartosc REAL NOT NULL,
            FOREIGN KEY(transakcja_id) REFERENCES transakcje(id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect("kasa.db")
    conn.row_factory = sqlite3.Row
    return conn

# ----------------------------------------------------
# SZABLON HTML
# ----------------------------------------------------
HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kasa Sklepowa</title>
    <script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #eef2f5; margin: 0; padding: 15px; }
        .container { max-width: 1000px; margin: auto; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        h1, h2, h3 { color: #1a252f; margin-top: 0; }
        .btn { padding: 10px 15px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; text-decoration: none; display: inline-block; font-size: 15px; text-align: center; }
        .btn-green { background: #2ecc71; color: white; }
        .btn-red { background: #e74c3c; color: white; }
        .btn-blue { background: #3498db; color: white; }
        .btn-orange { background: #e67e22; color: white; }
        .btn-gray { background: #95a5a6; color: white; }
        
        form { margin-bottom: 20px; }
        input, select { padding: 10px; border: 1px solid #ccc; border-radius: 6px; font-size: 16px; }
        .input-group { display: flex; gap: 10px; flex-wrap: wrap; }
        .input-group input { flex: 1; min-width: 150px; }

        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }

        .header-nav { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #eee; padding-bottom: 15px; margin-bottom: 20px; }
        .summary { background: #2c3e50; color: white; padding: 18px; border-radius: 8px; text-align: right; margin-top: 20px; font-size: 1.3em; }
        .summary span { color: #2ecc71; font-weight: bold; font-size: 1.3em; }
        
        .alert { padding: 10px; border-radius: 6px; margin-bottom: 15px; font-weight: bold; }
        .alert-error { background: #f8d7da; color: #721c24; }
        .alert-success { background: #d4edda; color: #155724; }

        .qty-input { width: 60px; text-align: center; padding: 5px; font-weight: bold; }

        #reader { width: 100%; max-width: 500px; margin: 15px auto; border-radius: 8px; overflow: hidden; display: none; }
        .scanner-box { text-align: center; background: #f8f9fa; border: 2px dashed #b2bec3; padding: 15px; border-radius: 8px; margin-bottom: 20px; }

        .search-results { background: #fff; border: 1px solid #ddd; border-radius: 6px; margin-top: 5px; max-height: 200px; overflow-y: auto; }
        .search-item { padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
        .search-item:hover { background: #f1f2f6; }

        .payment-box { background: #f8f9fa; border: 1px solid #ddd; padding: 20px; border-radius: 8px; margin-top: 20px; }
        .payment-methods { display: flex; gap: 15px; margin: 15px 0; }
        .payment-methods label { flex: 1; background: white; border: 2px solid #ccc; padding: 15px; border-radius: 8px; text-align: center; cursor: pointer; font-weight: bold; font-size: 18px; }
        .payment-methods input[type="radio"] { display: none; }
        .payment-methods label.active { border-color: #2ecc71; background: #e8f8f5; }

        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: #f8f9fa; border: 1px solid #ddd; padding: 15px; border-radius: 8px; text-align: center; }
        .stat-card h4 { margin: 0; color: #7f8c8d; font-size: 0.9em; }
        .stat-card p { margin: 5px 0 0 0; font-size: 1.5em; font-weight: bold; color: #2c3e50; }
    </style>
</head>
<body>
    <div class="container">
        {{ content | safe }}
    </div>
</body>
</html>
"""

# ----------------------------------------------------
# TRASY APLIKACJI - EKRAN GŁÓWNY
# ----------------------------------------------------

@app.route("/")
def home():
    koszyk = session.get("koszyk", {})
    szukaj_q = request.args.get("q", "").strip()
    
    produkty_w_koszyku = []
    suma_total = 0.0

    if koszyk:
        conn = get_db_connection()
        for kod, ilosc in koszyk.items():
            prod = conn.execute("SELECT * FROM produkty WHERE kod_kreskowy = ?", (kod,)).fetchone()
            if prod:
                wartosc = prod["cena"] * ilosc
                suma_total += wartosc
                produkty_w_koszyku.append({
                    "id": prod["id"],
                    "nazwa": prod["nazwa"],
                    "kod_kreskowy": prod["kod_kreskowy"],
                    "cena": prod["cena"],
                    "kategoria": prod["kategoria"],
                    "ilosc": ilosc,
                    "wartosc": wartosc
                })
        conn.close()

    wyniki_szukania = []
    if szukaj_q:
        conn = get_db_connection()
        wyniki_szukania = conn.execute(
            "SELECT * FROM produkty WHERE nazwa LIKE ? OR kod_kreskowy LIKE ?", 
            (f"%{szukaj_q}%", f"%{szukaj_q}%")
        ).fetchall()
        conn.close()

    rows = ""
    for item in produkty_w_koszyku:
        rows += f"""
        <tr>
            <td><b>{item['nazwa']}</b><br><small style="color: #7f8c8d;">{item['kategoria']}</small></td>
            <td><code>{item['kod_kreskowy']}</code></td>
            <td>{item['cena']:.2f} zł</td>
            <td>
                <form action="/koszyk/zmien_ilosc" method="POST" style="display: inline; margin: 0;">
                    <input type="hidden" name="kod" value="{item['kod_kreskowy']}">
                    <input type="number" step="0.001" name="ilosc" value="{item['ilosc']}" class="qty-input" onchange="this.form.submit()">
                </form>
            </td>
            <td><b>{item['wartosc']:.2f} zł</b></td>
            <td>
                <a href="/koszyk/usun/{item['kod_kreskowy']}" class="btn btn-red" style="padding: 4px 8px; font-size: 13px;">✕</a>
            </td>
        </tr>
        """

    search_html = ""
    if szukaj_q:
        search_html += f"<h4>🔎 Wyniki wyszukiwania dla: '{szukaj_q}'</h4><div class='search-results'>"
        if wyniki_szukania:
            for p in wyniki_szukania:
                search_html += f"""
                <div class='search-item'>
                    <div><b>{p['nazwa']}</b> ({p['cena']:.2f} zł) - <code>{p['kod_kreskowy']}</code></div>
                    <form action='/koszyk/dodaj' method='POST' style='margin: 0;'>
                        <input type='hidden' name='kod_kreskowy' value='{p['kod_kreskowy']}'>
                        <button type='submit' class='btn btn-green' style='padding: 5px 10px;'>+ Dodaj</button>
                    </form>
                </div>
                """
        else:
            search_html += "<div class='search-item' style='color: #7f8c8d;'>Brak wyników.</div>"
        search_html += "</div><br>"

    msg = session.pop("msg", None)
    msg_type = session.pop("msg_type", "error")
    alert_html = f'<div class="alert alert-{msg_type}">{msg}</div>' if msg else ""

    content = f"""
        <div class="header-nav">
            <h1>🛒 Kasa Sklepowa</h1>
            <div>
                <a href="/admin" class="btn btn-blue">⚙️ Admin</a>
            </div>
        </div>

        {alert_html}

        <div class="scanner-box">
            <h3>📷 Skaner Kodów Kreskowych</h3>
            <button id="start-scan-btn" class="btn btn-blue" onclick="startScanner()">📷 Włącz aparat</button>
            <button id="stop-scan-btn" class="btn btn-red" onclick="stopScanner()" style="display: none;">⏹️ Wyłącz aparat</button>
            <div id="reader"></div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
            <form id="barcode-form" action="/koszyk/dodaj" method="POST">
                <h3>🔍 Wpisz kod kreskowy:</h3>
                <div class="input-group">
                    <input type="text" id="kod_kreskowy_input" name="kod_kreskowy" placeholder="Kod kreskowy..." required>
                    <button type="submit" class="btn btn-green">➕ Dodaj</button>
                </div>
            </form>

            <form action="/" method="GET">
                <h3>🔎 Szukaj po nazwie:</h3>
                <div class="input-group">
                    <input type="text" name="q" value="{szukaj_q}" placeholder="np. Chleb, Jabłka...">
                    <button type="submit" class="btn btn-blue">Szukaj</button>
                </div>
            </form>
        </div>

        {search_html}

        <h3>📋 Koszyk:</h3>
        <table>
            <thead>
                <tr>
                    <th>Produkt</th>
                    <th>Kod</th>
                    <th>Cena</th>
                    <th>Ilość / Waga</th>
                    <th>Wartość</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                {rows if rows else '<tr><td colspan="6" style="text-align: center; color: #7f8c8d;">Koszyk jest pusty. Zeskanuj lub dodaj produkt!</td></tr>'}
            </tbody>
        </table>

        <div class="summary">
            Suma do zapłaty: <span>{suma_total:.2f} zł</span>
        </div>

        <div style="margin-top: 15px; display: flex; justify-content: space-between;">
            <a href="/koszyk/wyczysc" class="btn btn-red" onclick="return confirm('Wyczyścić cały koszyk?')">🗑️ Wyczyść</a>
            <a href="/platnosc" class="btn btn-green" style="font-size: 18px; padding: 12px 25px; {'pointer-events: none; opacity: 0.5;' if not koszyk else ''}">💵 Przejdź do Płatności</a>
        </div>

        <script>
            let html5QrcodeScanner = null;

            function startScanner() {{
                document.getElementById('reader').style.display = 'block';
                document.getElementById('start-scan-btn').style.display = 'none';
                document.getElementById('stop-scan-btn').style.display = 'inline-block';

                html5QrcodeScanner = new Html5Qrcode("reader");
                const config = {{ fps: 10, qrbox: {{ width: 250, height: 150 }} }};

                html5QrcodeScanner.start(
                    {{ facingMode: "environment" }},
                    config,
                    onScanSuccess
                ).catch(err => {{
                    alert("Błąd aparatu: " + err);
                    stopScanner();
                }});
            }}

            function stopScanner() {{
                if (html5QrcodeScanner) {{
                    html5QrcodeScanner.stop().then(() => {{
                        document.getElementById('reader').style.display = 'none';
                        document.getElementById('start-scan-btn').style.display = 'inline-block';
                        document.getElementById('stop-scan-btn').style.display = 'none';
                    }}).catch(err => console.log(err));
                }}
            }}

            function onScanSuccess(decodedText) {{
                let audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                let osc = audioCtx.createOscillator();
                osc.connect(audioCtx.destination);
                osc.frequency.value = 800;
                osc.start();
                osc.stop(audioCtx.currentTime + 0.15);

                document.getElementById('kod_kreskowy_input').value = decodedText;
                stopScanner();
                document.getElementById('barcode-form').submit();
            }}
        </script>
    """
    return render_template_string(HTML_LAYOUT, content=content)


# ----------------------------------------------------
# EKRAN PŁATNOŚCI I SYMULACJA TERMINALA POS
# ----------------------------------------------------
@app.route("/platnosc", methods=["GET", "POST"])
def platnosc():
    koszyk = session.get("koszyk", {})
    if not koszyk:
        return redirect(url_for("home"))

    conn = get_db_connection()
    produkty_w_koszyku = []
    suma_total = 0.0

    for kod, ilosc in koszyk.items():
        prod = conn.execute("SELECT * FROM produkty WHERE kod_kreskowy = ?", (kod,)).fetchone()
        if prod:
            wartosc = prod["cena"] * ilosc
            suma_total += wartosc
            produkty_w_koszyku.append({
                "nazwa": prod["nazwa"],
                "cena": prod["cena"],
                "ilosc": ilosc,
                "wartosc": wartosc
            })

    error = ""
    if request.method == "POST":
        metoda = request.form.get("metoda")
        wplacono_str = request.form.get("wplacono", "0").replace(",", ".")
        wplacono = float(wplacono_str) if wplacono_str else 0.0

        if metoda == "Gotówka" and wplacono < suma_total:
            error = f"❌ Podano za małą kwotę! Brakuje: {(suma_total - wplacono):.2f} zł"
        elif metoda in ["Karta", "BLIK"]:
            # Jeśli wybrano kartę/BLIK -> przekierowujemy na ekran terminala
            session["oczekujaca_transakcja"] = {
                "suma": suma_total,
                "metoda": metoda,
                "produkty": produkty_w_koszyku
            }
            conn.close()
            return redirect(url_for("platnosc_terminal"))
        else:
            # Gotówka - zapisujemy od razu
            reszta = wplacono - suma_total
            data_czas = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO transakcje (data_czas, suma, metoda_platnosci, wplacono, reszta) VALUES (?, ?, ?, ?, ?)",
                (data_czas, suma_total, metoda, wplacono, reszta)
            )
            transakcja_id = cursor.lastrowid

            for item in produkty_w_koszyku:
                cursor.execute(
                    "INSERT INTO transakcje_pozycje (transakcja_id, nazwa_produktu, cena_jedn, ilosc, wartosc) VALUES (?, ?, ?, ?, ?)",
                    (transakcja_id, item["nazwa"], item["cena"], item["ilosc"], item["wartosc"])
                )

            conn.commit()
            conn.close()

            session.pop("koszyk", None)
            session["ostatnia_transakcja"] = {
                "id": transakcja_id,
                "suma": suma_total,
                "metoda": metoda,
                "wplacono": wplacono,
                "reszta": reszta
            }
            return redirect(url_for("platnosc_sukces"))

    conn.close()

    content = f"""
        <h2>💵 Ekran Płatności</h2>
        {f'<div class="alert alert-error">{error}</div>' if error else ''}

        <div class="summary" style="text-align: center; font-size: 1.8em; margin-bottom: 20px;">
            Do zapłaty: <span>{suma_total:.2f} zł</span>
        </div>

        <form method="POST">
            <h3>1. Wybierz metodę płatności:</h3>
            <div class="payment-methods">
                <label id="lbl-gotowka" class="active">
                    <input type="radio" name="metoda" value="Gotówka" checked onclick="toggleGotowka(true)">
                    💵 Gotówka
                </label>
                <label id="lbl-karta">
                    <input type="radio" name="metoda" value="Karta" onclick="toggleGotowka(false)">
                    💳 Karta
                </label>
                <label id="lbl-blik">
                    <input type="radio" name="metoda" value="BLIK" onclick="toggleGotowka(false)">
                    📱 BLIK
                </label>
            </div>

            <div id="box-gotowka" class="payment-box">
                <h3>2. Podaj kwotę od klienta:</h3>
                <div class="input-group">
                    <input type="number" step="0.01" id="wplacono" name="wplacono" placeholder="np. 50" oninput="obliczReszte({suma_total:.2f})">
                </div>
                <h3 style="margin-top: 15px;">Reszta do wydania: <span id="reszta-val" style="color: #e74c3c;">0.00 zł</span></h3>
            </div>

            <div style="margin-top: 25px; display: flex; justify-content: space-between;">
                <a href="/" class="btn btn-gray">← Powrót do kasy</a>
                <button type="submit" class="btn btn-green" style="font-size: 18px; padding: 12px 30px;">✅ Przejdź dalej</button>
            </div>
        </form>

        <script>
            function toggleGotowka(isGotowka) {{
                document.getElementById('box-gotowka').style.display = isGotowka ? 'block' : 'none';
                document.getElementById('lbl-gotowka').className = isGotowka ? 'active' : '';
                document.getElementById('lbl-karta').className = !isGotowka ? '' : '';
                document.getElementById('lbl-blik').className = !isGotowka ? '' : '';
            }}

            function obliczReszte(suma) {{
                let wplacono = parseFloat(document.getElementById('wplacono').value) || 0;
                let reszta = wplacono - suma;
                let el = document.getElementById('reszta-val');

                if (reszta >= 0) {{
                    el.innerText = reszta.toFixed(2) + " zł";
                    el.style.color = "#2ecc71";
                }} else {{
                    el.innerText = "Za mało o " + Math.abs(reszta).toFixed(2) + " zł";
                    el.style.color = "#e74c3c";
                }}
            }}
        </script>
    """
    return render_template_string(HTML_LAYOUT, content=content)


@app.route("/platnosc/terminal", methods=["GET", "POST"])
def platnosc_terminal():
    t_data = session.get("oczekujaca_transakcja")
    if not t_data:
        return redirect(url_for("home"))

    # Dokończenie transakcji po udanej autoryzacji w terminalu
    if request.method == "POST":
        conn = get_db_connection()
        data_czas = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO transakcje (data_czas, suma, metoda_platnosci, wplacono, reszta) VALUES (?, ?, ?, ?, ?)",
            (data_czas, t_data["suma"], t_data["metoda"], t_data["suma"], 0.0)
        )
        transakcja_id = cursor.lastrowid

        for item in t_data["produkty"]:
            cursor.execute(
                "INSERT INTO transakcje_pozycje (transakcja_id, nazwa_produktu, cena_jedn, ilosc, wartosc) VALUES (?, ?, ?, ?, ?)",
                (transakcja_id, item["nazwa"], item["cena"], item["ilosc"], item["wartosc"])
            )

        conn.commit()
        conn.close()

        session.pop("koszyk", None)
        session.pop("oczekujaca_transakcja", None)
        session["ostatnia_transakcja"] = {
            "id": transakcja_id,
            "suma": t_data["suma"],
            "metoda": t_data["metoda"],
            "wplacono": t_data["suma"],
            "reszta": 0.0
        }
        return redirect(url_for("platnosc_sukces"))

    content = f"""
        <div style="max-width: 450px; margin: 30px auto; background: #2c3e50; color: white; padding: 30px; border-radius: 15px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.3); font-family: monospace;">
            <h3 style="color: #bdc3c7; margin-bottom: 5px;">TERMINAL POS</h3>
            <p style="font-size: 0.9em; color: #7f8c8d; margin-top: 0;">OCZEKIWANIE NA KARTĘ / BLIK</p>
            <hr style="border-color: #34495e;">

            <div style="font-size: 2.2em; font-weight: bold; margin: 25px 0; color: #2ecc71;">
                {t_data['suma']:.2f} PLN
            </div>

            <div id="terminal-status" style="background: #34495e; padding: 15px; border-radius: 8px; font-size: 1.1em; margin-bottom: 25px; min-height: 50px; display: flex; align-items: center; justify-content: center;">
                📲 Proszę zbliżyć kartę lub podać BLIK...
            </div>

            <form id="finish-form" method="POST">
                <button type="submit" id="confirm-btn" class="btn btn-green" style="width: 100%; display: none; font-size: 18px; padding: 12px;">✅ Dokończ</button>
            </form>
            <a href="/platnosc" class="btn btn-red" style="margin-top: 10px; width: 90%; font-size: 13px;"> Anuluj transakcję</a>
        </div>

        <script>
            let statusEl = document.getElementById('terminal-status');
            let formEl = document.getElementById('finish-form');

            // Krok 1: Wykrycie karty po 2 sek
            setTimeout(() => {{
                statusEl.innerText = "⏳ Odczytywanie karty / autoryzacja...";
                statusEl.style.color = "#f1c40f";
            }}, 2000);

            // Krok 2: Akceptacja po 4 sek
            setTimeout(() => {{
                statusEl.innerText = "✅ Transakcja Zaakceptowana!";
                statusEl.style.color = "#2ecc71";
                
                // Automatyczne wysłanie formularza
                setTimeout(() => {{
                    formEl.submit();
                }}, 1000);
            }}, 4000);
        </script>
    """
    return render_template_string(HTML_LAYOUT, content=content)

# ----------------------------------------------------
# AKCJE KOSZYKA
# ----------------------------------------------------
@app.route("/koszyk/dodaj", methods=["POST"])
def koszyk_dodaj():
    kod = request.form.get("kod_kreskowy", "").strip()
    
    conn = get_db_connection()
    prod = conn.execute("SELECT * FROM produkty WHERE kod_kreskowy = ?", (kod,)).fetchone()
    conn.close()

    if not prod:
        session["msg"] = f"❌ Brak produktu o kodzie: {kod}"
        session["msg_type"] = "error"
    else:
        koszyk = session.get("koszyk", {})
        koszyk[kod] = koszyk.get(kod, 0) + 1
        session["koszyk"] = koszyk
        session["msg"] = f"✅ Dodano: {prod['nazwa']}"
        session["msg_type"] = "success"

    return redirect(url_for("home"))

@app.route("/koszyk/zmien_ilosc", methods=["POST"])
def koszyk_zmien_ilosc():
    kod = request.form.get("kod")
    try:
        ilosc = float(request.form.get("ilosc", 1))
        koszyk = session.get("koszyk", {})
        if kod in koszyk:
            if ilosc <= 0:
                del koszyk[kod]
            else:
                koszyk[kod] = ilosc
            session["koszyk"] = koszyk
    except ValueError:
        pass
    return redirect(url_for("home"))

@app.route("/koszyk/usun/<kod>")
def koszyk_usun(kod):
    koszyk = session.get("koszyk", {})
    if kod in koszyk:
        del koszyk[kod]
        session["koszyk"] = koszyk
    return redirect(url_for("home"))

@app.route("/koszyk/wyczysc")
def koszyk_wyczysc():
    session.pop("koszyk", None)
    return redirect(url_for("home"))


# ----------------------------------------------------
# PANEL ADMINA + RAPORTY I HISTORIA
# ----------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = ""
    if request.method == "POST":
        haslo = request.form.get("haslo")
        if haslo == "admin123":
            session["admin"] = True
            return redirect(url_for("admin_panel"))
        else:
            error = "❌ Niepoprawne hasło!"

    content = f"""
        <h2>🔒 Logowanie Admina</h2>
        <p style="color: red;">{error}</p>
        <form method="POST">
            <input type="password" name="haslo" placeholder="Hasło (admin123)" required>
            <button type="submit" class="btn btn-blue">Zaloguj</button>
        </form>
        <a href="/">← Powrót</a>
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

    conn = get_db_connection()
    produkty = conn.execute("SELECT * FROM produkty").fetchall()
    conn.close()

    rows = ""
    for p in produkty:
        rows += f"""
        <tr>
            <td>{p['id']}</td>
            <td><b>{p['nazwa']}</b></td>
            <td><code>{p['kod_kreskowy']}</code></td>
            <td>{p['cena']:.2f} zł</td>
            <td>{p['kategoria']}</td>
            <td>
                <a href="/admin/edytuj/{p['id']}" class="btn btn-orange" style="padding: 4px 8px; font-size: 13px;">Edytuj</a>
                <a href="/admin/usun/{p['id']}" class="btn btn-red" style="padding: 4px 8px; font-size: 13px;" onclick="return confirm('Usuń?')">Usuń</a>
            </td>
        </tr>
        """

    content = f"""
        <div class="header-nav">
            <h2>⚙️ Panel Administratora</h2>
            <div>
                <a href="/admin/transakcje" class="btn btn-orange">📜 Historia i Raporty</a>
                <a href="/admin/dodaj" class="btn btn-green">+ Dodaj Produkt</a>
                <a href="/admin/logout" class="btn btn-red">Wyloguj</a>
            </div>
        </div>
        <h3>📦 Lista Produktów w Bazie</h3>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Nazwa</th>
                    <th>Kod</th>
                    <th>Cena</th>
                    <th>Kategoria</th>
                    <th>Akcje</th>
                </tr>
            </thead>
            <tbody>
                {rows if rows else '<tr><td colspan="6">Brak produktów. Dodaj pierwszy!</td></tr>'}
            </tbody>
        </table>
        <br>
        <a href="/" class="btn btn-blue">← Powrót do Kasy</a>
    """
    return render_template_string(HTML_LAYOUT, content=content)


@app.route("/admin/transakcje")
def admin_transakcje():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    transakcje = conn.execute("SELECT * FROM transakcje ORDER BY id DESC").fetchall()

    # Wyliczanie statystyk
    obrot_total = conn.execute("SELECT SUM(suma) FROM transakcje").fetchone()[0] or 0.0
    liczba_transakcji = conn.execute("SELECT COUNT(*) FROM transakcje").fetchone()[0] or 0
    
    obrot_gotowka = conn.execute("SELECT SUM(suma) FROM transakcje WHERE metoda_platnosci = 'Gotówka'").fetchone()[0] or 0.0
    obrot_karta = conn.execute("SELECT SUM(suma) FROM transakcje WHERE metoda_platnosci = 'Karta'").fetchone()[0] or 0.0
    obrot_blik = conn.execute("SELECT SUM(suma) FROM transakcje WHERE metoda_platnosci = 'BLIK'").fetchone()[0] or 0.0

    conn.close()

    rows = ""
    for t in transakcje:
        rows += f"""
        <tr>
            <td><b>#{t['id']}</b></td>
            <td>{t['data_czas']}</td>
            <td><b>{t['suma']:.2f} zł</b></td>
            <td><span class="btn btn-gray" style="padding: 2px 8px; font-size: 12px;">{t['metoda_platnosci']}</span></td>
            <td>
                <a href="/admin/transakcja/{t['id']}" class="btn btn-blue" style="padding: 4px 8px; font-size: 13px;">👁️ Podgląd paragonu</a>
            </td>
        </tr>
        """

    content = f"""
        <div class="header-nav">
            <h2>📊 Historia Sprzedaży i Raporty</h2>
            <div>
                <a href="/admin" class="btn btn-gray">← Powrót do Produktów</a>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <h4>ŁĄCZNY OBRÓT</h4>
                <p style="color: #2ecc71;">{obrot_total:.2f} zł</p>
            </div>
            <div class="stat-card">
                <h4>LICZBA TRANSAKCJI</h4>
                <p>{liczba_transakcji}</p>
            </div>
            <div class="stat-card">
                <h4>GOTÓWKA</h4>
                <p>{obrot_gotowka:.2f} zł</p>
            </div>
            <div class="stat-card">
                <h4>KARTA / BLIK</h4>
                <p>{(obrot_karta + obrot_blik):.2f} zł</p>
            </div>
        </div>

        <h3>📜 Lista Transakcji:</h3>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Data i Czas</th>
                    <th>Suma</th>
                    <th>Metoda</th>
                    <th>Szczegóły</th>
                </tr>
            </thead>
            <tbody>
                {rows if rows else '<tr><td colspan="5" style="text-align: center; color: #7f8c8d;">Brak zarejestrowanych transakcji.</td></tr>'}
            </tbody>
        </table>
    """
    return render_template_string(HTML_LAYOUT, content=content)


@app.route("/admin/transakcja/<int:id>")
def admin_transakcja_szczegoly(id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    t = conn.execute("SELECT * FROM transakcje WHERE id = ?", (id,)).fetchone()
    if not t:
        conn.close()
        return redirect(url_for("admin_transakcje"))

    pozycje = conn.execute("SELECT * FROM transakcje_pozycje WHERE transakcja_id = ?", (id,)).fetchall()
    conn.close()

    rows = ""
    for p in pozycje:
        rows += f"""
        <tr>
            <td><b>{p['nazwa_produktu']}</b></td>
            <td>{p['cena_jedn']:.2f} zł</td>
            <td>{p['ilosc']}</td>
            <td><b>{p['wartosc']:.2f} zł</b></td>
        </tr>
        """

    content = f"""
        <h2>🧾 Szczegóły Transakcji #{t['id']}</h2>
        <p><b>Data i Czas:</b> {t['data_czas']}</p>
        <p><b>Metoda Płatności:</b> {t['metoda_platnosci']}</p>
        {"<p><b>Wpłacono:</b> " + f"{t['wplacono']:.2f}" + " zł | <b>Reszta:</b> " + f"{t['reszta']:.2f}" + " zł</p>" if t['metoda_platnosci'] == "Gotówka" else ""}

        <h3>Pozycje na paragonie:</h3>
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
                {rows}
            </tbody>
        </table>

        <div class="summary" style="margin-top: 20px;">
            Suma całkowita: <span>{t['suma']:.2f} zł</span>
        </div>

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
        nazwa = request.form.get("nazwa")
        kod = request.form.get("kod_kreskowy")
        cena = request.form.get("cena")
        kategoria = request.form.get("kategoria")

        try:
            conn = get_db_connection()
            conn.execute(
                "INSERT INTO produkty (nazwa, kod_kreskowy, cena, kategoria) VALUES (?, ?, ?, ?)",
                (nazwa, kod, float(cena), kategoria)
            )
            conn.commit()
            conn.close()
            return redirect(url_for("admin_panel"))
        except sqlite3.IntegrityError:
            error = "❌ Kod kreskowy już istnieje!"
        except Exception as e:
            error = f"❌ Błąd: {e}"

    content = f"""
        <h2>➕ Dodaj Produkt</h2>
        <p style="color: red;">{error}</p>
        <form method="POST">
            <input type="text" name="nazwa" placeholder="Nazwa" required>
            <input type="text" name="kod_kreskowy" placeholder="Kod kreskowy" required>
            <input type="number" step="0.01" name="cena" placeholder="Cena" required>
            <input type="text" name="kategoria" placeholder="Kategoria" required>
            <button type="submit" class="btn btn-green">Zapisz</button>
        </form>
        <a href="/admin">← Anuluj</a>
    """
    return render_template_string(HTML_LAYOUT, content=content)

@app.route("/admin/edytuj/<int:id>", methods=["GET", "POST"])
def admin_edytuj(id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    produkt = conn.execute("SELECT * FROM produkty WHERE id = ?", (id,)).fetchone()

    if request.method == "POST":
        nazwa = request.form.get("nazwa")
        kod = request.form.get("kod_kreskowy")
        cena = request.form.get("cena")
        kategoria = request.form.get("kategoria")

        conn.execute(
            "UPDATE produkty SET nazwa = ?, kod_kreskowy = ?, cena = ?, kategoria = ? WHERE id = ?",
            (nazwa, kod, float(cena), kategoria, id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("admin_panel"))

    conn.close()

    content = f"""
        <h2>✏️ Edytuj Produkt</h2>
        <form method="POST">
            <input type="text" name="nazwa" value="{produkt['nazwa']}" required>
            <input type="text" name="kod_kreskowy" value="{produkt['kod_kreskowy']}" required>
            <input type="number" step="0.01" name="cena" value="{produkt['cena']}" required>
            <input type="text" name="kategoria" value="{produkt['kategoria']}" required>
            <button type="submit" class="btn btn-orange">Zapisz</button>
        </form>
        <a href="/admin">← Anuluj</a>
    """
    return render_template_string(HTML_LAYOUT, content=content)

@app.route("/admin/usun/<int:id>")
def admin_usun(id):
    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    conn.execute("DELETE FROM produkty WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_panel"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, ssl_context='adhoc')