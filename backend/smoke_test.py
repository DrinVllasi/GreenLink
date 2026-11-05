"""Runs a full parcel journey against your running server.

1. Start the server:  uvicorn main:app --reload     (in one window)
2. In ANOTHER window (venv active):  python smoke_test.py
"""
import json
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = "http://localhost:8000"


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")
    except urllib.error.URLError:
        print("Cannot reach the server. Is uvicorn running on port 8000?")
        sys.exit(1)


def step(title, ok, extra=""):
    print(("PASS  " if ok else "FAIL  ") + title + (f"  ->  {extra}" if extra else ""))
    if not ok:
        sys.exit(1)


_, users = call("GET", "/users")
sender = next(u for u in users if u["role"] == "sender")
_, routes = call("GET", "/routes")
route = next(r for r in routes if r["origin"].startswith("Prishtin") and r["destination"] == "Prizren")

code, q = call("POST", "/parcels/quote", {"route_id": route["id"], "weight_kg": 3})
step("Quote", code == 200 and q["best_departure"] is not None,
     f"price {q['price']} EUR, best bus {q['best_departure']['operator']}")

code, created = call("POST", "/parcels", {
    "sender_id": sender["id"], "route_id": route["id"], "receiver_name": "Test Receiver",
    "receiver_phone": "+38344999999", "weight_kg": 3, "content_type": "handmade goods"})
step("Create parcel", code == 200, created["parcel"]["code"] if code == 200 else created)
parcel = created["parcel"]
pcode, pickup = parcel["code"], parcel["pickup_code"]

code, r = call("POST", f"/parcels/{pcode}/collect", {"pickup_code": pickup})
step("Collect too early is refused", code == 409, r.get("detail"))

for expected in ["matched", "loaded", "in_transit", "arrived"]:
    code, r = call("POST", f"/parcels/{pcode}/scan", {})
    step(f"Scan -> {expected}", code == 200 and r["parcel"]["status"] == expected, r.get("message"))

code, r = call("POST", f"/parcels/{pcode}/collect", {"pickup_code": "0000x"})
step("Wrong pickup code is refused", code == 403, r.get("detail"))

code, r = call("POST", f"/parcels/{pcode}/collect", {"pickup_code": pickup})
step("Collect with correct code", code == 200,
     f"{r.get('co2_avoided_kg')} kg CO2 avoided, {r.get('credits_awarded')} credits")

code, r = call("POST", f"/parcels/{pcode}/collect", {"pickup_code": pickup})
step("Double collect is refused", code == 409, r.get("detail"))

code, s = call("GET", f"/senders/{sender['id']}/summary")
step("Sender summary", code == 200, f"{s['parcels_total']} parcels, {s['credits_balance']} credits")

print("\nAll checks passed. Open http://localhost:8000/docs and look at GET /notifications.")
