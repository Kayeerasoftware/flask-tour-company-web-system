# DEHAPIZ Tour and Travel Uganda 🇺🇬

A full-stack tour company web application built with Flask for managing Uganda safari and travel packages.

## Features

- Browse and search Uganda tours (destination, price filter)
- User registration, login, and booking management
- Cancel bookings from the user dashboard
- Admin panel: add/edit/delete tours, view all bookings and contact messages
- Contact form with message storage
- Responsive design with Bootstrap 5

## Tech Stack

- **Backend:** Python / Flask, Flask-SQLAlchemy, Flask-Login
- **Database:** SQLite
- **Frontend:** Bootstrap 5, Bootstrap Icons
- **Deployment:** Gunicorn / Render-ready (Procfile included)

## Setup & Run Locally

```bash
# 1. Clone the repo
git clone <repo-url>
cd tour_company_flask

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Visit `http://127.0.0.1:5000`

## Admin Access

The database is seeded automatically on first run with sample tours and an admin account:

| Field    | Value                  |
|----------|------------------------|
| Email    | admin@dehapiz.com      |
| Password | admin123               |

Admin panel: `http://127.0.0.1:5000/admin`

## Project Structure

```
tour_company_flask/
├── app.py                  # Main Flask app, models, routes
├── requirements.txt
├── Procfile                # For deployment (gunicorn)
├── static/
│   ├── style.css
│   ├── dehapiz_logo.jpeg
│   ├── uploads/            # Tour images
│   └── team/               # Team member photos
└── templates/
    ├── base.html
    ├── index.html
    ├── tours.html
    ├── tour_detail.html
    ├── booking.html
    ├── my_bookings.html
    ├── about.html
    ├── contact.html
    ├── login.html
    ├── register.html
    └── admin/
        ├── dashboard.html
        ├── tours.html
        ├── tour_form.html
        ├── bookings.html
        └── messages.html
```

## Developer

Built by **Kayeera Nathan**  DEHAPIZ Tour and Travel Uganda as a school project
