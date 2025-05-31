import csv

# =============================
# Account Management Functions
# =============================

def load_cash(filename="account.csv"):
    with open(filename, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            return float(row['Cash'])
    return 0.0

def save_cash(cash, filename="account.csv"):
    with open(filename, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['Cash'])
        writer.writeheader()
        writer.writerow({'Cash': cash})
