# Metered API Billing System

## Overview

This project implements a metered API billing platform using Django REST Framework and React.

Features:

* Customer Management
* JWT Authentication
* Usage Event Ingestion
* Idempotent Event Processing
* Credit Issuance
* Invoice Generation
* Invoice Listing
* Invoice Detail API
* React Dashboard

## Tech Stack

Backend:

* Django
* Django REST Framework
* SQLite

Frontend:

* React
* Vite
* Bootstrap

## Setup

### Backend

Install dependencies:

```bash
pip install -r requirements.txt
```

Apply migrations:

```bash
python manage.py migrate
```

Run server:

```bash
python manage.py runserver
```

Backend URL:

```text
http://127.0.0.1:8000
```

### Frontend

Navigate to frontend:

```bash
cd frontend
```

Install packages:

```bash
npm install
```

Run application:

```bash
npm run dev
```

Frontend URL:

```text
http://localhost:5173
```

## Authentication

Generate JWT token:

```http
POST /api/token/
```

Example:

```json
{
  "username": "sowmy",
  "password": "admin123"
}
```

Use returned access token as:

```http
Authorization: Bearer <token>
```

## Seed Data

Generate sample customers and usage events:

```bash
python seed.py
```

## APIs

### Customers

```http
GET /ops/customers/
```

### Usage Events

```http
GET /v1/events/
POST /v1/events/create/
```

### Credits

```http
POST /ops/credits/create/
```

### Invoices

```http
GET /v1/invoices/
POST /v1/invoices/generate/
GET /v1/invoices/{invoice_id}/
```

## Design Notes

Detailed design decisions, trade-offs, scalability considerations, and security considerations are documented in:

```text
DESIGN.md
```
