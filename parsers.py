"""Spreadsheet parsing for Ultron.

These are the pure functions behind the app: they take the columns and rows of
an uploaded spreadsheet and turn them into structured, validated results. They
have no Flask or API dependencies, so they're fast to unit-test (see tests/).

The core trick is fuzzy column auto-mapping: real-world exports never use the
same header names, so each parser guesses which column means what from a list
of keywords.
"""


def make_col_finder(columns):
    """Return a function that finds the first column whose header contains any
    of the given keywords (case-insensitive)."""
    lowered = [str(c).lower().strip() for c in columns]

    def find_col(keywords):
        for kw in keywords:
            for i, header in enumerate(lowered):
                if kw in header:
                    return columns[i]
        return None

    return find_col


def _get(row, col):
    return str(row.get(col, "")).strip() if col else ""


def parse_sales_order(columns, rows):
    """Map rows to sales-order fields and validate required ones."""
    find_col = make_col_finder(columns)
    mapping = {
        "customer": find_col(["customer", "client", "buyer", "name"]),
        "item": find_col(["item", "code", "sku", "product"]),
        "description": find_col(["description", "desc", "detail"]),
        "qty": find_col(["qty", "quantity", "amount", "units"]),
        "rate": find_col(["rate", "price", "unit price", "cost"]),
        "date": find_col(["date", "order date", "so date"]),
        "po": find_col(["po", "purchase order", "po number"]),
    }

    orders = []
    for i, row in enumerate(rows):
        order = {field: _get(row, col) for field, col in mapping.items()}
        errors = []
        if not order["customer"]:
            errors.append("Missing customer name")
        if not order["item"]:
            errors.append("Missing item/stock code")
        if not order["qty"]:
            errors.append("Missing quantity")
        elif not _is_number(order["qty"]):
            errors.append(f"Invalid quantity: {order['qty']}")
        order["row"] = i + 2  # +2: header row + 1-indexing, matches the sheet
        order["errors"] = errors
        order["valid"] = not errors
        orders.append(order)

    valid = sum(1 for o in orders if o["valid"])
    return {
        "mapping": mapping,
        "orders": orders,
        "valid_count": valid,
        "invalid_count": len(orders) - valid,
        "ready_to_import": valid,
        "summary": f"{valid} orders ready, {len(orders) - valid} have issues",
    }


def parse_item_codes(columns, rows):
    """Parse a stock/item-code list and flag duplicate codes."""
    find_col = make_col_finder(columns)
    mapping = {
        "category": find_col(["category", "cat", "metal", "type"]),
        "code": find_col(["code", "item", "id", "sku"]),
        "description": find_col(["description", "desc", "name"]),
        "type1": find_col(["type1", "type 1", "class1"]),
        "type2": find_col(["type2", "type 2", "class2"]),
    }

    codes = []
    seen = {}
    duplicates = []
    for i, row in enumerate(rows):
        entry = {field: _get(row, col) for field, col in mapping.items()}
        entry["row"] = i + 2
        code = entry["code"]
        if code:
            if code in seen:
                duplicates.append({"code": code, "rows": [seen[code], i + 2]})
            else:
                seen[code] = i + 2
        codes.append(entry)

    return {
        "mapping": mapping,
        "codes": codes,
        "total": len(codes),
        "duplicates": duplicates,
        "duplicate_count": len(duplicates),
        "summary": f"{len(codes)} item codes found, {len(duplicates)} duplicates",
    }


def parse_inventory(columns, rows):
    """Parse inventory and flag items at or below their reorder point."""
    find_col = make_col_finder(columns)
    mapping = {
        "item": find_col(["item", "code", "sku"]),
        "description": find_col(["description", "desc", "name"]),
        "qty": find_col(["qty", "quantity", "on hand", "stock"]),
        "reorder": find_col(["reorder", "min", "minimum", "threshold"]),
        "cost": find_col(["cost", "unit cost", "price"]),
        "location": find_col(["location", "warehouse", "vault", "bin"]),
    }

    items = []
    low_stock = []
    for i, row in enumerate(rows):
        item = {field: _get(row, col) for field, col in mapping.items()}
        item["row"] = i + 2
        qty = _to_float(item["qty"])
        reorder = _to_float(item["reorder"])
        item["qty_num"] = qty
        item["reorder_num"] = reorder
        item["low_stock"] = reorder > 0 and qty <= reorder
        if item["low_stock"]:
            low_stock.append(item)
        items.append(item)

    return {
        "mapping": mapping,
        "items": items,
        "total": len(items),
        "low_stock": low_stock,
        "low_stock_count": len(low_stock),
        "summary": f"{len(items)} items, {len(low_stock)} below reorder point",
    }


def find_duplicates(columns, rows):
    """Flag rows that repeat on name + amount + date."""
    find_col = make_col_finder(columns)
    name_col = find_col(["name", "customer", "vendor", "item", "code", "description"])
    amount_col = find_col(["amount", "total", "rate", "price", "cost"])
    date_col = find_col(["date", "transaction date", "order date"])

    seen = {}
    duplicates = []
    for i, row in enumerate(rows):
        parts = []
        if name_col:
            parts.append(_get(row, name_col).lower())
        if amount_col:
            parts.append(_get(row, amount_col))
        if date_col:
            parts.append(_get(row, date_col))
        key = "|".join(parts)
        if key and key in seen:
            duplicates.append({
                "row": i + 2,
                "matches_row": seen[key],
                "key": key,
                "data": {c: str(row.get(c, "")) for c in columns[:5]},
            })
        elif key:
            seen[key] = i + 2

    return {
        "duplicates": duplicates,
        "duplicate_count": len(duplicates),
        "total_rows": len(rows),
        "summary": f"{len(duplicates)} duplicate rows found out of {len(rows)} total",
    }


def _is_number(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _to_float(value):
    try:
        return float(value) if value else 0.0
    except (TypeError, ValueError):
        return 0.0
