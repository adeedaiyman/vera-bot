# Vera Challenge Bot

This project is a FastAPI-based backend bot built for the Vera AI Challenge. The goal of the bot is to generate intelligent, context-aware messages for merchants based on incoming triggers.

---

## 🚀 What this bot does

The bot receives structured context (categories, merchants, triggers, customers) and produces actionable messages using simple, deterministic logic.

For example:

* If a competitor opens nearby → suggest promotional action
* If demand drops → suggest boosting offers
* If new trends appear → suggest strategic changes

The focus is on:

* Relevance
* Clarity
* Actionability

---

## ⚙️ Tech Stack

* Python 3.11
* FastAPI
* Uvicorn

No external LLM is required — logic is rule-based and deterministic.

---

## 📂 Project Structure

```
vera-bot/
│
├── main.py              # Main FastAPI app
├── composer.py          # Message generation logic
├── requirements.txt     # Dependencies
├── Procfile             # Deployment config (Railway)
└── README.md            # Documentation
```

---

## 🧪 API Endpoints

### 1. Health Check

```
GET /v1/healthz
```

Returns service status and loaded context counts.

---

### 2. Metadata

```
GET /v1/metadata
```

Basic bot information.

---

### 3. Context Ingestion

```
POST /v1/context
```

Used by the judge to push data like:

* categories
* merchants
* triggers
* customers

---

### 4. Tick (Core Logic)

```
POST /v1/tick
```

Processes triggers and returns actions.

This is the most important endpoint.

---

### 5. Reply (Optional)

```
POST /v1/reply
```

Handles follow-up interactions (if implemented).

---

## 🧠 How it works

1. Context is stored in-memory
2. `/v1/tick` receives active triggers
3. Bot matches:

   * trigger → merchant → category
4. A message is generated using `compose_message()`
5. A structured action is returned

---

## ✨ Message Strategy

Messages are designed to be:

* Short and direct
* Personalized (merchant name + locality)
* Action-driven (clear CTA)
* Context-aware (trigger-based)

Example:

> “A new competitor just opened nearby. Act now to protect your customers. Promote your best offer immediately.”

---

## 🚀 Running Locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open:

```
http://127.0.0.1:8000/docs
```

---

## 🌐 Deployment

This bot is deployed using Railway.

Steps:

1. Push code to GitHub
2. Connect repo to Railway
3. Ensure `Procfile` is present
4. Deploy

---

## ⚠️ Notes

* Context is stored in-memory (no database)
* On restart, context resets
* The judge handles context reloading, so this is expected

---

## ✅ Submission Ready

The bot meets all required criteria:

* Handles dynamic context
* Processes triggers correctly
* Returns structured actions
* Keeps responses under time limits

---

## 🙌 Final Note

This project focuses on simplicity and reliability rather than over-engineering. The goal is to deliver clear, useful outputs that a real merchant could act on immediately.

---
