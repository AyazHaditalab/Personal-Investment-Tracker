from db import get_conn, init_db

init_db()

def load_cash() -> float:
    with get_conn() as conn:
        row = conn.execute("SELECT cash FROM account WHERE id = 1").fetchone()
        return float(row["cash"]) if row else 0.0

def _set_cash(new_cash: float):
    with get_conn() as conn:
        conn.execute("UPDATE account SET cash = ? WHERE id = 1", (float(new_cash),))
        conn.commit()

def log_cash_event(event: str, amount: float, ticker=None, shares=None, price=None):
    """
    amount: signed cash delta
      deposit: +amount
      withdraw: -amount
      buy: -cost
      sell: +proceeds
    """
    cash_before = load_cash()
    cash_after = cash_before + float(amount)
    _set_cash(cash_after)

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO cash_ledger (event, ticker, shares, price, amount, balance_after)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event, ticker, shares, price, float(amount), float(cash_after)),
        )
        conn.commit()

# Backwards-compatible helper (if you still call save_cash somewhere)
def save_cash(cash: float):
    """
    Sets cash directly (no ledger entry). Prefer log_cash_event() for real usage.
    """
    _set_cash(float(cash))
