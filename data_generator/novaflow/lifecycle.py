"""Customer lifecycle simulation.

For every customer this walks through time and produces:
  * New Business opportunities (with retries after losses)
  * on a win: accounts, a platform subscription, optional onboarding services
  * Expansion opportunities (seat upsells, add-ons, services)
  * Renewal opportunities at each annual/multi-year term end, or monthly churn
Outcomes depend on segment, industry, lead source, rep skill and a hidden
customer "health" score, so the resulting data carries real signal.
"""
from math import log
from random import Random

import numpy as np
import pandas as pd

from .config import CHURN_REASONS, CURRENCY_BY_COUNTRY, END_DATE, INDUSTRIES, LEAD_SOURCES, NB_LOSS_REASONS, \
    OPEN_STAGES, SEGMENTS
from .reference import ADDONS_BY_SEGMENT, PLATFORM_BY_TIER, RepPicker
from .utils import END_ORD, add_months, fmt_id, quarter_end

LOST_STAGE_WEIGHTS = [0.22, 0.24, 0.2, 0.16, 0.11, 0.07]
BU_NAMES = ["Finance", "Marketing", "Data Platform", "EMEA Operations", "APAC Operations", "Product",
            "Supply Chain", "Customer Success", "HR Analytics"]


class Lifecycle:
    def __init__(self, customers, hidden, reps, rep_skill, products, seed):
        self.py = Random(seed)
        self.picker = RepPicker(reps, self.py)
        self.skill = rep_skill
        self.c = customers
        self.h = hidden
        self.price = dict(zip(products.product_id, products.list_price_usd.astype(float)))
        self.model = dict(zip(products.product_id, products.pricing_model))
        self.short = dict(zip(products.product_id, products.product_name.str.replace("NovaFlow ", "", regex=False)))
        self.launch = {p: d.toordinal() for p, d in zip(products.product_id, products.launch_date.dt.date)}
        self.opps, self.subs, self.accounts, self.charges = [], [], [], []
        self.nb_loss = (list(NB_LOSS_REASONS), list(NB_LOSS_REASONS.values()))
        self.churn_reasons = (list(CHURN_REASONS), list(CHURN_REASONS.values()))

    # ------------------------------------------------------------------ helpers
    def _choice(self, pair):
        return self.py.choices(pair[0], pair[1])[0]

    def _close(self, created, cycle, pwin, snap=False):
        """Return (close_ord, is_closed, is_won, stage, last_stage, probability, snapped)."""
        py = self.py
        close = created + cycle
        if close > END_ORD:
            idx = min(5, int((END_ORD - created) / cycle * 6))
            stage, prob = OPEN_STAGES[idx]
            return close, False, False, stage, stage, prob, False
        won = py.random() < pwin
        snapped = False
        if won:
            if snap and py.random() < 0.35:
                qe = quarter_end(close)
                if qe - close <= 45 and qe <= END_ORD:
                    close = max(created + 1, qe - py.randint(0, 6))
                    snapped = True
            return close, True, True, "Closed Won", "Negotiation", 100, snapped
        last = py.choices([s for s, _ in OPEN_STAGES], LOST_STAGE_WEIGHTS)[0]
        return close, True, False, "Closed Lost", last, 0, False

    def _opp(self, **kw):
        kw["opportunity_id"] = fmt_id("OPP", len(self.opps) + 1)
        self.opps.append(kw)
        return kw

    def _account(self, cid, name, atype, created, manager, country, health):
        aid = fmt_id("ACC", len(self.accounts) + 1, 6)
        self.accounts.append(dict(account_id=aid, customer_id=cid, account_name=name, account_type=atype,
                                  created_ord=created, account_manager_id=manager, billing_country=country,
                                  billing_currency=CURRENCY_BY_COUNTRY[country],
                                  health_score=int(np.clip(round((health + self.py.gauss(0, 0.1)) * 100), 1, 100)),
                                  status=None, churned_ord=-1))
        return aid

    def _sub(self, **kw):
        kw["subscription_id"] = fmt_id("SUB", len(self.subs) + 1, 6)
        self.subs.append(kw)
        return kw

    # ------------------------------------------------------------------ main loop
    def run(self):
        py = self.py
        c = self.c
        n = len(c)
        owner = [None] * n
        since = [-1] * n
        churned = [-1] * n
        cols = (c.customer_id.values, c.company_name.values, c.segment.values, c.region.values,
                c.country.values, c.industry.values, c.acquisition_source.values, c.created_ord.values,
                c.domain.values, self.h["health"], self.h["fit"])
        for i, (cid, company, seg, region, country, industry, source, created, domain, health, fit) in \
                enumerate(zip(*cols)):
            cfg = SEGMENTS[seg]
            created = int(created)
            if py.random() > 0.9:  # never reaches the pipeline (only leads/web activity)
                owner[i] = self.picker.pick("AE", region, seg, created)
                if source == "Free Trial" and py.random() < 0.6:
                    a = self._account(cid, company + " (Trial)", "Trial", created, None, country, health)
                    self.accounts[-1]["status"] = "Expired"
                continue
            t = created + int(py.expovariate(1 / 25))
            if t > END_ORD:
                owner[i] = self.picker.pick("AE", region, seg, created)
                continue
            mult = LEAD_SOURCES[source][2] * INDUSTRIES[industry][1] * fit
            tiers = (list(cfg["tiers"]), list(cfg["tiers"].values()))
            attempts, won = 0, None
            first_nb = None
            while True:
                attempts += 1
                ae = self.picker.pick("AE", region, seg, t)
                cycle = max(5, int(py.lognormvariate(log(cfg["cycle_median"]), 0.55)))
                tier = self._choice(tiers)
                pid = PLATFORM_BY_TIER[tier]
                seats = max(3, int(py.lognormvariate(log(cfg["seats_median"]), cfg["seats_sigma"])))
                disc = py.uniform(*cfg["discount"])
                pwin = min(0.85, cfg["win_rate"] * mult * self.skill[ae] * (1.1 if attempts > 1 else 1.0))
                close, closed, is_won, stage, last, prob, snapped = self._close(t, cycle, pwin, snap=True)
                if snapped:
                    disc += py.uniform(0.03, 0.08)  # end-of-quarter discounting
                disc = round(min(disc, 0.45), 3)
                o = self._opp(customer_id=cid, account_id=None, owner_rep_id=ae, product_id=pid,
                              opportunity_type="New Business", lead_source=source,
                              opportunity_name=f"{company} - {tier} - New Business",
                              seats=seats, discount_pct=disc,
                              amount=round(seats * self.price[pid] * 12 * (1 - disc), 2),
                              created_ord=t, close_ord=close, is_closed=closed, is_won=is_won,
                              stage_name=stage, last_stage=last, probability=prob,
                              loss_reason=None if (is_won or not closed) else self._choice(self.nb_loss))
                if first_nb is None:
                    first_nb, first_created = o["opportunity_id"], t
                owner[i] = ae
                if not closed:
                    break
                if is_won:
                    won = o
                    break
                if attempts >= 8 or py.random() > 0.8:
                    break
                t = close + py.randint(30, 180)
                if t > END_ORD:
                    break
            if source == "Free Trial":
                self._account(cid, company + " (Trial)", "Trial", max(created, first_created - py.randint(1, 14)),
                              None, country, health)
                self.accounts[-1]["status"] = "Converted" if won else "Expired"
            if won is None:
                continue
            since[i] = won["close_ord"]
            churned[i] = self._customer(cid, company, seg, region, country, domain, health, won)
        return owner, since, churned

    # ------------------------------------------------------------------ paying customer
    def _customer(self, cid, company, seg, region, country, domain, health, nb):
        py = self.py
        cfg = SEGMENTS[seg]
        won_day = nb["close_ord"]
        am = self.picker.pick("AM", region, None, won_day)
        first_account = len(self.accounts)
        acct = self._account(cid, company, "Production", won_day, am, country, health)
        nb["account_id"] = acct
        monthly = py.random() < cfg["monthly_share"]
        freq = "Monthly" if monthly else "Annual"
        churn_reason = self._choice(self.churn_reasons)

        # ---- term chain / churn date
        terms, churn = [], -1
        if monthly:
            hazard = min(0.12, 0.008 + 0.06 * (1 - health))
            tenure = int(log(1 - py.random()) / log(1 - hazard)) + 1
            churn = add_months(won_day, tenure)
            if churn > END_ORD:
                churn = -1
        else:
            ts, length = won_day, py.choice(cfg["terms"])
            while True:
                te = add_months(ts, length)
                if te > END_ORD:
                    terms.append((ts, te, length, None))
                    break
                p_renew = min(0.97, 0.3 + 0.7 * health + (0.04 if seg == "Enterprise" else 0))
                renewed = py.random() < p_renew
                terms.append((ts, te, length, renewed))
                if not renewed:
                    churn = te
                    break
                ts, length = te, py.choice(cfg["terms"])
        limit = churn if churn > 0 else END_ORD + 1

        lines = []

        def add_line(account_id, pid, opp_id, start, qty, unit, disc):
            lines.append(self._sub(account_id=account_id, customer_id=cid, product_id=pid, opportunity_id=opp_id,
                                   start_ord=start, end_ord=churn, billing_frequency=freq, anchor_ord=won_day,
                                   quantity=qty, list_unit_price=unit, discount_pct=round(disc, 3),
                                   mrr=round(qty * unit * (1 - disc), 2),
                                   churn_reason=churn_reason if churn > 0 else None))

        add_line(acct, nb["product_id"], nb["opportunity_id"], won_day, nb["seats"], self.price[nb["product_id"]],
                 nb["discount_pct"])
        platform_pid = nb["product_id"]
        platform_seats = nb["seats"]

        onboard_p = {"SMB": 0.05, "Mid-Market": 0.35, "Enterprise": 0.7}[seg]
        if py.random() < onboard_p:
            amt = self.price["PRD-011"] * (py.uniform(1, 3) if seg == "Enterprise" else py.uniform(0.6, 1.2))
            self.charges.append(dict(account_id=acct, customer_id=cid, product_id="PRD-011",
                                     opportunity_id=nb["opportunity_id"], charge_ord=won_day + py.randint(0, 14),
                                     amount_usd=round(amt, -2)))

        # ---- secondary accounts
        bu_accounts = []
        if seg != "SMB" and py.random() < (0.5 if seg == "Enterprise" else 0.25):
            d = won_day + py.randint(1, 45)
            if d < limit and d <= END_ORD:
                self._account(cid, company + " - Sandbox", "Sandbox", d, am, country, health)
        if seg == "Enterprise" and py.random() < 0.35:
            for bu in py.sample(BU_NAMES, py.randint(1, 2)):
                d = won_day + py.randint(120, 700)
                if d < limit and d <= END_ORD:
                    bu_accounts.append((self._account(cid, f"{company} - {bu}", "Business Unit", d, am, country,
                                                      health), d))

        # ---- expansions
        rate = cfg["expansion_rate"] * (0.4 + health) / 365
        owned = set()
        t = won_day + 45 + int(py.expovariate(rate))
        addon_w = ADDONS_BY_SEGMENT[seg]
        while t < limit and t <= END_ORD:
            rep = self.picker.pick("AM", region, None, t)
            r = py.random()
            cands = [p for p in addon_w if p not in owned and self.launch[p] <= t]
            if r < 0.45 or (r < 0.9 and not cands):
                kind, pid = "seats", platform_pid
                qty = max(1, int(platform_seats * py.uniform(0.1, 0.4)))
            elif r < 0.9:
                kind = "addon"
                pid = py.choices(cands, [addon_w[p] for p in cands])[0]
                qty = platform_seats if self.model[pid] == "per_seat" else 1
            else:
                kind = "services"
                pid = "PRD-012" if py.random() < 0.6 else "PRD-011"
                qty = 1
            disc = py.uniform(0, cfg["discount"][1] * 0.6)
            unit = self.price[pid]
            if kind == "services":
                amount = round(unit * py.uniform(0.8, 2.0 if seg == "Enterprise" else 1.2), -2)
            else:
                amount = round(qty * unit * 12 * (1 - disc), 2)
            cycle = max(5, int(py.lognormvariate(log(cfg["cycle_median"] * 0.45), 0.5)))
            close, closed, is_won, stage, last, prob, _ = self._close(t, cycle, min(0.85, 0.2 + 0.45 * health),
                                                                      snap=True)
            loss = None
            if closed and churn > 0 and close >= churn:
                is_won, stage, prob, loss = False, "Closed Lost", 0, "Customer Churned"
            elif closed and not is_won:
                loss = self._choice(self.nb_loss)
            target = acct
            live_bu = [a for a, d in bu_accounts if d <= t]
            if live_bu and py.random() < 0.4:
                target = py.choice(live_bu)
            label = {"seats": "Seat Expansion", "addon": self.short[pid], "services": self.short[pid]}[kind]
            o = self._opp(customer_id=cid, account_id=target, owner_rep_id=rep, product_id=pid,
                          opportunity_type="Expansion", lead_source="Existing Customer",
                          opportunity_name=f"{company} - {label} - Expansion", seats=qty,
                          discount_pct=round(disc, 3) if kind != "services" else 0.0, amount=amount,
                          created_ord=t, close_ord=close, is_closed=closed, is_won=is_won,
                          stage_name=stage, last_stage=last, probability=prob, loss_reason=loss)
            if is_won:
                if kind == "services":
                    self.charges.append(dict(account_id=target, customer_id=cid, product_id=pid,
                                             opportunity_id=o["opportunity_id"], charge_ord=close,
                                             amount_usd=amount))
                else:
                    add_line(target, pid, o["opportunity_id"], close, qty, unit, disc)
                    if kind == "seats":
                        platform_seats += qty
                    else:
                        owned.add(pid)
            elif kind == "addon" and not closed:
                owned.add(pid)  # don't open a duplicate while one is in flight
            t += 1 + int(py.expovariate(rate))

        # ---- renewals (annual / multi-year contracts)
        for ts, te, length, renewed in terms:
            created = te - py.randint(75, 110)
            if created > END_ORD:
                continue
            rep = self.picker.pick("AM", region, None, created)
            acv = sum(l["mrr"] * 12 for l in lines if l["start_ord"] < te)
            base = dict(customer_id=cid, account_id=acct, owner_rep_id=rep, product_id=platform_pid,
                        opportunity_type="Renewal", lead_source="Existing Customer",
                        opportunity_name=f"{company} - Renewal {self.short[platform_pid].split()[-1]} "
                                         f"({length} mo)",
                        seats=platform_seats, discount_pct=0.0, amount=round(acv, 2), created_ord=created)
            if renewed is None:  # still open at snapshot
                cycle = te - created
                idx = min(5, int((END_ORD - created) / cycle * 6))
                stage, prob = OPEN_STAGES[idx]
                self._opp(**base, close_ord=te, is_closed=False, is_won=False, stage_name=stage, last_stage=stage,
                          probability=prob, loss_reason=None)
            else:
                close = min(END_ORD, te - py.randint(0, 20))
                self._opp(**base, close_ord=close, is_closed=True, is_won=renewed,
                          stage_name="Closed Won" if renewed else "Closed Lost",
                          last_stage="Negotiation" if renewed else py.choice(["Proposal", "Negotiation"]),
                          probability=100 if renewed else 0, loss_reason=None if renewed else churn_reason)

        # ---- current contract term on each subscription line
        for l in lines:
            if terms:
                ts, te, length, _ = terms[-1]
                l["term_months"] = length
                l["current_term_start_ord"] = max(ts, l["start_ord"])
                l["current_term_end_ord"] = te
            else:
                l["term_months"] = 1
                last = churn if churn > 0 else END_ORD
                k = 0
                while add_months(won_day, k + 1) <= last:
                    k += 1
                if churn > 0:
                    k -= 1
                l["current_term_start_ord"] = max(add_months(won_day, max(k, 0)), l["start_ord"])
                l["current_term_end_ord"] = add_months(won_day, max(k, 0) + 1)

        # ---- close out accounts
        for a in self.accounts[first_account:]:
            a["status"] = "Churned" if churn > 0 else "Active"
            a["churned_ord"] = churn
        return churn
