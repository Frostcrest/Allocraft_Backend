import json
from pathlib import Path
from schwab_transform_service import transform_accounts, transform_positions, transform_orders, transform_transactions

# Paths to Schwab JSON samples
SCHWAB_JSON_DIR = Path("../../../../docs/development/import-page-schwab-json-import/schwab-api-responses")

# Helper to load JSON

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    # Test accounts/positions
    accounts_path = SCHWAB_JSON_DIR / "accounts" / "accounts.json"
    positions_path = SCHWAB_JSON_DIR / "accounts" / "accounts_positions.json"
    account_numbers_path = SCHWAB_JSON_DIR / "accounts" / "accountNumbers.json"
    orders_path = SCHWAB_JSON_DIR / "orders" / "orders.json"
    account_orders_path = SCHWAB_JSON_DIR / "orders" / "account_orders.json"
    transactions_path = SCHWAB_JSON_DIR / "transactions" / "transactions.json"

    # Load and transform
    accounts_json = load_json(accounts_path)
    positions_json = load_json(positions_path)
    account_numbers_json = load_json(account_numbers_path)
    orders_json = load_json(orders_path)
    account_orders_json = load_json(account_orders_path)
    transactions_json = load_json(transactions_path)

    # Transform
    accounts = transform_accounts(accounts_json)
    positions = transform_positions(positions_json)
    orders = transform_orders(orders_json)
    account_orders = transform_orders(account_orders_json)
    transactions = transform_transactions(transactions_json)

    # Print summary
    print(f"Accounts: {len(accounts)}")
    print(f"Positions: {len(positions)}")
    print(f"Orders: {len(orders)}")
    print(f"Account Orders: {len(account_orders)}")
    print(f"Transactions: {len(transactions)}")
    print("Sample Account:", accounts[0] if accounts else None)
    print("Sample Position:", positions[0] if positions else None)
    print("Sample Order:", orders[0] if orders else None)
    print("Sample Transaction:", transactions[0] if transactions else None)

if __name__ == "__main__":
    main()
