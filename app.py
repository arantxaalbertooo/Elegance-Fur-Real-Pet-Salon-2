"""Elegance Fur Real Pet Salon CRM Hub - Flask + SQLite. Run: python app.py"""
import calendar, csv, json, os, re, sqlite3
from datetime import datetime, timedelta, date
from functools import wraps
from flask import Flask, g, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "salon.db")
SEED = os.path.join(BASE, "seed_data")
app = Flask(__name__)
app.secret_key = "change-this-secret-before-submitting"

ROLES = ("Admin", "Receptionist", "Groomer")
ROLE_HOME = {"Admin": "dashboard", "Receptionist": "dashboard", "Groomer": "appointments"}
STATUSES = ["Scheduled", "In progress", "Completed", "Canceled"]
SVC_SQL = ("SELECT product_id AS service_id, product_name AS service_name, category AS description, unit_price AS price, duration_minutes, is_active FROM products")
STAGES = ["Lead", "Qualified", "Proposal", "Won", "Lost"]
OPEN_MIN, CLOSE_MIN = 8 * 60, 18 * 60          # salon hours 8:00 AM - 6:00 PM
ALL = ROLES
DESK = ("Admin", "Receptionist")
NAV = [
    ("WORKSPACE", [("dashboard", "Dashboard", "▦", ALL), ("appointments", "Appointments & schedule", "▤", ALL),
                   ("customers", "Customer records", "♙", DESK), ("pets", "Pet profiles", "♧", ALL),
                   ("services", "Grooming services", "✦", ALL), ("feedback", "Feedback", "♡", ALL)]),
    ("CRM", [("segments", "Segments & CLV", "◈", DESK), ("pipeline", "Sales pipeline", "⇄", DESK),
             ("service", "Tickets & interactions", "✉", DESK), ("reports", "Reports", "▥", DESK)]),
    ("ADMINISTRATION", [("users", "Staff accounts", "⚙", ("Admin",))]),
]
TITLES = {ep: label for _, items in NAV for ep, label, _, _ in items}
TITLES["customer"] = "Customer profile"


# ---------- formatting helpers (Jinja filters) ----------
def peso(v):
    v = float(v or 0)
    return "₱{:,.0f}".format(v) if v == int(v) else "₱{:,.2f}".format(v)

def code(n, prefix):
    return "{}-{:03d}".format(prefix, int(n)) if n is not None else "—"

def parse_dt(s):
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try: return datetime.strptime(s, f)
        except (TypeError, ValueError): pass
    return None

def _t12(d):
    return "{}:{:02d} {}".format(d.hour % 12 or 12, d.minute, "AM" if d.hour < 12 else "PM")

def dlabel(s):
    d = parse_dt(s)
    return "{}, {} {}, {}".format(d.strftime("%a"), d.strftime("%b"), d.day, d.year) if d else "—"

def tlabel(s):
    d = parse_dt(s)
    return _t12(d) if d else "—"

def dtlabel(s):
    d = parse_dt(s)
    return "{} {}, {} · {}".format(d.strftime("%b"), d.day, d.year, _t12(d)) if d else "—"

def initials(s):
    return "".join(w[0] for w in str(s or "?").split()[:2]).upper()

def stars(n):
    n = max(0, min(5, int(round(float(n or 0)))))
    return "★" * n + "☆" * (5 - n)

def age_text(n):                    # pets.age is text in the schema ("3 years")
    return None if n in (None, "") else "{} year{}".format(int(n), "" if int(n) == 1 else "s")

def agenum(s):
    m = re.match(r"\d+", str(s or ""))
    return int(m.group()) if m else ""

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")

for _n, _f in dict(agenum=agenum, peso=peso, code=code, dlabel=dlabel, tlabel=tlabel, dtlabel=dtlabel, initials=initials, stars=stars, slug=slug).items():
    app.jinja_env.filters[_n] = _f


# ---------- database helpers (every query is parameterized) ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    d = g.pop("db", None)
    if d: d.close()

def q(sql, args=(), one=False):
    rows = db().execute(sql, args).fetchall()
    return (rows[0] if rows else None) if one else rows

def run(sql, args=()):
    cur = db().execute(sql, args); db().commit(); return cur.lastrowid

def one(sql, args=()):
    return q(sql, args, one=True)[0]

def now(): return datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------- MODULE 1: login, roles and staff accounts ----------
def home():
    return url_for(ROLE_HOME.get(session.get("role"), "dashboard"))

def access(*roles):
    """Login + role check. A wrong role gets a notice and is sent back home (never signed out)."""
    roles = roles or ALL
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            if "uid" not in session: return redirect(url_for("login"))
            if session.get("role") not in roles:
                flash("That page is not available for your role. You are still signed in.", "err")
                return redirect(home())
            return f(*a, **k)
        return w
    return deco

@app.before_request
def still_active():
    if "uid" in session and request.endpoint not in ("static", "logout"):
        u = q("SELECT is_active, role, full_name FROM users WHERE user_id=?", (session["uid"],), one=True)
        if not u or not u["is_active"]:
            session.clear(); flash("Your account is disabled or no longer exists.", "err")
            return redirect(url_for("login"))
        session.update(role=u["role"], name=u["full_name"])

@app.context_processor
def inject():
    role = session.get("role")
    nav = [(sec, [(ep, lab, ic) for ep, lab, ic, rl in items if role in rl]) for sec, items in NAV]
    ep = request.endpoint or ""
    return dict(nav=[(s, i) for s, i in nav if i], page_title=TITLES.get(ep, "Workspace"), ep=ep,
                today_label="{}, {} {}".format(datetime.now().strftime("%A"), datetime.now().strftime("%b"), datetime.now().day).upper(), is_desk=role in DESK, is_admin=role == "Admin")

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if "uid" in session and request.method == "GET": return redirect(home())
    if request.method == "POST":
        ident = request.form.get("email", "").strip().lower()
        u = q("SELECT * FROM users WHERE (lower(email)=? OR lower(username)=?) AND is_active=1", (ident, ident), one=True)
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            session.clear(); session.update(uid=u["user_id"], name=u["full_name"], role=u["role"])
            return redirect(home())
        flash("Email or password is incorrect, or this account is disabled.", "err")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.errorhandler(403)
