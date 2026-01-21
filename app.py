from flask import Flask, render_template, request
from chatbot import run_engine, compute_allocation_variant
import json
import os

app = Flask(__name__)

HISTORY_FILE = "history.json"


# ===== מסך ראשי =====
@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    profile = None
    whatif = None

    if request.method == "POST":
        profile = {
            "amount": int(request.form["amount"]),
            "years": int(request.form["years"]),
            "risk": request.form["risk"],
            "liquidity": request.form["liquidity"],
            "goal": request.form["goal"],
            "experience": request.form["experience"]
        }

        # חישוב בסיסי + שמרני + אגרסיבי
        result = run_engine(profile)

        # What-If (שינוי סיכון)
        if "whatif" in request.form:
            if request.form["whatif"] == "up":
                whatif = compute_allocation_variant(profile, "גבוה")
            elif request.form["whatif"] == "down":
                whatif = compute_allocation_variant(profile, "נמוך")

    return render_template(
        "index.html",
        result=result,
        profile=profile,
        whatif=whatif
    )


# ===== היסטוריה =====
@app.route("/history")
def history():
    if not os.path.exists(HISTORY_FILE):
        data = []
    else:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    return render_template("history.html", history=data)


# ===== טעינת תיק מההיסטוריה =====
@app.route("/load/<int:idx>")
def load(idx):
    if not os.path.exists(HISTORY_FILE):
        return "No history", 404

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if idx < 0 or idx >= len(data):
        return "Invalid index", 404

    profile = data[idx]["profile"]
    result = run_engine(profile)

    return render_template(
        "index.html",
        result=result,
        profile=profile,
        whatif=None
    )


# ===== הרצה =====
if __name__ == "__main__":
    app.run(debug=True)
