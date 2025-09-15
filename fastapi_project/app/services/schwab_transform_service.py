
"""
Schwab Data Transformation Service

Transforms Schwab API JSON data (accounts, positions, orders, transactions)
into Allocraft's internal models: stocks, options, wheels, cash balance, transactions, and orders.

Input: Schwab JSON (as loaded from API or file)
Output: Allocraft ORM objects (Stock, Option, WheelCycle, etc.)
"""

from typing import Any, Dict, List



def transform_accounts(json_data: Any) -> List[Dict[str, Any]]:
	"""Transform Schwab accounts JSON to Allocraft SchwabAccount dicts. Handles dict or list root."""
	accounts = []
	# If root is a dict with 'accounts', use it; if it's a list, treat as list of accounts
	if isinstance(json_data, dict) and "accounts" in json_data:
		account_list = json_data["accounts"]
	elif isinstance(json_data, list):
		account_list = json_data
	else:
		account_list = []
	for acct in account_list:
		account = {
			"account_number": acct.get("accountNumber") or acct.get("accountId"),
			"account_type": acct.get("type"),
			"cash_balance": acct.get("cashBalance", 0.0),
			"buying_power": acct.get("buyingPower", 0.0),
			"total_value": acct.get("liquidationValue", 0.0),
			"day_trading_buying_power": acct.get("dayTradingBuyingPower", 0.0),
			"is_day_trader": acct.get("isDayTrader", False),
			"raw_data": acct,
		}
		accounts.append(account)
	return accounts



def transform_positions(json_data: Any) -> List[Dict[str, Any]]:
	"""Transform Schwab positions JSON to Allocraft Stock/Option dicts. Handles dict or list root."""
	positions = []
	# If root is a dict with 'accounts', use it; if it's a list, treat as list of accounts
	if isinstance(json_data, dict) and "accounts" in json_data:
		account_list = json_data["accounts"]
	elif isinstance(json_data, list):
		account_list = json_data
	else:
		account_list = []
	for acct in account_list:
		for pos in acct.get("positions", []):
			asset_type = pos.get("assetType")
			base = {
				"symbol": pos.get("symbol"),
				"asset_type": asset_type,
				"quantity": pos.get("quantity", 0.0),
				"cost_basis": pos.get("costBasis", 0.0),
				"market_value": pos.get("marketValue", 0.0),
				"long_quantity": pos.get("longQuantity", 0.0),
				"short_quantity": pos.get("shortQuantity", 0.0),
				"current_day_profit_loss": pos.get("currentDayProfitLoss", 0.0),
				"current_day_profit_loss_percentage": pos.get("currentDayProfitLossPercentage", 0.0),
				"raw_data": pos,
			}
			if asset_type == "OPTION":
				base.update({
					"underlying_symbol": pos.get("underlyingSymbol"),
					"option_type": pos.get("putCall"),
					"strike_price": pos.get("strikePrice"),
					"expiration_date": pos.get("expirationDate"),
					"option_deliverables": pos.get("optionDeliverables"),
					"description": pos.get("description"),
				})
			positions.append(base)
	return positions



def transform_orders(json_data: Any) -> List[Dict[str, Any]]:
	"""Transform Schwab orders JSON to Allocraft Order dicts. Handles dict or list root."""
	orders = []
	# If root is a dict with 'orders', use it; if it's a list, treat as list of orders
	if isinstance(json_data, dict) and "orders" in json_data:
		order_list = json_data["orders"]
	elif isinstance(json_data, list):
		order_list = json_data
	else:
		order_list = []
	for order in order_list:
		base = {
			"order_id": order.get("orderId"),
			"account_number": order.get("accountNumber"),
			"order_type": order.get("orderType"),
			"status": order.get("status"),
			"entered_time": order.get("enteredTime"),
			"close_time": order.get("closeTime"),
			"price": order.get("price"),
			"raw_data": order,
		}
		legs = []
		for leg in order.get("orderLegCollection", []):
			legs.append({
				"order_leg_type": leg.get("orderLegType"),
				"instrument": leg.get("instrument"),
				"instruction": leg.get("instruction"),
				"quantity": leg.get("quantity"),
			})
		base["order_legs"] = legs
		orders.append(base)
	return orders




