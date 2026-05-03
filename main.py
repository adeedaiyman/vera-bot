from fastapi import FastAPI
from datetime import datetime
import uuid
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

app = FastAPI(title="Vera Challenge Bot", version="FINAL")

# ===============================
# MODELS
# ===============================
class ReplyRequest(BaseModel):
    message: str
    merchant_id: str
    conversation_id: str


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
# GLOBALS
# ===============================
START_TIME = datetime.utcnow()

contexts = {
    "category": {},
    "merchant": {},
    "customer": {},
    "trigger": {}
}

sent_keys = set()
conversations = {}

# ===============================
# HELPERS
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
    return f"{trigger.get('kind')}:{trigger.get('merchant_id')}:{now[:10]}"


# ===============================
# DETECTION LOGIC
# ===============================
STOP_WORDS = ["stop", "unsubscribe", "opt out", "remove me", "cancel", "end"]

def is_stop(text):
    return any(k in text.lower() for k in STOP_WORDS)


def is_auto_reply(text):
    auto_keywords = [
        "out of office", "auto reply", "automatic reply",
        "busy", "call later", "not available",
        "away", "respond later"
    ]
    return any(k in text.lower() for k in auto_keywords)


def detect_intent(text):
    t = text.lower()

    if any(k in t for k in ["yes", "yeah", "sure", "go ahead", "ok", "okay"]):
        return "confirm"

    if any(k in t for k in ["no", "not interested", "later", "no thanks"]):
        return "reject"

    if any(k in t for k in ["book", "schedule", "appointment"]):
        return "booking"

    if any(k in t for k in ["price", "cost", "offer"]):
        return "pricing"

    return "default"


# ===============================
# MESSAGE COMPOSER
# ===============================
def compose_message(category, merchant, trigger):
    kind = trigger.get("kind", "")
    identity = merchant.get("identity", {})

    business = identity.get("name", "Your business")
    locality = identity.get("locality") or identity.get("city", "")

    offers = merchant.get("offers", [])
    top_offer = offers[0] if offers else {}
    offer_name = top_offer.get("name", "your best offer")
    offer_price = top_offer.get("price")

    offer_str = f"{offer_name} @ ₹{offer_price}" if offer_price else offer_name

    if kind == "competitor_opened":
        return trim(
            f"{business}, a new competitor just opened in {locality}. "
            f"Act now to protect your customers. Promote {offer_str} immediately. "
            f"Reply 'yes' and I’ll launch this instantly."
        )

    return trim(
        f"{business}, I found a way to increase customers in {locality}. "
        f"I recommend promoting {offer_str}. Reply 'yes' to launch now."
    )


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
        "approach": "Trigger prioritization + contextual CTA messaging"
    }


@app.post("/v1/context")
async def context(data: ContextRequest):
    if data.scope not in contexts:
        return {"accepted": False}

    contexts[data.scope][data.context_id] = {
        "payload": data.payload,
        "version": data.version
    }

    return {
        "accepted": True,
        "ack_id": f"ack_{uuid.uuid4().hex[:8]}"
    }


# ===============================
# TICK
# ===============================
@app.post("/v1/tick")
async def tick(data: TickRequest):

    now = data.now
    actions = []

    for trigger_id, trigger_data in contexts["trigger"].items():

        if trigger_id not in data.available_triggers:
            continue

        payload = trigger_data.get("payload", {})
        merchant_id = payload.get("merchant_id")

        merchant_data = contexts["merchant"].get(merchant_id)
        if not merchant_data:
            continue

        merchant = merchant_data["payload"]
        category = contexts["category"].get(
            merchant.get("category_slug"), {}
        ).get("payload", {})

        body = compose_message(category, merchant, payload)

        action = {
            "conversation_id": f"conv_{trigger_id}",
            "merchant_id": merchant_id,
            "customer_id": None,
            "send_as": "vera",
            "trigger_id": trigger_id,
            "template_name": payload.get("kind"),
            "template_params": [],
            "body": body,
            "cta": "reply",
            "suppression_key": build_suppression_key(payload, now),
            "rationale": "trigger-based action"
        }

        actions.append(action)

        if len(actions) >= 20:
            break

    return {"actions": actions}


# ===============================
# REPLY (FINAL FIXED)
# ===============================
@app.post("/v1/reply")
async def reply(data: ReplyRequest):

    text = data.message.strip()
    merchant_id = data.merchant_id
    conversation_id = data.conversation_id

    # STOP FIRST
    if is_stop(text):
        return {
            "actions": [
                {
                    "type": "end",
                    "reason": "user_opt_out",
                    "final": True
                }
            ]
        }

    # AUTO REPLY
    if is_auto_reply(text):
        return {"actions": []}

    intent = detect_intent(text)

    merchant = contexts["merchant"].get(merchant_id, {}).get("payload", {})
    identity = merchant.get("identity", {})

    business = identity.get("name", "your business")
    locality = identity.get("locality") or identity.get("city", "")

    offers = merchant.get("offers", [])
    top_offer = offers[0] if offers else {}
    offer_name = top_offer.get("name", "your best offer")
    offer_price = top_offer.get("price")

    offer_str = f"{offer_name} @ ₹{offer_price}" if offer_price else offer_name

    # =========================
    # CONFIRM
    # =========================
    if intent == "confirm":
        return {
            "actions": [
                {
                    "type": "send",
                    "conversation_id": conversation_id,
                    "body": f"Great, launching {offer_str} for {business} in {locality}. You’ll start seeing results shortly."
                },
                {
                    "type": "end",
                    "reason": "completed"
                }
            ]
        }

    # =========================
    # BOOKING
    # =========================
    if intent == "booking":
        return {
            "actions": [
                {
                    "type": "send",
                    "conversation_id": conversation_id,
                    "body": f"Got it. I’ll schedule this for {business} right away."
                }
            ]
        }

    # =========================
    # PRICING
    # =========================
    if intent == "pricing":
        return {
            "actions": [
                {
                    "type": "send",
                    "conversation_id": conversation_id,
                    "body": f"I can optimize pricing for {business} in {locality} to increase conversions. Want me to proceed?"
                }
            ]
        }

    # =========================
    # REJECT
    # =========================
    if intent == "reject":
        return {
            "actions": [
                {
                    "type": "end",
                    "reason": "user_not_interested"
                }
            ]
        }

    # =========================
    # DEFAULT (HIGH ENGAGEMENT)
    # =========================
    return {
        "actions": [
            {
                "type": "send",
                "conversation_id": conversation_id,
                "body": f"{business} in {locality} can get more customers this week. "
                        f"I recommend promoting {offer_str} now. "
                        f"Reply 'yes' and I’ll launch it instantly."
            }
        ]
    }


# ===============================
# RUN
# ===============================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)