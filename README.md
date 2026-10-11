# KisanValue

KisanValue is a full-stack Flask prototype for connecting farmers with buyers, machinery owners, compost and biochar producers, and agricultural waste-value opportunities.

## Features

- Farmer registration and login
- Buyer registration and reporting of material requirements
- Residue marketplace with listing creation and search
- Rule-based matching engine with transparent scoring
- Farm residue digital passport data structure
- HarvestPool pooling workflow
- FodderConnect, SoilRenew, FarmShare, SoilWise and FarmLoop planning modules
- Admin dashboard and demo impact reporting
- SQLite database initialization and demo seed data

## Local setup

1. Open the project folder.
2. Create and activate a virtual environment if you prefer:
   - `python -m venv .venv`
   - Windows: `.venv\Scripts\activate`
3. Install dependencies:
   - `python -m pip install -r requirements.txt`
4. Start the app:
   - `python app.py`
   - or `flask --app app run`
5. Visit `http://127.0.0.1:5000` in the browser.

## Demo login accounts

- Admin: `admin@kisanvalue.in` / `admin123`
- Farmer: `farmer@demo.in` / `demo123`
- Buyer: `buyer@demo.in` / `buyer123`
- Machinery owner: `owner@demo.in` / `owner123`

## Notes

- All demo data is clearly marked as sample material for the prototype.
- No real payment processing or buyer verification is implemented in this prototype.
- Database changes are stored in the project-level SQLite file `kisanvalue.db` unless a custom database path is configured.

## Testing

Run the included tests with:

`python -m pytest -q`