def transform_transactions(json_data: Any) -> List[Dict[str, Any]]:
	"""Transform Schwab transactions JSON to Allocraft transaction dicts, tagging wheel-related events."""
	transactions = []
	# Schwab format: { 'transactions': [ ... ] } or list root
	if isinstance(json_data, dict) and "transactions" in json_data:
		tx_list = json_data["transactions"]
	elif isinstance(json_data, list):
		tx_list = json_data
	else:
		tx_list = []
	for tx in tx_list:
		# Extract core fields
		symbol = tx.get("symbol") or tx.get("underlyingSymbol")
		action = tx.get("transactionType") or tx.get("action")
		subcode = tx.get("subCode") or tx.get("subcode")
		quantity = tx.get("quantity", 0)
		description = tx.get("description", "")
		amount = tx.get("amount", 0.0)
		date = tx.get("transactionDate") or tx.get("date")
		# Wheel event tagging logic
		wheel_event = None
		# Normalize action/description for robust matching
		desc = description.lower()
		act = (action or "").lower()
		sub = (subcode or "").lower()
		if ("put" in desc and "sell to open" in desc) or (act == "sell" and "put" in desc):
			wheel_event = "put_sold_to_open"
		elif ("put" in desc and "buy to close" in desc) or (act == "buy" and "put" in desc):
			wheel_event = "put_bought_to_close"
		elif ("call" in desc and "sell to open" in desc) or (act == "sell" and "call" in desc):
			wheel_event = "call_sold_to_open"
		elif ("call" in desc and "buy to close" in desc) or (act == "buy" and "call" in desc):
			wheel_event = "call_bought_to_close"
		elif "assigned" in desc or "assignment" in desc or "exercise" in desc:
			if "put" in desc:
				wheel_event = "put_assigned"
			elif "call" in desc:
				wheel_event = "call_assigned"
		elif ("bought" in desc or act == "buy") and quantity == 100:
			wheel_event = "stock_bought_100"
		elif ("sold" in desc or act == "sell") and quantity == 100:
			wheel_event = "stock_sold_100"
		elif "expired" in desc:
			wheel_event = "option_expired"
		# Add more rules as needed
		transactions.append({
			"symbol": symbol,
			"action": action,
			"subcode": subcode,
			"quantity": quantity,
			"description": description,
			"amount": amount,
			"date": date,
			"wheel_event": wheel_event,
			"raw_data": tx
		})
	return transactions
	"""Transform Schwab transactions JSON to Allocraft Transaction dicts. Handles dict or list root."""
	txns = []
	# If root is a dict with 'transactions', use it; if it's a list, treat as list of transactions
	if isinstance(json_data, dict) and "transactions" in json_data:
		txn_list = json_data["transactions"]
	elif isinstance(json_data, list):
		txn_list = json_data
	else:
		txn_list = []
	for txn in txn_list:
		txns.append({
			"transaction_id": txn.get("transactionId"),
			"account_number": txn.get("accountNumber"),
			"type": txn.get("type"),
			"amount": txn.get("amount"),
			"date": txn.get("date"),
			"description": txn.get("description"),
			"raw_data": txn,
		})
	return txns


def transform_wheels(json_data: Dict[str, Any]) -> List[Dict[str, Any]]:
	"""
	Transform Schwab data to Allocraft WheelCycle and WheelEvent dicts.
	Groups related option and stock trades into wheel cycles/events using wheel_event tags.
	"""
	# Step 1: Get all transactions with wheel_event tags
	transactions = transform_transactions(json_data)
	cycles = []
	current_cycle = None
	cycle_id = 1

	for tx in transactions:
		we = tx.get("wheel_event")
		if we == "put_sold_to_open":
			# Start a new wheel cycle
			if current_cycle:
				cycles.append(current_cycle)
			current_cycle = {
				"cycle_id": cycle_id,
				"symbol": tx["symbol"],
				"events": [
					{"type": we, "tx": tx}
				],
				"status": "Open"
			}
			cycle_id += 1
		elif current_cycle and we:
			# Add event to current cycle if symbol matches
			if tx["symbol"] == current_cycle["symbol"]:
				current_cycle["events"].append({"type": we, "tx": tx})
				# End cycle on assignment, call away, or stock sale
				if we in ("put_assigned", "call_assigned", "stock_sold_100", "option_expired"):
					current_cycle["status"] = "Closed"
					cycles.append(current_cycle)
					current_cycle = None
	# If a cycle is still open at the end, add it
	if current_cycle:
		cycles.append(current_cycle)
	return cycles
