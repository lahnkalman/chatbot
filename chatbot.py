from openai import OpenAI
import json
from datetime import datetime
import os

client = OpenAI()

# ===== קובץ יומן =====
HISTORY_FILE = "history.json"

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_to_history(profile, allocation, notes):
    history = load_history()
    history.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "profile": profile,
        "allocation": allocation,
        "notes": notes
    })
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# ===== מצב =====
portfolio = {
    "profile": None,
    "allocation": None,
    "notes": None
}

# ===== עזר =====
def ask_choice(prompt, choices):
    while True:
        print(prompt)
        for k, v in choices.items():
            print(f"{k}) {v}")
        ans = input("בחר מספר: ").strip()
        if ans in choices:
            return choices[ans]
        print("❌ לא הבנתי. נסה שוב.\n")

def ask_int(prompt, min_val=None, max_val=None):
    while True:
        ans = input(prompt).strip().replace(",", "")
        if ans.isdigit():
            val = int(ans)
            if (min_val is None or val >= min_val) and (max_val is None or val <= max_val):
                return val
        print("❌ מספר לא תקין. נסה שוב.\n")

def round_amount(x, step=100):
    return int(round(x / step) * step)

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

# ===== לוגיקת הקצאה =====
def compute_allocation(amount, years, risk, liquidity, goal, experience):

    equity_pct = {"נמוך": 0.30, "בינוני": 0.55, "גבוה": 0.80}[risk]

    if years <= 2:
        equity_pct -= 0.20
    elif years <= 5:
        equity_pct -= 0.10
    elif years >= 10:
        equity_pct += 0.05

    equity_pct -= {"גבוהה": 0.15, "בינונית": 0.05, "נמוכה": 0}[liquidity]
    equity_pct += {
        "שמירה על ערך (שמרני)": -0.10,
        "איזון (ביניים)": 0,
        "צמיחה (אגרסיבי)": 0.05
    }[goal]

    equity_pct = clamp(equity_pct, 0.10, 0.90)

    cash_pct = {"גבוהה": 0.20, "בינונית": 0.10, "נמוכה": 0.05}[liquidity]
    if years <= 2:
        cash_pct += 0.10
    cash_pct = clamp(cash_pct, 0.05, 0.35)

    bonds_pct = 1.0 - equity_pct - cash_pct

    equity_amount = amount * equity_pct
    cash_amount = amount * cash_pct
    bonds_amount = amount * bonds_pct

    stocks_amount = equity_amount * (0.10 if experience != "מתחיל" and risk != "נמוך" else 0)
    broad_amount = equity_amount - stocks_amount

    allocation = {
        "קרנות סל רחבות (גלובלי)": round_amount(broad_amount * 0.75),
        "קרנות סל רחבות (מקומי)": round_amount(broad_amount * 0.25),
        "מניות/סקטורים (מדומה)": round_amount(stocks_amount),
        "אג\"ח/סולידי": round_amount(bonds_amount),
        "מזומן/נזיל": round_amount(cash_amount)
    }

    total = sum(allocation.values())
    allocation["מזומן/נזיל"] += amount - total

    return {k: v for k, v in allocation.items() if v != 0}

# ===== Compare =====
def compute_allocation_variant(profile, forced_risk):
    return compute_allocation(
        amount=profile["amount"],
        years=profile["years"],
        risk=forced_risk,
        liquidity=profile["liquidity"],
        goal=profile["goal"],
        experience=profile["experience"]
    )

# ===== What-If =====
def compute_whatif(profile, field, new_value):
    updated = profile.copy()
    updated[field] = new_value
    return compute_allocation(
        amount=updated["amount"],
        years=updated["years"],
        risk=updated["risk"],
        liquidity=updated["liquidity"],
        goal=updated["goal"],
        experience=updated["experience"]
    )

# ===== AI הסבר =====
def explain_with_ai(profile, allocation):
    resp = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": "הסבר לימודי קצר על הקצאת נכסים. עד 4 משפטים."},
            {"role": "user", "content": f"פרופיל: {profile}\nהקצאה: {allocation}"}
        ]
    )
    return resp.output_text.strip()

