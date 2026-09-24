"""Billing: invoice line items -> invoices (one per account per billing date)
-> payments (charges, failed retries, installments and refunds)."""
from random import Random

import numpy as np
import pandas as pd

from .config import CURRENCY_BY_COUNTRY, FX_TO_USD, TAX_RATE_BY_REGION
from .utils import DAY_SECONDS, END_ORD, EPOCH_ORD, add_months, business_seconds, fmt_id, ord_to_date


def _periods(line):
    """Yield (period_start, period_end, fraction_of_full_period) for a subscription line."""
    start, end, anchor = line["start_ord"], line["end_ord"], line["anchor_ord"]
    limit = end if end > 0 else 10**9
    if line["billing_frequency"] == "Monthly":
        k = 0
        while True:
            p0 = add_months(start, k)
            if p0 >= limit or p0 > END_ORD:
                return
            full = add_months(start, k + 1)
            p1 = min(full, limit)
            yield p0, p1, 12 * (p1 - p0) / 365.25 if p1 < full else 1.0, 1
            k += 1
    else:
        k = 0
        while add_months(anchor, 12 * (k + 1)) <= start:
            k += 1
        p0 = start
        while p0 < limit and p0 <= END_ORD:
            full = add_months(anchor, 12 * (k + 1))
            p1 = min(full, limit)
            yield p0, p1, (p1 - p0) / 365.25, 12
            p0, k = full, k + 1


def build_invoice_lines(subs, charges):
    rows = []
    for l in subs.to_dict("records"):
        for p0, p1, frac, months in _periods(l):
            # frac is a fraction of a month (monthly) or of a year (annual)
            list_amt = l["quantity"] * l["list_unit_price"] * frac * months
            rows.append((l["account_id"], l["customer_id"], l["subscription_id"], l["product_id"], None,
                         l["billing_frequency"], p0, p0, p1, l["quantity"], round(list_amt, 2),
                         round(list_amt * l["discount_pct"], 2)))
    for ch in charges.to_dict("records"):
        if ch["charge_ord"] <= END_ORD:
            rows.append((ch["account_id"], ch["customer_id"], None, ch["product_id"], ch["opportunity_id"],
                         "One-time", ch["charge_ord"], ch["charge_ord"], ch["charge_ord"], 1,
                         ch["amount_usd"], 0.0))
    return pd.DataFrame(rows, columns=["account_id", "customer_id", "subscription_id", "product_id",
                                       "opportunity_id", "billing_frequency", "invoice_ord", "period_start_ord",
                                       "period_end_ord", "quantity", "list_amount_usd", "discount_amount_usd"])


