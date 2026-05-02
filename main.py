from fastapi import FastAPI, Request
from datetime import datetime
import uuid
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

app = FastAPI(title="Vera Challenge Bot", version="FINAL")

# ===============================
# Server start time
# ===============================
START_TIME = datetime.utcnow()

# ===============================
# In-memory storage
# ===============================
contexts = {
    "category": {},
    "merchant": {},
    "customer": {},
    "trigger": {}
}

sent_keys = set()
conversations = {}

# ===============================
# Helpers
# ===============================
def utc_now():
    return datetime.utcnow().isoformat() + "Z"

def uptime_seconds():
    return int((datetime.utcnow() - START_TIME).total_seconds())

def trigger_priority(kind):
    return {
        "renewal_due": 1,
        "perf_dip": 2,
        "competitor_opened": 3,
        "festival_upcoming": 4,
        "recall_due": 5,
        "regulation_change": 6,
        "research_digest": 7
    }.get(kind, 99)

def category_goal(slug):
    return {
        "dentists": "patients",
        "salons": "bookings",
        "gyms": "memberships",
        "restaurants": "orders",
        "pharmacies": "refills"
    }.get(slug, "customers")

def trim(msg):
    return msg[:320]

def build_suppression_key(trigger, now):
    kind = trigger.get("kind", "unknown")
    merchant_id = trigger.get("merchant_id", "unknown")
    day = now[:10]
    return f"{kind}:{merchant_id}:{day}"

# ===============================
# Message Composer (FINAL BOOSTED)
# ===============================
def compose_message(category, merchant, trigger, customer=None):
    kind = trigger.get("kind", "")
    payload = trigger.get("payload", {})

    identity = merchant.get("identity", {})
    business = identity.get("name", "Your business")
    locality = identity.get("locality") or identity.get("city", "")
    owner = identity.get("owner_first_name") or business

    category_slug = merchant.get("category_slug", "")
    goal = category_goal(category_slug)

    performance = merchant.get("performance", {})
    ctr = performance.get("ctr_pct")
    peer_ctr = performance.get("peer_ctr_pct")

    offers = merchant.get("offers", [])
    top_offer = offers[0] if offers else {}
    offer_name = top_offer.get("name")
    offer_price = top_offer.get("price")

    offer_str = f"{offer_name} @ ₹{offer_price}" if offer_name else "your best offer"

    # =========================
    # PERFORMANCE DIP
    # =========================
    if kind == "perf_dip" and ctr and peer_ctr:
        gap = peer_ctr - ctr
        loss_pct = int((gap / peer_ctr) * 100) if peer_ctr else 0

        return trim(
            f"{owner}, your CTR is {ctr:.1f}% vs {peer_ctr:.1f}% in {locality}. "
            f"That’s ~{loss_pct}% fewer customers reaching you. "
            f"Promote {offer_str} now to recover quickly. "
            f"I can fix this in minutes."
        )

    # =========================
    # COMPETITOR (IMPROVED)
    # =========================
    if kind == "competitor_opened":
        return trim(
            f"{business}, a new competitor just opened in {locality}. "
            f"Act now to protect your customers. "
            f"Promote {offer_str} immediately to stay ahead. "
            f"I can launch this in minutes."
        )

    # =========================
    # FESTIVAL
    # =========================
    if kind == "festival_upcoming":
        return trim(
            f"{business}, demand is rising in {locality}. "
            f"Promote {offer_str} now to capture more customers. "
            f"I can launch this right away."
        )

    # =========================
    # RENEWAL
    # =========================
    if kind == "renewal_due":
        days = payload.get("days_remaining", 0)
        plan = payload.get("plan", "Pro")

        return trim(
            f"{business}, your {plan} plan expires in {days} days. "
            f"Renew now to avoid losing visibility and leads. "
            f"I can renew this instantly."
        )

    # =========================
    # RESEARCH
    # =========================
    if kind == "research_digest":
        return trim(
            f"{owner}, similar businesses in {locality} are growing faster. "
            f"I can show what’s working right now."
        )

    # =========================
    # REGULATION
    # =========================
    if kind == "regulation_change":
        return trim(
            f"{owner}, a recent update may impact your business in {locality}. "
            f"I can help you stay compliant."
        )

    return trim(
        f"{business}, I found ways to improve your {goal} in {locality}. "
        f"I can help you grow faster."
    )