# ===== פונקציה ל-Web =====
def run_engine(profile):
    allocation = compute_allocation(
        amount=profile["amount"],
        years=profile["years"],
        risk=profile["risk"],
        liquidity=profile["liquidity"],
        goal=profile["goal"],
        experience=profile["experience"]
    )

    conservative = compute_allocation_variant(profile, "נמוך")
    aggressive = compute_allocation_variant(profile, "גבוה")

    return {
        "allocation": allocation,
        "conservative": conservative,
        "aggressive": aggressive
    }

# ===== CLI (רק כשמריצים ישירות) =====
if __name__ == "__main__":

    print("🤖 סוכן הקצאה לימודי (כסף מדומה).")
    print("פקודות: profile | compare | whatif | status | reset | help | exit\n")

    while True:
        cmd = input("אתה: ").strip()

        if not cmd:
            continue

        c = cmd.lower()

        if c == "exit":
            print("👋 יציאה")
            break

        if c == "help":
            print("profile | compare | whatif | status | reset | exit\n")
            continue

        if c == "reset":
            portfolio = {"profile": None, "allocation": None, "notes": None}
            print("🔄 אופס.\n")
            continue

        if c == "status":
            if not portfolio["profile"]:
                print("אין פרופיל פעיל.\n")
                continue
            print(portfolio)
            continue

        if c == "compare":
            if not portfolio["profile"]:
                print("❌ אין פרופיל להשוואה.\n")
                continue

            base = portfolio["profile"]
            cons = compute_allocation_variant(base, "נמוך")
            aggr = compute_allocation_variant(base, "גבוה")

            print("\n🟢 שמרני:")
            for k, v in cons.items():
                print(f"- {k}: {v} ש\"ח")

            print("\n🔴 אגרסיבי:")
            for k, v in aggr.items():
                print(f"- {k}: {v} ש\"ח")
            print()
            continue

        if c.startswith("whatif"):
            if not portfolio["profile"]:
                print("❌ אין פרופיל פעיל.\n")
                continue

            parts = cmd.split()
            if len(parts) < 3:
                print("שימוש: whatif <risk|years|liquidity|goal> <value>\n")
                continue

            field = parts[1]
            value = " ".join(parts[2:])

            if field == "years":
                if not value.isdigit():
                    print("❌ years חייב להיות מספר.\n")
                    continue
                value = int(value)

            new_alloc = compute_whatif(portfolio["profile"], field, value)

            print("\n🔄 What-If:")
            for k, v in new_alloc.items():
                print(f"- {k}: {v} ש\"ח")
            print()
            continue

        if c == "profile":
            amount = ask_int("כמה כסף? ")
            years = ask_int("לכמה שנים? ")

            risk = ask_choice("רמת סיכון?", {"1": "נמוך", "2": "בינוני", "3": "גבוה"})
            liquidity = ask_choice("נזילות?", {"1": "גבוהה", "2": "בינונית", "3": "נמוכה"})
            goal = ask_choice("יעד?", {
                "1": "שמירה על ערך (שמרני)",
                "2": "איזון (ביניים)",
                "3": "צמיחה (אגרסיבי)"
            })
            experience = ask_choice("ניסיון?", {"1": "מתחיל", "2": "בינוני", "3": "מנוסה"})

            profile = {
                "amount": amount,
                "years": years,
                "risk": risk,
                "liquidity": liquidity,
                "goal": goal,
                "experience": experience
            }

            allocation = compute_allocation(amount, years, risk, liquidity, goal, experience)
            notes = explain_with_ai(profile, allocation)

            portfolio["profile"] = profile
            portfolio["allocation"] = allocation
            portfolio["notes"] = notes

            save_to_history(profile, allocation, notes)

            print("\n📊 הקצאה:")
            for k, v in allocation.items():
                print(f"- {k}: {v} ש\"ח")
            print("\n🧠", notes, "\n")
            continue

        print("❌ פקודה לא מוכרת.\n")