def build_billing(rng, seed, subs, charges, accounts, customers, health_by_customer):
    py = Random(seed + 7)
    lines = build_invoice_lines(subs, charges)
    lines["net_amount_usd"] = (lines.list_amount_usd - lines.discount_amount_usd).round(2)
    lines = lines[lines.net_amount_usd > 0].copy()
    # monthly card billing is kept separate from annual invoicing even on the same day
    lines["inv_kind"] = np.where(lines.billing_frequency == "Monthly", "M", "A")
    lines = lines.sort_values(["invoice_ord", "account_id", "inv_kind"], kind="stable").reset_index(drop=True)
    key = lines.account_id + "|" + lines.invoice_ord.astype(str) + "|" + lines.inv_kind
    codes, uniq = pd.factorize(key)
    lines["invoice_id"] = np.array([fmt_id("INV", i + 1) for i in range(len(uniq))], dtype=object)[codes]
    lines.insert(0, "invoice_line_id", [fmt_id("INL", i + 1) for i in range(len(lines))])

    acc = accounts.set_index("account_id")
    cust = customers.set_index("customer_id")
    inv = lines.groupby("invoice_id", sort=False).agg(
        account_id=("account_id", "first"), customer_id=("customer_id", "first"),
        inv_kind=("inv_kind", "first"), invoice_ord=("invoice_ord", "first"),
        period_start_ord=("period_start_ord", "min"), period_end_ord=("period_end_ord", "max"),
        subtotal_usd=("list_amount_usd", "sum"), discount_usd=("discount_amount_usd", "sum")).reset_index()
    inv["segment"] = inv.customer_id.map(cust.segment)
    region = inv.customer_id.map(cust.region)
    inv["currency"] = inv.account_id.map(acc.billing_currency)
    inv["fx_rate_to_usd"] = inv.currency.map(FX_TO_USD)
    net = (inv.subtotal_usd - inv.discount_usd).round(2)
    inv["tax_rate"] = region.map(TAX_RATE_BY_REGION).values
    total_usd = (net * (1 + inv.tax_rate)).round(2)
    dec = np.where(inv.currency == "JPY", 0, 2)
    to_local = lambda usd: np.array([round(v, d) for v, d in zip(usd / inv.fx_rate_to_usd, dec)])
    inv["subtotal"] = to_local(inv.subtotal_usd)
    inv["discount_amount"] = to_local(inv.discount_usd)
    inv["tax_amount"] = to_local(net * inv.tax_rate)
    inv["total_amount"] = to_local(total_usd)
    inv["total_amount_usd"] = total_usd
    terms = np.where(inv.inv_kind == "M", 0,
                     np.where(inv.segment == "Enterprise", rng.choice([30, 45, 60], len(inv), p=[0.4, 0.35, 0.25]),
                              30))
    inv["payment_terms"] = np.where(terms == 0, "Due on receipt", np.char.add("Net ", terms.astype(str)))
    inv["due_ord"] = inv.invoice_ord + terms
    yr = pd.DatetimeIndex(ord_to_date(inv.invoice_ord.values)).year
    inv["invoice_number"] = [f"NF-{y}-{i:07d}" for y, i in zip(yr, range(1, len(inv) + 1))]

    # ---------------- payments
    pays = []
    status, paid_ord = [], []
    health = inv.customer_id.map(health_by_customer).values
    for idx, (iid, aid, cid, kind, iord, due, amt, amt_usd, cur, seg) in enumerate(zip(
            inv.invoice_id, inv.account_id, inv.customer_id, inv.inv_kind, inv.invoice_ord, inv.due_ord,
            inv.total_amount, inv.total_amount_usd, inv.currency, inv.segment)):
        h = health[idx]
        if py.random() < 0.003:
            status.append("Void"); paid_ord.append(-1)
            continue
        if kind == "M":
            method = "Credit Card" if py.random() < 0.9 else "PayPal"
            day, paid = iord, False
            for attempt in range(4):
                if day > END_ORD:
                    break
                if py.random() < 0.03 + 0.1 * (1 - h):
                    pays.append((iid, aid, cid, day, amt, cur, amt_usd, method, "Failed",
                                 py.choices(["card_declined", "insufficient_funds", "expired_card",
                                             "processing_error"], [0.45, 0.3, 0.2, 0.05])[0], "charge"))
                    day += (3, 5, 7, 7)[attempt]
                else:
                    pays.append((iid, aid, cid, day, amt, cur, amt_usd, method, "Succeeded", None, "charge"))
                    paid = True
                    break
            if paid:
                status.append("Paid"); paid_ord.append(day)
            else:
                status.append("Uncollectible" if END_ORD - iord > 30 else "Past Due"); paid_ord.append(-1)
        else:
            method = py.choices(["ACH", "Wire Transfer", "Credit Card", "Check"], [0.45, 0.33, 0.17, 0.05])[0]
            if py.random() < 0.008 + 0.03 * (1 - h):
                pay_day = 10**9
            else:
                pay_day = due + int(max(-due + iord, py.gauss(-4 + 22 * (1 - h), 12)))
            if pay_day > END_ORD:
                if END_ORD - due > 120:
                    status.append("Uncollectible")
                else:
                    status.append("Overdue" if due < END_ORD else "Open")
                paid_ord.append(-1)
                continue
            if seg == "Enterprise" and amt_usd > 100_000 and py.random() < 0.25:
                first = round(amt / 2, 2)
                second_day = min(pay_day + py.randint(20, 40), END_ORD)
                pays.append((iid, aid, cid, pay_day, first, cur, round(amt_usd / 2, 2), method, "Succeeded", None,
                             "charge"))
                pays.append((iid, aid, cid, second_day, round(amt - first, 2), cur, round(amt_usd - amt_usd / 2, 2),
                             method, "Succeeded", None, "charge"))
                pay_day = second_day
            else:
                pays.append((iid, aid, cid, pay_day, amt, cur, amt_usd, method, "Succeeded", None, "charge"))
            status.append("Paid"); paid_ord.append(pay_day)
        if status[-1] == "Paid" and py.random() < 0.004:
            rday = min(paid_ord[-1] + py.randint(2, 40), END_ORD)
            share = py.choice([1.0, 0.5, 0.25])
            pays.append((iid, aid, cid, rday, -round(amt * share, 2), cur, -round(amt_usd * share, 2),
                         pays[-1][7], "Succeeded", None, "refund"))
    inv["status"] = status
    inv["paid_ord"] = paid_ord

    p = pd.DataFrame(pays, columns=["invoice_id", "account_id", "customer_id", "day", "amount", "currency",
                                    "amount_usd", "payment_method", "status", "failure_reason", "payment_type"])
    sec = business_seconds(rng, len(p))
    p["payment_date"] = ((p.day.values - EPOCH_ORD) * DAY_SECONDS + sec).astype("datetime64[s]")
    fee = np.select([p.payment_method == "Credit Card", p.payment_method == "PayPal", p.payment_method == "ACH",
                     p.payment_method == "Wire Transfer"],
                    [p.amount_usd.abs() * 0.029 + 0.30, p.amount_usd.abs() * 0.0349 + 0.49,
                     np.minimum(p.amount_usd.abs() * 0.008, 5.0), 15.0], 0.0)
    p["processor_fee_usd"] = np.where((p.status == "Succeeded") & (p.payment_type == "charge"), fee, 0.0).round(2)
    p = p.sort_values(["payment_date"], kind="stable").reset_index(drop=True)
    p.insert(0, "payment_id", [fmt_id("PAY", i + 1) for i in range(len(p))])
    prefix = p.payment_method.map({"Credit Card": "ch_", "PayPal": "pp_", "ACH": "ach_", "Wire Transfer": "wire_",
                                   "Check": "chk_"})
    p["transaction_reference"] = prefix + pd.Series([f"{x:012x}" for x in rng.integers(0, 2**48, len(p))])
    p = p.drop(columns=["day"])

    inv["invoice_date"] = ord_to_date(inv.invoice_ord)
    inv["due_date"] = ord_to_date(inv.due_ord)
    inv["period_start"] = ord_to_date(inv.period_start_ord)
    inv["period_end"] = ord_to_date(inv.period_end_ord)
    inv["paid_date"] = ord_to_date(inv.paid_ord)
    inv["billing_type"] = inv.inv_kind.map({"M": "Monthly Subscription", "A": "Annual / One-time"})
    invoices = inv[["invoice_id", "invoice_number", "account_id", "customer_id", "invoice_date", "due_date",
                    "period_start", "period_end", "billing_type", "payment_terms", "currency", "fx_rate_to_usd",
                    "subtotal", "discount_amount", "tax_rate", "tax_amount", "total_amount", "total_amount_usd",
                    "status", "paid_date"]]

    lines["period_start"] = ord_to_date(lines.period_start_ord)
    lines["period_end"] = ord_to_date(lines.period_end_ord)
    lines = lines[["invoice_line_id", "invoice_id", "subscription_id", "product_id", "opportunity_id",
                   "billing_frequency", "period_start", "period_end", "quantity", "list_amount_usd",
                   "discount_amount_usd", "net_amount_usd"]]
    return invoices, lines, p
