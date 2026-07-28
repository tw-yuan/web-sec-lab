import os
import sqlite3
import subprocess
from flask import Flask, g, render_template, render_template_string, request, make_response

app = Flask(__name__)

# ── Flags ─────────────────────────────────────────────────────────────────────
FLAG_CMDI = os.environ.get('FLAG_CMDI', 'AIS3{c0mm4nd_1nj3ct10n_g1v3s_y0u_sh3ll}')
FLAG_XSS  = os.environ.get('FLAG_XSS',  'AIS3{xss_st34ls_c00k13s_l1k3_c4ndy}')
FLAG_SSTI = os.environ.get('FLAG_SSTI', 'AIS3{sst1_t3mpl4t3_1nj3ct10n_pwn3d}')
FLAG_SQLI = os.environ.get('FLAG_SQLI', 'AIS3{sql_1nj3ct10n_byp4ss_3v3ryth1ng}')

# SSTI flag exposed through Flask config (accessible via {{ config }})
app.config['SECRET_FLAG'] = FLAG_SSTI

# Write CMDI flag to file (target of command injection)
with open('/flag_cmdi.txt', 'w') as f:
    f.write(FLAG_CMDI + '\n')

# ── SQLite setup ──────────────────────────────────────────────────────────────
DATABASE = '/tmp/ais3corp.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS employees (
                id      INTEGER PRIMARY KEY,
                name    TEXT NOT NULL,
                dept    TEXT NOT NULL,
                title   TEXT NOT NULL,
                email   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS secrets (
                id      INTEGER PRIMARY KEY,
                name    TEXT NOT NULL,
                value   TEXT NOT NULL
            );
            DELETE FROM employees;
            DELETE FROM secrets;
            INSERT INTO employees VALUES
                (1001, 'Alice Chen',  'Engineering',  'Senior Engineer',     'alice@ais3corp.com'),
                (1002, 'Bob Wang',    'Marketing',    'Marketing Manager',   'bob@ais3corp.com'),
                (1003, 'Carol Liu',   'HR',           'HR Specialist',       'carol@ais3corp.com'),
                (1004, 'David Tsai',  'Security',     'Penetration Tester',  'david@ais3corp.com'),
                (1005, 'Eve Lin',     'Finance',      'Financial Analyst',   'eve@ais3corp.com');
        ''')
        db.execute(
            "INSERT INTO secrets (name, value) VALUES ('flag', ?)", (FLAG_SQLI,)
        )
        db.commit()

init_db()

# ── Sample feedback data (XSS challenge) ──────────────────────────────────────
FEEDBACKS = [
    {'id': 1, 'author': 'Alice Chen',  'content': '很棒的資安服務，稽核報告非常詳盡！',   'date': '2025-01-15'},
    {'id': 2, 'author': 'Bob Wang',    'content': '團隊專業，反應迅速，強烈推薦。',        'date': '2025-02-03'},
    {'id': 3, 'author': 'Carol Liu',   'content': '滲透測試做得很徹底，找出了好幾個漏洞。', 'date': '2025-02-20'},
    {'id': 4, 'author': 'David Tsai',  'content': '報告品質高，說明清楚易懂。',            'date': '2025-03-01'},
]

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ── Challenge 1: Command Injection ────────────────────────────────────────────
@app.route('/network-tool', methods=['GET', 'POST'])
def network_tool():
    result = None
    error  = None
    host   = ''

    if request.method == 'POST':
        host = request.form.get('host', '').strip()
        if host:
            # VULNERABLE: user input passed directly to shell
            cmd = f'ping -c 2 -W 1 {host}'
            try:
                result = subprocess.check_output(
                    cmd, shell=True, stderr=subprocess.STDOUT, timeout=10
                ).decode('utf-8', errors='replace')
            except subprocess.CalledProcessError as e:
                result = e.output.decode('utf-8', errors='replace')
            except subprocess.TimeoutExpired:
                error = '連線逾時，請確認主機位址是否正確。'
            except Exception as e:
                error = str(e)

    return render_template('cmdi.html', result=result, error=error, host=host)


# ── Challenge 2: Reflected XSS ───────────────────────────────────────────────
@app.route('/feedback')
def feedback():
    keyword = request.args.get('q', '')
    if keyword:
        results = [f for f in FEEDBACKS
                   if keyword.lower() in f['content'].lower()
                   or keyword.lower() in f['author'].lower()]
    else:
        results = FEEDBACKS

    # VULNERABLE: keyword rendered with |safe in template (no escaping)
    resp = make_response(render_template('xss.html', keyword=keyword, feedbacks=results))
    # Flag in non-HttpOnly cookie — readable by JS
    resp.set_cookie('flag', FLAG_XSS, httponly=False, samesite='Lax')
    return resp


# ── Challenge 3: SSTI (Jinja2) ───────────────────────────────────────────────
@app.route('/report')
def report():
    name   = request.args.get('name', '')
    result = None

    if name:
        # VULNERABLE: user input embedded directly into Jinja2 template string
        template = f'Hello, {name}! 您的個人化報告已成功產生。'
        try:
            result = render_template_string(template)
        except Exception as e:
            result = f'Template Error: {e}'

    return render_template('ssti.html', name=name, result=result)


# ── Challenge 4: SQL Injection ────────────────────────────────────────────────
@app.route('/employee-search')
def employee_search():
    emp_id  = request.args.get('id', '')
    results = []
    error   = None
    query   = ''

    if emp_id:
        # VULNERABLE: user input concatenated directly into SQL query
        query = f"SELECT id, name, dept, title, email FROM employees WHERE id = {emp_id}"
        try:
            db  = get_db()
            cur = db.execute(query)
            results = [dict(row) for row in cur.fetchall()]
        except Exception as e:
            error = str(e)

    return render_template('sqli.html', emp_id=emp_id, results=results,
                           error=error, query=query)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
