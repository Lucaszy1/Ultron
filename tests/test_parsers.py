"""Unit tests for the spreadsheet parsers (no Flask/API needed)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers import (find_duplicates, make_col_finder, parse_inventory,
                     parse_item_codes, parse_sales_order)


def test_column_finder_is_fuzzy_and_case_insensitive():
    find = make_col_finder(["Customer Name", "Unit Price", "QTY"])
    assert find(["customer"]) == "Customer Name"
    assert find(["rate", "price"]) == "Unit Price"
    assert find(["qty"]) == "QTY"
    assert find(["nonexistent"]) is None


def test_sales_order_maps_and_validates():
    cols = ["Customer", "Item", "Qty", "Rate"]
    rows = [
        {"Customer": "Acme", "Item": "G5L63", "Qty": "2", "Rate": "100"},
        {"Customer": "", "Item": "S1OZ", "Qty": "x", "Rate": "25"},  # bad: no customer, bad qty
    ]
    out = parse_sales_order(cols, rows)
    assert out["valid_count"] == 1
    assert out["invalid_count"] == 1
    bad = out["orders"][1]
    assert "Missing customer name" in bad["errors"]
    assert any("Invalid quantity" in e for e in bad["errors"])
    assert out["orders"][0]["row"] == 2  # header + 1-indexed


def test_item_codes_flags_duplicates():
    cols = ["Code", "Description"]
    rows = [{"Code": "G5L63", "Description": "Gold $5"},
            {"Code": "S1OZ", "Description": "Silver 1oz"},
            {"Code": "G5L63", "Description": "Gold $5 dup"}]
    out = parse_item_codes(cols, rows)
    assert out["total"] == 3
    assert out["duplicate_count"] == 1
    assert out["duplicates"][0]["code"] == "G5L63"


def test_inventory_flags_low_stock():
    cols = ["Item", "Qty", "Reorder"]
    rows = [{"Item": "A", "Qty": "3", "Reorder": "5"},   # low
            {"Item": "B", "Qty": "10", "Reorder": "5"},  # ok
            {"Item": "C", "Qty": "0", "Reorder": "0"}]   # reorder 0 -> not flagged
    out = parse_inventory(cols, rows)
    assert out["low_stock_count"] == 1
    assert out["low_stock"][0]["item"] == "A"


def test_find_duplicates_on_name_amount_date():
    cols = ["Vendor", "Amount", "Date"]
    rows = [{"Vendor": "ACME", "Amount": "100", "Date": "2026-01-01"},
            {"Vendor": "acme", "Amount": "100", "Date": "2026-01-01"},  # dup (case-insensitive name)
            {"Vendor": "ACME", "Amount": "200", "Date": "2026-01-01"}]
    out = find_duplicates(cols, rows)
    assert out["duplicate_count"] == 1
    assert out["duplicates"][0]["matches_row"] == 2


def test_empty_input_is_safe():
    assert parse_sales_order([], [])["valid_count"] == 0
    assert parse_inventory([], [])["total"] == 0


def test_app_token_guard(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    import app as ultron_app
    monkeypatch.setattr(ultron_app, "APP_TOKEN", "s3cret")
    client = ultron_app.app.test_client()
    assert client.post("/chat", json={}).status_code == 401
    assert client.post("/chat", json={}, headers={"X-App-Token": "nope"}).status_code == 401
    # right token gets past the guard (an export needs no API call)
    ok = client.post("/export-excel", json={"columns": ["a"], "rows": [{"a": 1}]},
                     headers={"X-App-Token": "s3cret"})
    assert ok.status_code == 200
    assert client.get("/config").status_code == 200  # GETs stay open
