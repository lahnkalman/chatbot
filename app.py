from flask import Flask, render_template, request
from openai import OpenAI
import json
import os
from datetime import datetime

app = Flask(__name__)
client = OpenAI()

HISTORY_FILE = "history.json"

# ---------- מנוע הקצאה ----------

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def round_amount(x, step=100):
    return int(round(x / step) * step)

def run_engine(profile):
    amount = profile["amount"]
    years = profile["years"]
    risk = profile["risk"]
    liquidity = profile["liquidity"]
    goal = profile["goal"]
    experience = profile["experience"]

    if risk == "נמוך":
        equity_pct = 0.30
    elif risk == "בינוני":
        equity_pct = 0.55
    else:
        equity_pct = 0.80

    if years <= 2:
        equity_pct -= 0.20
    elif years <= 5:
        equity_pct -= 0.10
    elif years >= 10:
        equity_pct += 0.05

    if liquidity == "גבוהה":
        equity_pct -= 0.15
    elif liquidity == "בינונית":
        equity_pct -= 0.05

    if goal == "שמירה על ערך (שמרני)":
        equity_pct -= 0.10
    elif goal == "צמיחה (אגרסיבי)":
        equity_pct += 0.05

    equity_pct = clamp(equity_pct, 0.10, 0.90)

    if liquidity == "גבוהה":
        cash_pct = 0.20
    elif liquidity == "בינונית":
        cash_pct = 0.10
    else:
        cash_pct = 0.05

    if years <= 2:
        cash_pct += 0.10

    cash_pct = clamp(cash_pct, 0.05, 0.35)
    bonds_pct = 1 - equity_pct - cash_pct

    if bonds_pct < 0.05:
        delta = 0.05 - bonds_pct
        equity_pct -= delta
        bonds_pct = 1 - equity_pct - cash_pct

    allow_stocks = experience != "מתחיל" and risk != "נמוך"
    stocks_pct = 0.10 if allow_stocks else 0
    broad_pct = 1 - stocks_pct

    global_pct = 0.75
    local_pct = 0.25

    equity_amt = amount * equity_pct
    cash_amt = amount * cash_pct
    bonds_amt = amount * bonds_pct

    stocks_amt = equity_amt * stocks_pct
    broad_amt = equity_amt * broad_pct

    global_amt = broad_amt * global_pct
    local_amt = broad_amt * local_pct

    allocation = {
        "קרנות סל רחבות (גלובלי)": round_amount(global_amt),
        "קרנות סל רחבות (מקומי)": round_amount(local_amt),
        "מניות/סקטורים (מדומה)": round_amount(stocks_amt),
        "אג\"ח/סולידי": round_amount(bonds_amt),
        "מזומן/נזיל": round_amount(cash_amt),
    }

    total = sum(allocation.values())
    allocation["מזומן/נזיל"] += amount - total

    return allocation

# ---------- הסבר עם AI ----------

def explain(profile, allocation):
    system = "אתה מסביר הקצאת נכסים לימודית. בלי ייעוץ. עד 4 משפטים."
    alloc = "\n".join([f"{k}: {v}" for k, v in allocation.items()])

    user = f"""
סכום: {profile['amount']}
טווח: {profile['years']}
סיכון: {profile['risk']}
נזילות: {profile['liquidity']}
יעד: {profile['goal']}
ניסיון: {profile['experience']}

הקצאה:
{alloc}

תן הסבר קצר.
"""

    r = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
    )
    return r.output_text

# ---------- היסטוריה ----------

def save_history(profile, allocation, notes):
    data = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    data.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "profile": profile,
        "allocation": allocation,
        "notes": notes
    })

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- Routes ----------

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    profile = None
    notes = None

    if request.method == "POST":
        profile = {
            "amount": int(request.form["amount"]),
            "years": int(request.form["years"]),
            "risk": request.form["risk"],
            "liquidity": request.form["liquidity"],
            "goal": request.form["goal"],
            "experience": request.form["experience"]
        }

        result = run_engine(profile)

        try:
            notes = explain(profile, result)
        except Exception:
            notes = "לא הצלחתי להביא הסבר מה-AI כרגע, אבל ההקצאה חושבה מקומית."

        save_history(profile, result, notes)

    return render_template("index.html", result=result, profile=profile, notes=notes)

@app.route("/history")
def history():
    if not os.path.exists(HISTORY_FILE):
        return "No history yet"
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return render_template("history.html", data=data)

# ---------- RUN ----------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
