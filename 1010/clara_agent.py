#!/usr/bin/env python3
"""
CLARA v2.2 - Command Line Algorithmic Routing Agent
1010 micro-node beta ledger. stdlib-only, no database, zero overhead.

Two capture layers, because they serve different masters:
  - clara_ledger.log : append-only human/forensic AUDIT trail (logging module)
  - clara_log.jsonl  : one structured row per trial == the draft backend SCHEMA

The 600-second clock is split into SEGMENTS so a failed run tells you WHERE
it died, not just that it did:
  STAGE   = order placed  -> rider departs   (tests predictive pre-positioning)
  TRANSIT = departs       -> arrives at door  (dominant cost; ~= geofence size)
  DOOR    = arrives       -> drop confirmed   (the human last leg + handshake)
The rider taps 'Mark checkpoint' on depart and on arrival. Skipping marks is
fine: segments go null, total elapsed is always recorded.

Run:  python clara_agent.py
Env:  CLARA_LOG (jsonl) ; CLARA_AUDIT (.log) ; CLARA_GEOFENCE (default 600)
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

# --- Tunable protocol constants (the secret seasoning, in one place) ---
GEOFENCE_SECONDS = int(os.environ.get("CLARA_GEOFENCE", "600"))  # 10-min SLA
PAY_ON_LATE = False               # late drop: item delivered, fee withheld
DELIVERY_FEE = Decimal("10.00")
DATA_PATH = os.environ.get("CLARA_LOG", "clara_log.jsonl")
AUDIT_PATH = os.environ.get("CLARA_AUDIT", "clara_ledger.log")
CENTS = Decimal("0.01")

logging.basicConfig(filename=AUDIT_PATH, level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")


def money(v):
    """Quantize to cents. Money is Decimal, never float."""
    return Decimal(v).quantize(CENTS, rounding=ROUND_HALF_UP)


def usd(v):
    return f"${money(v):.2f}"


def _secs(v):
    return None if v is None else round(v, 1)


class CLARALedger:
    def __init__(self, rider_name):
        self.node_id = str(uuid.uuid4())[:8]
        self.rider_name = rider_name

        # SKU-keyed $30 block: sum(wholesale * qty) == $30.00 exactly.
        self.inventory = {
            "1": {"name": "M&Ms",         "qty": 10, "wholesale": Decimal("1.00")},
            "2": {"name": "Charger",      "qty": 2,  "wholesale": Decimal("5.00")},
            "3": {"name": "Energy Drink", "qty": 5,  "wholesale": Decimal("2.00")},
        }

        self.payout_balance = Decimal("0.00")    # net cash to the rider node
        self.liability_escrow = Decimal("0.00")  # cumulative reimbursements owed to owners
        self.trips = 0
        self.active_order = None

    def boot_node(self):
        basis = sum((d["wholesale"] * d["qty"] for d in self.inventory.values()), Decimal("0.00"))
        logging.info(f"Node {self.node_id} ({self.rider_name}) ACTIVE. Cost basis {usd(basis)}.")
        print(f"\n[SYSTEM] Node {self.node_id} ({self.rider_name}) ACTIVE. "
              f"Geofence {GEOFENCE_SECONDS}s, cost basis {usd(basis)}.")
        self.print_inventory()

    def print_inventory(self):
        print("\n--- EDGE CACHE ---")
        for key, d in self.inventory.items():
            print(f"[{key}] {d['name']}: {d['qty']} units  (wholesale {usd(d['wholesale'])})")
        print("------------------")

    def trigger_order(self, sku_key):
        if self.active_order:
            print("[ERROR] Node busy. Finish current routing first.")
            return
        slot = self.inventory.get(sku_key)
        if not slot or slot["qty"] <= 0:
            print("[ERROR] Race Condition Prevented. Invalid SKU or out of stock.")
            return

        slot["qty"] -= 1  # lock one unit
        now = time.monotonic()
        # REAL-WORLD VALIDATION: time.monotonic() stops accidental drift (NTP/DST),
        # NOT a driver who controls their own device. A tamper-proof clock must be
        # server-authoritative -- the device reports events, the backend timestamps them.
        self.active_order = {
            "order_id": str(uuid.uuid4())[:8],
            "sku": sku_key,
            "item": slot["name"],
            "wholesale": slot["wholesale"],
            "start_time": now,
            "phase": "STAGE",
            "seg_start": now,
            "segments": {"stage": None, "transit": None, "door": None},
        }
        msg = f"Order {self.active_order['order_id']} for {slot['name']}. {GEOFENCE_SECONDS}s timer started [STAGE]."
        print(f"\n[ROUTING] {msg}")
        logging.info(msg)

    def mark_checkpoint(self):
        if not self.active_order:
            print("[ERROR] No active order to mark.")
            return
        o = self.active_order
        now = time.monotonic()
        seg = now - o["seg_start"]
        if o["phase"] == "STAGE":
            o["segments"]["stage"] = seg
            o["phase"] = "TRANSIT"
            label = f"Departed. STAGE {seg:.1f}s. Now in TRANSIT."
        elif o["phase"] == "TRANSIT":
            o["segments"]["transit"] = seg
            o["phase"] = "DOOR"
            label = f"Arrived. TRANSIT {seg:.1f}s. Now at DOOR."
        else:
            print("[INFO] Already at DOOR. Complete the drop.")
            return
        o["seg_start"] = now
        print(f"\n[MARK] {label}")
        logging.info(label)

    def _finalize_door(self, o, now):
        if o["phase"] == "DOOR" and o["segments"]["door"] is None:
            o["segments"]["door"] = now - o["seg_start"]

    def complete_drop(self):
        if not self.active_order:
            print("[ERROR] No active order to complete.")
            return
        o = self.active_order
        now = time.monotonic()
        elapsed = now - o["start_time"]
        self._finalize_door(o, now)
        within = elapsed <= GEOFENCE_SECONDS

        if within or PAY_ON_LATE:
            self.payout_balance += DELIVERY_FEE
            fee_paid = DELIVERY_FEE
            outcome = "DELIVERED" if within else "DELIVERED_LATE_PAID"
            line = f"[SUCCESS] Drop cleared in {elapsed:.1f}s. +{usd(DELIVERY_FEE)}."
            logging.info(line)
        else:
            fee_paid = Decimal("0.00")
            outcome = "SLA_MISS"
            line = f"[PENALTY] SLA missed: {elapsed:.1f}s > {GEOFENCE_SECONDS}s. Fee withheld, item delivered."
            logging.warning(line)

        print(f"\n{line}")
        print(f"[SEGMENTS] {self._seg_str(o)}")
        print(f"[LEDGER] Balance: {usd(self.payout_balance)}.")
        self._log_trial(o, outcome, elapsed, fee_paid, Decimal("0.00"))
        self.active_order = None

    def packet_loss(self):
        if not self.active_order:
            print("[ERROR] No active order to drop.")
            return
        o = self.active_order
        now = time.monotonic()
        elapsed = now - o["start_time"]
        self._finalize_door(o, now)
        cost = o["wholesale"]

        self.payout_balance -= cost      # auto-deduct from node
        self.liability_escrow += cost    # routed to owner reimbursement
        line = (f"[ALERT] Packet Loss: {o['item']} (order {o['order_id']}). "
                f"Deducted {usd(cost)}. Escrow total {usd(self.liability_escrow)}.")
        print(f"\n{line}")
        print(f"[SEGMENTS] {self._seg_str(o)}")
        print(f"[LEDGER] Balance: {usd(self.payout_balance)}.")
        logging.error(line)
        self._log_trial(o, "PACKET_LOSS", elapsed, Decimal("0.00"), cost)
        self.active_order = None

    @staticmethod
    def _seg_str(o):
        s = o["segments"]
        parts = [f"{k}={'--' if s[k] is None else f'{s[k]:.1f}s'}" for k in ("stage", "transit", "door")]
        return " | ".join(parts)

    def _log_trial(self, o, outcome, elapsed, fee_paid, deduction):
        self.trips += 1
        seg = o["segments"]
        row = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "node_id": self.node_id,
            "rider": self.rider_name,
            "order_id": o["order_id"],
            "sku": o["sku"],
            "item": o["item"],
            "wholesale": str(o["wholesale"]),
            "elapsed_seconds": round(elapsed, 1),
            "stage_seconds": _secs(seg["stage"]),
            "transit_seconds": _secs(seg["transit"]),
            "door_seconds": _secs(seg["door"]),
            "within_sla": elapsed <= GEOFENCE_SECONDS,
            "outcome": outcome,
            "fee_paid": str(money(fee_paid)),
            "deduction": str(money(deduction)),
            "balance_after": str(money(self.payout_balance)),
            "escrow_after": str(money(self.liability_escrow)),
        }
        with open(DATA_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")


def run_clara_cli():
    print("Initializing CLARA v2.2 (Command Line Algorithmic Routing Agent)...")
    node = CLARALedger("Heavy_Hitter_01")
    node.boot_node()

    while True:
        header = f"\n[BALANCE: {usd(node.payout_balance)} | ESCROW: {usd(node.liability_escrow)}]"
        if node.active_order:
            o = node.active_order
            elapsed = time.monotonic() - o["start_time"]
            remaining = GEOFENCE_SECONDS - elapsed
            flag = "OK" if remaining >= 0 else "OVER SLA"
            header += f" | ACTIVE {o['item']} [{o['phase']}] {elapsed:.0f}s ({remaining:.0f}s left) [{flag}]"
        print(header)
        print("1: Order | 2: Mark checkpoint | 3: Complete Drop | 4: Packet Loss | 5: Terminate")
        try:
            choice = input("Cmd: ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "5"

        if choice == "1":
            node.print_inventory()
            sku = input("Select SKU: ").strip()
            node.trigger_order(sku)
        elif choice == "2":
            node.mark_checkpoint()
        elif choice == "3":
            node.complete_drop()
        elif choice == "4":
            node.packet_loss()
        elif choice == "5":
            print(f"\n[SYSTEM] Shutting down. {node.trips} trial(s) -> {DATA_PATH}. "
                  f"Final balance {usd(node.payout_balance)}.")
            logging.info(f"Node {node.node_id} OFFLINE. {node.trips} trials, balance {usd(node.payout_balance)}.")
            return
        else:
            print("[ERROR] Invalid Command.")


if __name__ == "__main__":
    run_clara_cli()