def forbidden(e): return render_template("error.html", msg="You do not have permission to open this page."), 403

@app.errorhandler(404)
def missing(e): return render_template("error.html", msg="We could not find that record."), 404

@app.route("/users", methods=["GET", "POST"])
@access("Admin")
def users():
    if request.method == "POST":
        f = request.form
        name, email, pw, role = f.get("full_name", "").strip(), f.get("email", "").strip().lower(), f.get("password", ""), f.get("role")
        if not name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(pw) < 8 or role not in ROLES:
            flash("Enter a name, a valid email, a role, and a password with at least 8 characters.", "err")
        else:
            try:
                base, n = email.split("@")[0], 1
                uname = base
                while q("SELECT 1 FROM users WHERE lower(username)=?", (uname.lower(),), one=True): n += 1; uname = base + str(n)
                run("INSERT INTO users(full_name,username,email,password_hash,role,phone,created_at) VALUES(?,?,?,?,?,?,?)",
                    (name, uname, email, generate_password_hash(pw), role, f.get("phone", "").strip(), now()[:10]))
                flash("Staff account created.", "ok")
            except sqlite3.IntegrityError:
                flash("An account already uses that email.", "err")
        return redirect(url_for("users"))
    return render_template("users.html", rows=q("SELECT * FROM users ORDER BY CASE role WHEN 'Admin' THEN 0 WHEN 'Receptionist' THEN 1 ELSE 2 END, full_name"))

@app.route("/users/<int:uid>/toggle", methods=["POST"])
@access("Admin")
def user_toggle(uid):
    if uid == session["uid"]: flash("You cannot deactivate your own account.", "err")
    else:
        run("UPDATE users SET is_active=1-is_active WHERE user_id=?", (uid,)); flash("Account updated.", "ok")
    return redirect(url_for("users"))


# ---------- MODULE 2: customer management ----------
def default_segment():
    return one("SELECT segment_id FROM segments ORDER BY min_clv LIMIT 1")

CUST_SQL = ("SELECT c.*, sg.segment_name, (SELECT COUNT(*) FROM pets p WHERE p.customer_id=c.customer_id) AS npets, "
            "(SELECT COUNT(*) FROM appointments a WHERE a.customer_id=c.customer_id AND a.status='Completed') AS visits "
            "FROM customers c LEFT JOIN segments sg ON sg.segment_id=c.segment_id ")

@app.route("/customers")
@access(*DESK)
def customers():
    s, seg, show = request.args.get("q", "").strip(), request.args.get("segment", ""), request.args.get("show", "active")
    sql = CUST_SQL + ("WHERE (c.first_name||' '||c.last_name||' '||c.email||' '||IFNULL(c.phone,'')||' '||IFNULL(c.address,'')) LIKE ?")
    args = ["%" + s + "%"]
    if seg: sql += " AND c.segment_id=?"; args.append(seg)
    if show == "active": sql += " AND c.is_active=1"
    return render_template("customers.html", rows=q(sql + " ORDER BY c.last_name, c.first_name", args),
                           segments=q("SELECT * FROM segments ORDER BY min_clv DESC"), s=s, seg=seg, show=show)