# ===============================
# MODELS
# ===============================
class ContextRequest(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: Optional[str] = None

class TickRequest(BaseModel):
    now: str
    available_triggers: List[str]

# ===============================
# ENDPOINTS
# ===============================
@app.get("/v1/healthz")
def healthz():
    return {
        "status": "ok",
        "uptime_seconds": uptime_seconds(),
        "contexts_loaded": {k: len(v) for k, v in contexts.items()}
    }

@app.get("/v1/metadata")
def metadata():
    return {
        "team_name": "Aiyman",
        "version": "1.0",
        "approach": "Priority-based trigger system + contextual messaging"
    }

@app.post("/v1/context")
async def context(data: ContextRequest):
    if data.scope not in contexts:
        return {"accepted": False}

    contexts[data.scope][data.context_id] = {
        "version": data.version,
        "payload": data.payload,
        "delivered_at": data.delivered_at or utc_now()
    }

    return {
        "accepted": True,
        "ack_id": f"ack_{uuid.uuid4().hex[:8]}",
        "stored_at": utc_now()
    }

# ===============================
# FINAL TICK
# ===============================
@app.post("/v1/tick")
async def tick(data: TickRequest):

    now = data.now
    available_triggers = data.available_triggers or []

    actions = []
    collected = []

    # Collect triggers
    for trigger_id, trigger_data in contexts["trigger"].items():
        if trigger_id in available_triggers:
            payload = trigger_data.get("payload", {})
            payload["id"] = trigger_id
            collected.append(payload)

    # Sort by priority
    collected.sort(key=lambda x: trigger_priority(x.get("kind")))

    merchant_action_count = {}

    for t in collected:
        if len(actions) >= 20:
            break

        merchant_id = t.get("merchant_id")
        if not merchant_id:
            continue

        count = merchant_action_count.get(merchant_id, 0)
        if count >= 1 and trigger_priority(t.get("kind")) > 2:
            continue

        sk = build_suppression_key(t, now)
        if sk in sent_keys:
            continue

        merchant_data = contexts["merchant"].get(merchant_id)
        if not merchant_data:
            continue

        merchant = merchant_data["payload"]
        category_slug = merchant.get("category_slug")
        category = contexts["category"].get(category_slug, {}).get("payload", {})

        body = compose_message(category, merchant, t)

        kind = t.get("kind", "")

        # ✅ FIXED CTA LOGIC
        if kind in ["research_digest", "regulation_change"]:
            cta = "open_ended"
        else:
            cta = "reply"

        action = {
            "conversation_id": f"conv_{t['id']}",
            "merchant_id": merchant_id,
            "customer_id": t.get("customer_id"),
            "send_as": "vera",
            "trigger_id": t["id"],
            "template_name": kind,
            "template_params": [],
            "body": body,
            "cta": cta,
            "suppression_key": sk,
            "rationale": f"{kind} triggered due to real-time signals"
        }

        actions.append(action)
        sent_keys.add(sk)
        merchant_action_count[merchant_id] = count + 1

    return {"actions": actions}

# ===============================
# REPLY
# ===============================
@app.post("/v1/reply")
async def reply(request: Request):
    data = await request.json()
    text = data.get("message", "").lower()

    if "yes" in text:
        return {"action": "send", "body": "Great, setting it up now."}

    if "price" in text:
        return {"action": "send", "body": "I can show pricing options. Want to see?"}

    if "later" in text:
        return {"action": "wait", "body": "No problem, I’ll check later."}

    if "no" in text:
        return {"action": "end", "body": "Understood."}

    return {"action": "send", "body": "How can I help you grow your business?"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)