@app.route("/customers/save", methods=["POST"])
@access(*DESK)
def customer_save():
    f = request.form
    cid = f.get("customer_id", "").strip()
    first, last, email, phone = f.get("first_name", "").strip(), f.get("last_name", "").strip(), f.get("email", "").strip().lower(), f.get("phone", "").strip()
    back = url_for("customer", cid=cid) if cid else url_for("customers")
    if not first or not last or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        flash("First name, last name and a valid email are required.", "err"); return redirect(back)
    if phone and not re.fullmatch(r"[0-9+\-\s()]{7,20}", phone):
        flash("Phone number may only contain digits, spaces, + - and brackets (7 to 20 characters).", "err"); return redirect(back)
    consent = 1 if f.get("consent_given") else 0
    try:
        if not cid:
            run("INSERT INTO customers(segment_id,first_name,last_name,email,phone,address,consent_given,consent_date,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (default_segment(), first, last, email, phone, f.get("address", "").strip(), consent, now()[:10] if consent else None, now()[:10]))
            flash("Customer added.", "ok")
        else:
            old = q("SELECT consent_date FROM customers WHERE customer_id=?", (cid,), one=True) or abort(404)
            run("UPDATE customers SET first_name=?,last_name=?,email=?,phone=?,address=?,consent_given=?,consent_date=? WHERE customer_id=?",
                (first, last, email, phone, f.get("address", "").strip(), consent, (old["consent_date"] or now()[:10]) if consent else None, cid))
            flash("Customer updated.", "ok")
    except sqlite3.IntegrityError:
        flash("That email is already registered to another customer.", "err")
    return redirect(back)

@app.route("/customers/<int:cid>")
@access(*DESK)
def customer(cid):
    c = q(CUST_SQL + "WHERE c.customer_id=?", (cid,), one=True) or abort(404)
    hist = {}
    for h in appointment_rows("WHERE a.status='Completed' AND a.customer_id=? AND a.pet_id IS NOT NULL", (cid,), "ORDER BY a.appointment_datetime DESC"):
        hist.setdefault(h["pet_id"], []).append(h)
    return render_template("customer.html", c=c, clv=clv_of(cid), hist=hist,
        pets=q("SELECT *, name AS pet_name, coat AS coat_type, notes AS behavior_notes FROM pets WHERE customer_id=?", (cid,)),
        appts=appointment_rows("WHERE a.customer_id=?", (cid,), "ORDER BY a.appointment_datetime DESC LIMIT 8"),
        ints=q("SELECT i.*, u.full_name FROM interactions i LEFT JOIN users u ON u.user_id=i.user_id WHERE customer_id=? ORDER BY interaction_date DESC LIMIT 8", (cid,)),
        tix=q("SELECT t.*, u.full_name AS agent FROM tickets t LEFT JOIN users u ON u.user_id=t.assigned_to WHERE customer_id=? ORDER BY opened_at DESC", (cid,)))

@app.route("/customers/<int:cid>/toggle", methods=["POST"])
@access(*DESK)
def customer_toggle(cid):
    run("UPDATE customers SET is_active=1-is_active WHERE customer_id=?", (cid,))
    flash("Customer status updated.", "ok")
    return redirect(url_for("customer", cid=cid))

# pets: add from a customer page or from the pet profiles page; edit from the pet card
@app.route("/pets")
@access()
def pets():
    s = request.args.get("q", "").strip()
    rows = q("SELECT p.*, p.name AS pet_name, p.coat AS coat_type, p.notes AS behavior_notes, c.first_name||' '||c.last_name AS owner, c.customer_id AS cid FROM pets p JOIN customers c ON c.customer_id=p.customer_id "
             "WHERE (p.name||' '||IFNULL(p.breed,'')||' '||IFNULL(p.species,'')||' '||c.first_name||' '||c.last_name||' '||IFNULL(p.allergies,'')) LIKE ? "
             "ORDER BY p.name", ("%" + s + "%",))
    hist = {}
    for h in appointment_rows("WHERE a.status='Completed' AND a.pet_id IS NOT NULL", (), "ORDER BY a.appointment_datetime DESC"):
        hist.setdefault(h["pet_id"], []).append(h)
    return render_template("pets.html", rows=rows, hist=hist, s=s,
                           customers=q("SELECT customer_id, first_name, last_name FROM customers WHERE is_active=1 ORDER BY last_name, first_name"))

@app.route("/pets/save", methods=["POST"])
@access(*DESK)
def pet_save():
    f = request.form
    pid, cid, age = f.get("pet_id", "").strip(), f.get("customer_id", "").strip(), f.get("age", "").strip()
    back = f.get("next") or url_for("pets")
    if not back.startswith("/"): back = url_for("pets")
    if not f.get("pet_name", "").strip() or not cid or (age and (not age.isdigit() or int(age) > 40)):
        flash("Choose an owner, enter the pet name, and keep age a number from 0 to 40.", "err"); return redirect(back)
    vals = (cid, f["pet_name"].strip(), f.get("species", ""), f.get("breed", "").strip(), age_text(age), f.get("size", ""), f.get("coat_type", "").strip(),
            f.get("allergies", "").strip() or "None", f.get("medical_conditions", "").strip(), f.get("behavior_notes", "").strip(), f.get("grooming_preferences", "").strip())
    if pid:
        q("SELECT 1 FROM pets WHERE pet_id=?", (pid,), one=True) or abort(404)
        run("UPDATE pets SET customer_id=?,name=?,species=?,breed=?,age=?,size=?,coat=?,allergies=?,medical_conditions=?,notes=?,grooming_preferences=? WHERE pet_id=?", vals + (pid,))
        flash("Pet profile updated.", "ok")
    else:
        run("INSERT INTO pets(customer_id,name,species,breed,age,size,coat,allergies,medical_conditions,notes,grooming_preferences) VALUES(?,?,?,?,?,?,?,?,?,?,?)", vals)
        flash("Pet added.", "ok")
    return redirect(back)


# ---------- MODULE 3: segmentation and CLV ----------
# CLV = total price_charged on this customer's Completed appointments.
CLV_SQL = ("SELECT c.customer_id, c.first_name||' '||c.last_name AS name, c.segment_id, IFNULL(SUM(o.total_amount),0) AS clv, "
           "COUNT(DISTINCT o.appointment_id) AS visits FROM customers c LEFT JOIN orders o ON o.customer_id=c.customer_id GROUP BY c.customer_id")

def clv_of(cid):
    return one("SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE customer_id=?", (cid,))

def sync_orders(aid):
    """orders rows (one per service) exist only while an appointment is Completed; CLV is the sum of orders."""
    db().execute("DELETE FROM orders WHERE appointment_id=?", (aid,))
    db().execute("INSERT INTO orders(customer_id,product_id,quantity,total_amount,order_date,appointment_id) "
                 "SELECT a.customer_id, x.product_id, 1, x.price_charged, substr(a.appointment_datetime,1,10), a.appointment_id "
                 "FROM appointments a JOIN appointment_services x ON x.appointment_id=a.appointment_id WHERE a.appointment_id=? AND a.status='Completed'", (aid,))
    db().commit()

def recalc_segments():
    segs = q("SELECT * FROM segments ORDER BY min_clv DESC")
    for r in q(CLV_SQL):
        seg = next((s for s in segs if r["clv"] >= s["min_clv"]), segs[-1])
        db().execute("UPDATE customers SET segment_id=? WHERE customer_id=?", (seg["segment_id"], r["customer_id"]))
    db().commit()

@app.route("/segments", methods=["GET", "POST"])
@access(*DESK)
def segments():
    if request.method == "POST":
        if session["role"] == "Admin":
            for k, v in request.form.items():
                if k.startswith("min_") and v.replace(".", "", 1).isdigit():
                    run("UPDATE segments SET min_clv=? WHERE segment_id=?", (float(v), k[4:]))
            flash("Segment rules saved.", "ok")
        recalc_segments()
        flash("CLV and segments recalculated from order history.", "ok")
        return redirect(url_for("segments"))
    rows = q("SELECT t.*, sg.segment_name FROM (" + CLV_SQL + ") t LEFT JOIN segments sg ON sg.segment_id=t.segment_id ORDER BY t.clv DESC, t.name")
    counts = q("SELECT sg.*, COUNT(c.customer_id) n FROM segments sg LEFT JOIN customers c ON c.segment_id=sg.segment_id GROUP BY sg.segment_id ORDER BY sg.min_clv DESC")
    return render_template("segments.html", rows=rows, counts=counts, seg_bars=[[s["segment_name"], s["n"]] for s in counts])


# ---------- MODULE 4: sales pipeline ----------
@app.route("/pipeline", methods=["GET", "POST"])
@access(*DESK)
def pipeline():
    if request.method == "POST":
        f = request.form
        amt, close = f.get("expected_amount", ""), f.get("expected_close_date", "")
        if not f.get("customer_id") or not f.get("service_id") or not amt.replace(".", "", 1).isdigit() or (close and not parse_dt(close)):
            flash("Choose a customer and enter the expected amount as a positive number.", "err")
        else:
            run("INSERT INTO opportunities(customer_id,product_id,owner_id,stage,expected_amount,expected_close_date) VALUES(?,?,?,'Lead',?,?)",
                (f["customer_id"], f["service_id"], session["uid"], float(amt), close or None))
            flash("Opportunity added as a Lead.", "ok")
        return redirect(url_for("pipeline"))
    opps = q("SELECT o.*, c.first_name||' '||c.last_name AS cname, s.product_name AS service_name, u.full_name AS owner, "
             "(SELECT appointment_id FROM appointments a WHERE a.source_opportunity_id=o.opportunity_id) AS order_id "
             "FROM opportunities o JOIN customers c ON c.customer_id=o.customer_id LEFT JOIN products s ON s.product_id=o.product_id "
             "LEFT JOIN users u ON u.user_id=o.owner_id ORDER BY o.expected_close_date")
    return render_template("pipeline.html", stages=STAGES, opps=opps,
        customers=q("SELECT * FROM customers WHERE is_active=1 ORDER BY last_name, first_name"), services=q(SVC_SQL + " WHERE is_active=1"))

@app.route("/pipeline/<int:oid>/move", methods=["POST"])
@access(*DESK)
def opp_move(oid):
    stage = request.form.get("stage")
    o = q("SELECT * FROM opportunities WHERE opportunity_id=?", (oid,), one=True) or abort(404)
    if stage not in STAGES: abort(400)
    run("UPDATE opportunities SET stage=? WHERE opportunity_id=?", (stage, oid))
    exists = q("SELECT 1 FROM appointments WHERE source_opportunity_id=?", (oid,), one=True)
    if stage == "Won" and o["stage"] != "Won" and not exists:      # a Won opportunity creates an order (appointment)
        pet = q("SELECT pet_id FROM pets WHERE customer_id=? LIMIT 1", (o["customer_id"],), one=True)
        when = (o["expected_close_date"] or now()[:10]) + " 09:00"
        aid = run("INSERT INTO appointments(customer_id,pet_id,groomer_id,appointment_datetime,source_opportunity_id) VALUES(?,?,NULL,?,?)",
                  (o["customer_id"], pet["pet_id"] if pet else None, when, oid))
        run("INSERT INTO appointment_services VALUES(?,?,?)", (aid, o["product_id"], o["expected_amount"]))
        flash("Opportunity won - a Scheduled order was created in Appointments (assign a groomer there).", "ok")
    else:
        flash("Opportunity moved to " + stage + ".", "ok")
    return redirect(url_for("pipeline"))


# ---------- appointments (the orders that CLV is computed from) ----------
APPT_SQL = ("SELECT a.*, c.first_name||' '||c.last_name AS cname, c.consent_given, p.name AS pet_name, p.allergies, p.species, u.full_name AS groomer, "
            "(SELECT group_concat(s.product_name, ', ') FROM appointment_services x JOIN products s ON s.product_id=x.product_id WHERE x.appointment_id=a.appointment_id) AS svcs, "
            "(SELECT group_concat(x.product_id) FROM appointment_services x WHERE x.appointment_id=a.appointment_id) AS svc_ids, "
            "(SELECT SUM(price_charged) FROM appointment_services WHERE appointment_id=a.appointment_id) AS total, "
            "(SELECT SUM(s.duration_minutes) FROM appointment_services x JOIN products s ON s.product_id=x.product_id WHERE x.appointment_id=a.appointment_id) AS minutes, "
            "(SELECT 1 FROM feedback WHERE appointment_id=a.appointment_id) AS has_fb "
            "FROM appointments a JOIN customers c ON c.customer_id=a.customer_id LEFT JOIN pets p ON p.pet_id=a.pet_id LEFT JOIN users u ON u.user_id=a.groomer_id ")

def appointment_rows(where="", args=(), order="ORDER BY a.appointment_datetime DESC"):
    return q(APPT_SQL + where + " " + order, args)

def booking_error(f, ignore=None):
    """Validate a booking form. Returns (error message, clean values)."""
    cid, pid, gid, svc = f.get("customer_id"), f.get("pet_id") or None, f.get("groomer_id"), f.getlist("services")
    when = parse_dt((f.get("date", "") + " " + f.get("time", "")).strip())
    if not cid or not gid or not when or not svc:
        return "Choose a customer, a groomer, a date and start time, and at least one service.", None
    if not q("SELECT 1 FROM customers WHERE customer_id=? AND is_active=1", (cid,), one=True):
        return "That customer is missing or deactivated.", None
    if pid and not q("SELECT 1 FROM pets WHERE pet_id=? AND customer_id=?", (pid, cid), one=True):
        return "The selected pet must belong to the selected customer.", None
    if not q("SELECT 1 FROM users WHERE user_id=? AND role='Groomer' AND is_active=1", (gid,), one=True):
        return "Choose an active groomer.", None
    rows = [q("SELECT * FROM products WHERE product_id=? AND is_active=1", (s,), one=True) for s in svc]
    if not all(rows): return "One of the chosen services is not available.", None
    minutes = sum(r["duration_minutes"] for r in rows)
    start = when.hour * 60 + when.minute
    if start < OPEN_MIN or start + minutes > CLOSE_MIN:
        return "The booking ({} min) must fit within salon hours, 8:00 AM to 6:00 PM.".format(minutes), None
    for o in q("SELECT a.appointment_id, a.appointment_datetime, IFNULL((SELECT SUM(s.duration_minutes) FROM appointment_services x JOIN products s ON s.product_id=x.product_id "
               "WHERE x.appointment_id=a.appointment_id),60) AS m FROM appointments a WHERE a.groomer_id=? AND substr(a.appointment_datetime,1,10)=? AND a.status!='Canceled'",
               (gid, when.strftime("%Y-%m-%d"))):
        if str(o["appointment_id"]) == str(ignore): continue
        od = parse_dt(o["appointment_datetime"]); os_ = od.hour * 60 + od.minute
        if start < os_ + o["m"] and start + minutes > os_:
            return "That groomer already has a booking from {} to {}. Pick another slot.".format(
                _t12(od), _t12(od + timedelta(minutes=o["m"]))), None
    return None, dict(cid=cid, pid=pid, gid=gid, when=when.strftime("%Y-%m-%d %H:%M"), svc=svc, rows=rows)

@app.route("/appointments")
@access()
def appointments():
    s, st, day = request.args.get("q", "").strip(), request.args.get("status", ""), request.args.get("date", "")
    view = "month" if request.args.get("view") == "month" else "list"
    where, args = ["1=1"], []
    if session["role"] == "Groomer": where.append("a.groomer_id=?"); args.append(session["uid"])
    if s:
        where.append("(c.first_name||' '||c.last_name||' '||IFNULL(p.name,'')||' '||IFNULL(u.full_name,'')||' '||a.appointment_id||' ORD-'||printf('%03d',a.appointment_id)||' '||"
                     "IFNULL((SELECT group_concat(s.product_name,' ') FROM appointment_services x JOIN products s ON s.product_id=x.product_id WHERE x.appointment_id=a.appointment_id),'')) LIKE ?")
        args.append("%" + s + "%")
    if st in STATUSES: where.append("a.status=?"); args.append(st)
    month_start = None
    if view == "month":
        try: month_start = datetime.strptime(request.args.get("m", ""), "%Y-%m").date()
        except ValueError: month_start = date.today().replace(day=1)
    elif day: where.append("substr(a.appointment_datetime,1,10)=?"); args.append(day)
    rows = appointment_rows("WHERE " + " AND ".join(where), args, "ORDER BY a.appointment_datetime " + ("ASC" if view == "month" else "DESC") + " LIMIT 400")
    weeks, prev_m, next_m = None, None, None
    if view == "month":
        by_day = {}
        for r in rows: by_day.setdefault(r["appointment_datetime"][:10], []).append(r)
        weeks = [[(d, d.month == month_start.month, by_day.get(d.isoformat(), [])) for d in wk]
                 for wk in calendar.Calendar(firstweekday=6).monthdatescalendar(month_start.year, month_start.month)]
        prev_m = (month_start - timedelta(days=1)).replace(day=1).strftime("%Y-%m")
        next_m = (month_start + timedelta(days=32)).replace(day=1).strftime("%Y-%m")
    return render_template("appointments.html", rows=rows, view=view, weeks=weeks, month_start=month_start, prev_m=prev_m, next_m=next_m,
        f=dict(q=s, status=st, date=day), statuses=STATUSES, now_str=now(), today=date.today().isoformat(),
        pets=q("SELECT pet_id, customer_id, name AS pet_name FROM pets ORDER BY name"),
        customers=q("SELECT * FROM customers WHERE is_active=1 ORDER BY last_name, first_name"), services=q(SVC_SQL + " WHERE is_active=1"),
        groomers=q("SELECT * FROM users WHERE is_active=1 AND role='Groomer' ORDER BY full_name"),
        due=q("SELECT r.*, c.first_name||' '||c.last_name AS cname, c.consent_given FROM reminders r JOIN appointments a ON a.appointment_id=r.appointment_id "
              "JOIN customers c ON c.customer_id=a.customer_id WHERE r.status='Pending' ORDER BY r.scheduled_at LIMIT 10") if session["role"] in DESK else [])

@app.route("/appointments/save", methods=["POST"])
@access(*DESK)
def appt_save():
    f = request.form
    aid = f.get("appointment_id", "").strip()
    if aid:
        cur = q("SELECT * FROM appointments WHERE appointment_id=?", (aid,), one=True) or abort(404)
        if cur["status"] in ("Completed", "Canceled"):
            flash("Completed or canceled appointments can no longer be edited.", "err"); return redirect(url_for("appointments"))
    err, v = booking_error(f, ignore=aid or None)
    if err:
        flash(err, "err"); return redirect(request.referrer or url_for("appointments"))
    notes = f.get("groomer_notes", "").strip()
    if aid:
        old = {r["product_id"]: r["price_charged"] for r in q("SELECT * FROM appointment_services WHERE appointment_id=?", (aid,))}
        run("UPDATE appointments SET customer_id=?,pet_id=?,groomer_id=?,appointment_datetime=?,groomer_notes=? WHERE appointment_id=?", (v["cid"], v["pid"], v["gid"], v["when"], notes, aid))
        db().execute("DELETE FROM appointment_services WHERE appointment_id=?", (aid,))
        for r in v["rows"]:
            db().execute("INSERT INTO appointment_services VALUES(?,?,?)", (aid, r["product_id"], old.get(r["product_id"], r["unit_price"])))
        db().execute("UPDATE reminders SET scheduled_at=? WHERE appointment_id=? AND reminder_type='Upcoming' AND status='Pending'",
                     ((parse_dt(v["when"]) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M"), aid))
        db().commit(); flash("Appointment updated.", "ok")
    else:
        aid = run("INSERT INTO appointments(customer_id,pet_id,groomer_id,appointment_datetime,groomer_notes) VALUES(?,?,?,?,?)", (v["cid"], v["pid"], v["gid"], v["when"], notes))
        for r in v["rows"]:
            db().execute("INSERT INTO appointment_services VALUES(?,?,?)", (aid, r["product_id"], r["unit_price"]))
        db().commit()
        run("INSERT INTO reminders(appointment_id,reminder_type,scheduled_at) VALUES(?,?,?)", (aid, "Upcoming", (parse_dt(v["when"]) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")))
        flash("Appointment booked and reminder prepared.", "ok")
    return redirect(url_for("appointments"))

@app.route("/appointments/<int:aid>/status", methods=["POST"])
@access()
def appt_status(aid):
    st = request.form.get("status")
    a = q("SELECT * FROM appointments WHERE appointment_id=?", (aid,), one=True) or abort(404)
    if st not in STATUSES: abort(400)
    if session["role"] == "Groomer":      # groomers only move their own jobs forward: Scheduled -> In progress -> Completed
        if a["groomer_id"] != session["uid"] or (a["status"], st) not in (("Scheduled", "In progress"), ("In progress", "Completed")):
            flash("You can only start or complete appointments assigned to you.", "err"); return redirect(url_for("appointments"))
    run("UPDATE appointments SET status=?, groomer_notes=COALESCE(NULLIF(?,''),groomer_notes) WHERE appointment_id=?", (st, request.form.get("notes", "").strip(), aid))
    sync_orders(aid)
    if st == "Completed" and not q("SELECT 1 FROM reminders WHERE appointment_id=? AND reminder_type='Follow-up'", (aid,), one=True):
        run("INSERT INTO reminders(appointment_id,reminder_type,scheduled_at) VALUES(?,?,?)", (aid, "Follow-up", (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")))
    if st == "Canceled":
        run("DELETE FROM reminders WHERE appointment_id=? AND status='Pending' AND reminder_type='Upcoming'", (aid,))
    recalc_segments()
    flash("Appointment marked {}.".format(st.lower()), "ok")
    return redirect(request.referrer or url_for("appointments"))

@app.route("/appointments/<int:aid>/feedback", methods=["POST"])
@access(*DESK)
def appt_feedback(aid):
    f = request.form
    a = q("SELECT customer_id, status FROM appointments WHERE appointment_id=?", (aid,), one=True) or abort(404)
    if a["status"] != "Completed": flash("Feedback can only be recorded for completed appointments.", "err")
    elif q("SELECT 1 FROM feedback WHERE appointment_id=?", (aid,), one=True): flash("Feedback was already recorded for this appointment.", "err")
    elif f.get("grooming_rating") in list("12345") and f.get("service_rating") in list("12345"):
        run("INSERT INTO feedback(appointment_id,customer_id,grooming_rating,service_rating,comments,created_at) VALUES(?,?,?,?,?,?)",
            (aid, a["customer_id"], f["grooming_rating"], f["service_rating"], f.get("comments", "").strip(), now()))
        flash("Feedback saved.", "ok")
    else: flash("Ratings must be 1 to 5.", "err")
    return redirect(request.referrer or url_for("appointments"))

@app.route("/reminders/<int:rid>/sent", methods=["POST"])
@access(*DESK)
def reminder_sent(rid):
    run("UPDATE reminders SET status='Sent' WHERE reminder_id=?", (rid,)); flash("Reminder marked as sent.", "ok")
    return redirect(url_for("appointments"))

@app.route("/services")
@access()
def services():
    rows = q("SELECT s.product_id AS service_id, s.product_name AS service_name, s.category AS description, s.unit_price AS price, s.duration_minutes, (SELECT COUNT(*) FROM appointment_services x JOIN appointments a ON a.appointment_id=x.appointment_id "
             "WHERE x.product_id=s.product_id AND a.status!='Canceled') AS booked FROM products s WHERE s.is_active=1 ORDER BY s.unit_price")
    return render_template("services.html", rows=rows)

@app.route("/feedback")
@access()
def feedback():
    rows = q("SELECT f.*, c.first_name||' '||c.last_name AS cname, p.name AS pet_name, a.appointment_datetime, u.full_name AS groomer, "
             "(SELECT group_concat(s.product_name,', ') FROM appointment_services x JOIN products s ON s.product_id=x.product_id WHERE x.appointment_id=a.appointment_id) AS svcs "
             "FROM feedback f JOIN appointments a ON a.appointment_id=f.appointment_id JOIN customers c ON c.customer_id=f.customer_id "
             "LEFT JOIN pets p ON p.pet_id=a.pet_id LEFT JOIN users u ON u.user_id=a.groomer_id ORDER BY f.created_at DESC")
    pending = appointment_rows("WHERE a.status='Completed' AND NOT EXISTS (SELECT 1 FROM feedback f WHERE f.appointment_id=a.appointment_id)", (), "ORDER BY a.appointment_datetime DESC LIMIT 12") if session["role"] in DESK else []
    avg = lambda k: (sum(r[k] for r in rows) / len(rows)) if rows else None
    return render_template("feedback.html", rows=rows, pending=pending, avg_groom=avg("grooming_rating"), avg_service=avg("service_rating"))


# ---------- MODULE 5: service tickets and interactions ----------
@app.route("/service")
@access(*DESK)
def service():
    show = request.args.get("show", "open")
    where = "" if show == "all" else "WHERE t.status!='Closed'"
    return render_template("service.html", show=show,
        tickets=q("SELECT t.*, c.first_name||' '||c.last_name AS cname, u.full_name AS agent FROM tickets t JOIN customers c ON c.customer_id=t.customer_id "
                  "LEFT JOIN users u ON u.user_id=t.assigned_to " + where + " ORDER BY t.status='Closed', t.opened_at DESC"),
        ints=q("SELECT i.*, c.first_name||' '||c.last_name AS cname, u.full_name FROM interactions i JOIN customers c ON c.customer_id=i.customer_id "
               "LEFT JOIN users u ON u.user_id=i.user_id ORDER BY interaction_date DESC LIMIT 15"),
        customers=q("SELECT * FROM customers WHERE is_active=1 ORDER BY last_name, first_name"), staff=q("SELECT * FROM users WHERE is_active=1 ORDER BY full_name"))

@app.route("/interactions/new", methods=["POST"])
@access(*DESK)
def interaction_new():
    f = request.form
    if f.get("customer_id") and f.get("channel") in ("Call", "Email", "Chat", "Walk-in") and f.get("notes", "").strip():
        run("INSERT INTO interactions(customer_id,user_id,channel,notes,interaction_date) VALUES(?,?,?,?,?)",
            (f["customer_id"], session["uid"], f["channel"], f["notes"].strip(), now())); flash("Interaction logged.", "ok")
    else: flash("Choose a customer and channel, and write a note.", "err")
    return redirect(request.referrer or url_for("service"))

@app.route("/tickets/new", methods=["POST"])
@access(*DESK)
def ticket_new():
    f = request.form
    if f.get("customer_id") and f.get("subject", "").strip() and f.get("priority") in ("Low", "Medium", "High"):
        run("INSERT INTO tickets(customer_id,assigned_to,subject,priority,status,opened_at) VALUES(?,?,?,?,?,?)",
            (f["customer_id"], f.get("assigned_to") or None, f["subject"].strip(), f["priority"], "In progress" if f.get("assigned_to") else "Open", now()))
        flash("Ticket opened.", "ok")
    else: flash("Choose a customer and write a subject.", "err")
    return redirect(url_for("service"))

@app.route("/tickets/<int:tid>/assign", methods=["POST"])
@access(*DESK)
def ticket_assign(tid):
    run("UPDATE tickets SET assigned_to=?, status='In progress' WHERE ticket_id=? AND status!='Closed'", (request.form.get("assigned_to"), tid))
    flash("Ticket assigned.", "ok")
    return redirect(url_for("service"))

@app.route("/tickets/<int:tid>/close", methods=["POST"])
@access(*DESK)
def ticket_close(tid):
    score = request.form.get("csat_score", "")
    if score not in list("12345"): flash("A 1 to 5 satisfaction score is required to close a ticket.", "err")
    else:
        run("UPDATE tickets SET status='Closed', csat_score=?, closed_at=? WHERE ticket_id=?", (int(score), now(), tid)); flash("Ticket closed.", "ok")
    return redirect(url_for("service"))


# ---------- MODULE 6: dashboard and reports ----------
@app.route("/dashboard")
@access()
def dashboard():
    today, groomer = date.today().isoformat(), session["role"] == "Groomer"
    mine = " AND a.groomer_id={}".format(int(session["uid"])) if groomer else ""
    cnt = lambda cond: one("SELECT COUNT(*) FROM appointments a WHERE " + cond + mine)
    if groomer:
        kpis = [("My appointments today", cnt("substr(a.appointment_datetime,1,10)='{}' AND a.status!='Canceled'".format(today)), "▤", "Assigned to you"),
                ("Scheduled", cnt("a.status='Scheduled'"), "✓", "Ready to start"),
                ("In progress", cnt("a.status='In progress'"), "◷", "Currently being groomed"),
                ("Completed", cnt("a.status='Completed'"), "✦", "All-time completed sessions")]
        charts = {}
    else:
        won, lost = one("SELECT COUNT(*) FROM opportunities WHERE stage='Won'"), one("SELECT COUNT(*) FROM opportunities WHERE stage='Lost'")
        kpis = [("Active customers", one("SELECT COUNT(*) FROM customers WHERE is_active=1"), "♙", "Pet owners on record"),
                ("Registered pets", one("SELECT COUNT(*) FROM pets"), "♧", "Linked to owners"),
                ("Average CLV", peso(one("SELECT IFNULL(AVG(clv),0) FROM (" + CLV_SQL + ")")), "₱", "Per customer, completed orders"),
                ("Win rate", "{:.0f}%".format(100 * won / (won + lost)) if won + lost else "n/a", "⇄", "Won ÷ (Won + Lost)"),
                ("Open tickets", one("SELECT COUNT(*) FROM tickets WHERE status!='Closed'"), "✉", "Waiting for a resolution"),
                ("Avg satisfaction", "{:.1f} / 5".format(one("SELECT IFNULL(AVG(csat_score),0) FROM tickets WHERE csat_score IS NOT NULL")), "★", "From closed tickets"),
                ("Appointments today", cnt("substr(a.appointment_datetime,1,10)='{}' AND a.status!='Canceled'".format(today)), "▤", "Scheduled for today"),
                ("Upcoming appointments", cnt("a.status='Scheduled' AND substr(a.appointment_datetime,1,10)>='{}'".format(today)), "◷", "Still to come")]
        charts = {
            "services": [list(r) for r in q("SELECT s.product_name, COUNT(*) FROM appointment_services x JOIN products s ON s.product_id=x.product_id "
                                            "JOIN appointments a ON a.appointment_id=x.appointment_id WHERE a.status!='Canceled' GROUP BY s.product_id ORDER BY 2 DESC")],
            "status": [list(r) for r in q("SELECT status, COUNT(*) FROM appointments GROUP BY status ORDER BY 2 DESC")],
            "segments": [list(r) for r in q("SELECT sg.segment_name, COUNT(c.customer_id) FROM segments sg LEFT JOIN customers c ON c.segment_id=sg.segment_id GROUP BY sg.segment_id ORDER BY sg.min_clv DESC")],
        }
    upcoming = appointment_rows("WHERE a.status IN ('Scheduled','In progress')" + mine, (), "ORDER BY a.appointment_datetime LIMIT 6")
    alerts = [a for a in upcoming if a["allergies"] and a["allergies"].strip().lower() not in ("", "none", "none known")]
    return render_template("dashboard.html", kpis=kpis, charts=charts, upcoming=upcoming, alerts=alerts, now_str=now(),
                           greeting="Good morning" if datetime.now().hour < 12 else "Good afternoon" if datetime.now().hour < 18 else "Good evening")

@app.route("/reports")
@access(*DESK)
def reports():
    days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    busy = [(days[int(r[0])], r[1]) for r in q("SELECT strftime('%w',appointment_datetime), COUNT(*) FROM appointments WHERE status!='Canceled' GROUP BY 1 ORDER BY 2 DESC")]
    pop = q("SELECT s.product_name AS service_name, COUNT(*) n, SUM(x.price_charged) revenue FROM appointment_services x JOIN products s ON s.product_id=x.product_id "
            "JOIN appointments a ON a.appointment_id=x.appointment_id WHERE a.status!='Canceled' GROUP BY s.product_id ORDER BY n DESC")
    contacts = q("SELECT first_name||' '||last_name AS name, email, phone, consent_date FROM customers WHERE consent_given=1 AND is_active=1 ORDER BY last_name, first_name")
    skipped = one("SELECT COUNT(*) FROM customers WHERE consent_given=0 AND is_active=1")
    return render_template("reports.html", busy=busy, pop=pop, contacts=contacts, skipped=skipped)


# ---------- first run: create the database from schema.sql and the CSV files in seed_data/ ----------
def rows_of(name):
    with open(os.path.join(SEED, name), encoding="utf-8-sig", newline="") as fh:
        return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(fh)]

def num(ref):                       # "CUS-007" -> 7
    return int(ref.split("-")[1]) if ref else None

def init_db():
    con = sqlite3.connect(DB)
    con.executescript(open(os.path.join(BASE, "schema.sql")).read())
    # staff accounts (seed_data/salon_staff.csv holds password hashes only, never plain text)
    role_of, uid_of = {"admin": "Admin", "receptionist": "Receptionist", "groomer": "Groomer"}, {}
    for r in rows_of("salon_staff.csv"):
        cur = con.execute("INSERT INTO users(staff_code,full_name,username,email,password_hash,role,phone,specialty,experience,availability,rating,is_active,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (r["id"], r["fullName"], r["email"].split("@")[0].lower(), r["email"].lower(), r["password_hash"], role_of[r["role"]], r["phone"], r["specialty"],
             r["experience"], r["availability"], float(r["rating"]) if r["rating"] else None, 1 if r["status"] == "Active" else 0, r["createdAt"]))
        uid_of[r["id"]] = cur.lastrowid
    con.executemany("INSERT INTO segments(segment_name,min_clv,description) VALUES(?,?,?)",
        [("Standard Pup", 0, "Occasional grooming visits (CLV < ₱2,000)"), ("Silver Paw", 2000, "Regular maintenance visits (CLV ₱2,000 - ₱4,999)"),
         ("Golden VIP", 5000, "High frequency, premium grooming packages (CLV ₱5,000+)")])
    # service catalogue = the products the seed CSVs refer to (ids 1-5)
    con.executemany("INSERT INTO products(product_name,category,unit_price,duration_minutes) VALUES(?,?,?,?)",
        [("Bath & Blow Dry", "Basic Care", 450, 60), ("Full Haircut", "Full Styling", 650, 90), ("Nail Trimming", "A La Carte", 150, 20),
         ("Ear Cleaning", "A La Carte", 120, 15), ("Spa Package", "Package", 1200, 120)])
    svc = {r[1]: (r[0], r[2]) for r in con.execute("SELECT product_id, product_name, unit_price FROM products")}
    for r in rows_of("salon_customers.csv"):
        first, _, last = r["fullName"].partition(" ")
        yes = r["consent_given"].lower() == "yes"
        con.execute("INSERT INTO customers(customer_id,segment_id,first_name,last_name,email,phone,address,consent_given,consent_date,is_active,created_at) VALUES(?,1,?,?,?,?,?,?,?,?,?)",
            (num(r["id"]), first, last or "-", r["email"].lower(), r["phone"], r["address"], 1 if yes else 0, (r["consent_date"] or None) if yes else None,
             1 if r["status"] == "Active" else 0, r["createdAt"]))
    for r in rows_of("salon_pets.csv"):
        con.execute("INSERT INTO pets(pet_id,customer_id,name,species,breed,age,size,coat,allergies,medical_conditions,notes,grooming_preferences) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (num(r["pet_id"]), num(r["customer_id"]), r["pet_name"], r["species"], r["breed"], age_text(r["age_years"]), r["size"], r["coat_type"],
             r["allergies"] or "None", r["medical_conditions"], r["behavior_notes"], r["grooming_preferences"]))
    for r in rows_of("seed_opportunities.csv"):
        con.execute("INSERT INTO opportunities(opportunity_id,customer_id,product_id,owner_id,stage,expected_amount,expected_close_date) VALUES(?,?,?,?,?,?,?)",
            (num(r["opportunity_id"]), num(r["customer_id"]), int(r["service_id"]), uid_of[r["owner_id"]], r["stage"], float(r["expected_amount"]), r["expected_close_date"]))
    for r in rows_of("seed_orders.csv"):
        aid = num(r["order_id"])
        con.execute("INSERT INTO appointments(appointment_id,customer_id,pet_id,groomer_id,appointment_datetime,status,groomer_notes,source_opportunity_id) VALUES(?,?,?,?,?,?,?,?)",
            (aid, num(r["customer_id"]), num(r["pet_id"]), uid_of[r["groomer_id"]], r["appointment_datetime"], r["status"], r["groomer_notes"], num(r["source_opportunity_id"])))
        for name in [x.strip() for x in r["services"].split(";") if x.strip()]:
            con.execute("INSERT INTO appointment_services VALUES(?,?,?)", (aid, svc[name][0], svc[name][1]))
        if r["status"] == "Completed":     # completed bookings become order lines (CLV)
            con.execute("INSERT INTO orders(customer_id,product_id,quantity,total_amount,order_date,appointment_id) "
                        "SELECT customer_id, product_id, 1, price_charged, ?, ? FROM appointments a JOIN appointment_services x USING(appointment_id) WHERE appointment_id=?",
                        (r["appointment_datetime"][:10], aid, aid))
        if r["status"] == "Scheduled":     # same reminder the booking screen prepares: one day before
            con.execute("INSERT INTO reminders(appointment_id,reminder_type,scheduled_at) VALUES(?,?,?)",
                        (aid, "Upcoming", (parse_dt(r["appointment_datetime"]) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")))
    for r in rows_of("seed_interactions.csv"):
        con.execute("INSERT INTO interactions(interaction_id,customer_id,user_id,channel,notes,interaction_date,related_ref) VALUES(?,?,?,?,?,?,?)",
            (num(r["interaction_id"]), num(r["customer_id"]), uid_of[r["user_id"]], r["channel"], r["notes"], r["interaction_date"], r["related_ref"]))
    for r in rows_of("seed_tickets.csv"):
        con.execute("INSERT INTO tickets(ticket_id,customer_id,assigned_to,subject,priority,status,csat_score,opened_at,closed_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (num(r["ticket_id"]), num(r["customer_id"]), uid_of.get(r["assigned_to"]), r["subject"], r["priority"], r["status"],
             int(float(r["csat_score"])) if r["csat_score"] else None, r["opened_at"], r["closed_at"] or None))
    con.commit(); con.close()
    with app.app_context(): recalc_segments()

if not os.path.exists(DB): init_db()
if __name__ == "__main__":
    app.run(debug=True)
