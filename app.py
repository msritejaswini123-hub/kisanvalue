import os
import sqlite3
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "kisanvalue-dev-secret-key"
app.config["DATABASE"] = os.path.join(os.path.dirname(__file__), "kisanvalue.db")


def get_db_connection():
    if "db" not in g:
        conn = sqlite3.connect(app.config["DATABASE"])
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.before_request
def ensure_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = os.urandom(16).hex()
    if request.method == "POST":
        form_token = request.form.get("_csrf")
        expected = session.get("csrf_token")
        if form_token and expected and form_token != expected:
            flash("Security validation failed. Please refresh and try again.", "error")
            return redirect(url_for("login"))


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ? AND is_active = 1",
        (user_id,),
    ).fetchone()
    return dict(user) if user else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def role_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("role") not in allowed_roles:
                flash("You do not have access to that section.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def init_db():
    conn = get_db_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            mobile TEXT,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            language TEXT DEFAULT 'English',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS farmer_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            village TEXT,
            district TEXT,
            state TEXT,
            pin_code TEXT,
            land_area REAL,
            main_crops TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS buyer_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            contact_person TEXT,
            organization_name TEXT,
            business_category TEXT,
            operating_location TEXT,
            required_materials TEXT,
            estimated_quantity TEXT,
            procurement_frequency TEXT,
            delivery_preference TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS organization_requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id INTEGER,
            material TEXT,
            quantity TEXT,
            location TEXT,
            quality_requirements TEXT,
            preferred_price REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(buyer_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS residue_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS residue_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER,
            material_name TEXT,
            crop_source TEXT,
            quantity INTEGER,
            unit TEXT,
            moisture TEXT,
            quality_notes TEXT,
            village TEXT,
            district TEXT,
            available_date TEXT,
            price REAL,
            negotiable INTEGER DEFAULT 0,
            collection_option TEXT,
            min_order INTEGER,
            status TEXT DEFAULT 'Listed',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(farmer_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS residue_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER,
            batch_id TEXT UNIQUE,
            farmer_id INTEGER,
            harvest_season TEXT,
            quantity INTEGER,
            origin_location TEXT,
            quality_info TEXT,
            intended_use TEXT,
            listing_status TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(listing_id) REFERENCES residue_listings(id),
            FOREIGN KEY(farmer_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS buyer_enquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id INTEGER,
            material TEXT,
            quantity TEXT,
            location TEXT,
            quality_requirements TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(buyer_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER,
            buyer_id INTEGER,
            offer_price REAL,
            notes TEXT,
            status TEXT DEFAULT 'Offer submitted',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(listing_id) REFERENCES residue_listings(id),
            FOREIGN KEY(buyer_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER,
            buyer_id INTEGER,
            farmer_id INTEGER,
            quantity INTEGER,
            agreed_price REAL,
            status TEXT DEFAULT 'Accepted',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(listing_id) REFERENCES residue_listings(id),
            FOREIGN KEY(buyer_id) REFERENCES users(id),
            FOREIGN KEY(farmer_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS order_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            status TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        );

        CREATE TABLE IF NOT EXISTS delivery_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            stage TEXT,
            note TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        );

        CREATE TABLE IF NOT EXISTS pooling_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            material TEXT,
            location TEXT,
            status TEXT DEFAULT 'Open',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS pooling_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            quantity INTEGER,
            material TEXT,
            approved INTEGER DEFAULT 0,
            share TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(group_id) REFERENCES pooling_groups(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS machinery_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            equipment_type TEXT,
            location TEXT,
            service_radius TEXT,
            hourly_rate REAL,
            daily_rate REAL,
            operator_availability TEXT,
            fuel_details TEXT,
            availability TEXT,
            status TEXT DEFAULT 'Available',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(owner_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS machinery_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machinery_id INTEGER,
            farmer_id INTEGER,
            requested_date TEXT,
            duration_days INTEGER,
            status TEXT DEFAULT 'Requested',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(machinery_id) REFERENCES machinery_listings(id),
            FOREIGN KEY(farmer_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS soil_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producer_id INTEGER,
            product_type TEXT,
            product_name TEXT,
            quantity TEXT,
            unit TEXT,
            price_per_unit REAL,
            production_method TEXT,
            source_material TEXT,
            quality_documentation TEXT,
            delivery_option TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(producer_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS soil_product_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            buyer_id INTEGER,
            quantity TEXT,
            status TEXT DEFAULT 'Requested',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES soil_products(id),
            FOREIGN KEY(buyer_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS soil_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            field_size TEXT,
            crop_grown TEXT,
            fertilizer_expenditure REAL,
            soil_test_results TEXT,
            compost_or_biochar TEXT,
            application_dates TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            type TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            user_id INTEGER,
            rating INTEGER,
            comment TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES soil_products(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            subject TEXT,
            details TEXT,
            status TEXT DEFAULT 'Open',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS verification_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            status TEXT DEFAULT 'Unverified',
            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )
    conn.commit()


def create_demo_data():
    conn = get_db_connection()
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count > 0:
        return

    admin_hash = generate_password_hash("admin123")
    farmer_hash = generate_password_hash("demo123")
    buyer_hash = generate_password_hash("buyer123")
    owner_hash = generate_password_hash("owner123")

    conn.execute(
        "INSERT INTO users (full_name, email, mobile, password_hash, role, language) VALUES (?, ?, ?, ?, ?, ?)",
        ("Admin User", "admin@kisanvalue.in", "9000000000", admin_hash, "admin", "English"),
    )
    conn.execute(
        "INSERT INTO users (full_name, email, mobile, password_hash, role, language) VALUES (?, ?, ?, ?, ?, ?)",
        ("Demo Farmer", "farmer@demo.in", "9123456780", farmer_hash, "farmer", "Telugu"),
    )
    conn.execute(
        "INSERT INTO users (full_name, email, mobile, password_hash, role, language) VALUES (?, ?, ?, ?, ?, ?)",
        ("Demo Buyer", "buyer@demo.in", "9988776655", buyer_hash, "buyer", "English"),
    )
    conn.execute(
        "INSERT INTO users (full_name, email, mobile, password_hash, role, language) VALUES (?, ?, ?, ?, ?, ?)",
        ("Machinery Owner", "owner@demo.in", "9876543210", owner_hash, "machinery_owner", "Hindi"),
    )

    conn.execute(
        "INSERT INTO farmer_profiles (user_id, village, district, state, pin_code, land_area, main_crops) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (2, "Madhapur", "Nizamabad", "Telangana", "503001", 4.2, "Rice, Maize"),
    )
    conn.execute(
        "INSERT INTO buyer_profiles (user_id, contact_person, organization_name, business_category, operating_location, required_materials, estimated_quantity, procurement_frequency, delivery_preference) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (3, "Ranjit Kumar", "Green Agro Energy", "Bioenergy and biomass power plants", "Warangal", "Rice straw, maize stalks", "2500 kg", "Monthly", "Collection by buyer"),
    )

    conn.execute(
        "INSERT INTO organization_requirements (buyer_id, material, quantity, location, quality_requirements, preferred_price) VALUES (?, ?, ?, ?, ?, ?)",
        (3, "Rice Straw", "1000 kg", "Nizamabad", "Dry, low contamination", 2800),
    )
    conn.execute(
        "INSERT INTO organization_requirements (buyer_id, material, quantity, location, quality_requirements, preferred_price) VALUES (?, ?, ?, ?, ?, ?)",
        (3, "Sugarcane Bagasse", "1500 kg", "Medak", "Clean, dry, low moisture", 3200),
    )

    conn.executemany(
        "INSERT INTO residue_categories (name, description) VALUES (?, ?)",
        [
            ("Rice straw and rice husk", "By-products from rice cultivation and milling"),
            ("Wheat straw", "Field residue suitable for biomass and composting"),
            ("Maize stalks and cobs", "Ideal for bioenergy, compost and feed applications"),
            ("Sugarcane bagasse and tops", "Fibrous residue from cane processing"),
            ("Cotton stalks", "Useful for biomass and composting after processing"),
            ("Groundnut shells", "Light biomass residue for processing and fuels"),
            ("Coconut husks and shells", "Coir and fibre applications"),
            ("Banana stems and fibre", "Potential feed and fibre material"),
            ("Other locally relevant agricultural by-products", "Regional residue streams and mixed feedstock"),
        ],
    )

    conn.execute(
        "INSERT INTO residue_listings (farmer_id, material_name, crop_source, quantity, unit, moisture, quality_notes, village, district, available_date, price, negotiable, collection_option, min_order, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (2, "Rice Straw", "Rice", 1000, "kg", "12%", "Dry, stackable and low weed contamination", "Madhapur", "Nizamabad", "2026-10-20", 2200, 1, "Pickup", 250, "Listed"),
    )
    conn.execute(
        "INSERT INTO residue_listings (farmer_id, material_name, crop_source, quantity, unit, moisture, quality_notes, village, district, available_date, price, negotiable, collection_option, min_order, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (2, "Maize Stalks", "Maize", 800, "kg", "18%", "Mixed with cobs; suitable after drying", "Atchampet", "Kamareddy", "2026-10-17", 1800, 1, "Collection", 200, "Listed"),
    )

    conn.execute(
        "INSERT INTO residue_batches (listing_id, batch_id, farmer_id, harvest_season, quantity, origin_location, quality_info, intended_use, listing_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (1, "RV-001", 2, "Kharif 2026", 1000, "Madhapur, Nizamabad", "Dry and clean", "Bioenergy / compost", "Listed"),
    )
    conn.execute(
        "INSERT INTO residue_batches (listing_id, batch_id, farmer_id, harvest_season, quantity, origin_location, quality_info, intended_use, listing_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (2, "RV-002", 2, "Rabi 2026", 800, "Atchampet, Kamareddy", "Moderate moisture", "Bioenergy / feed", "Listed"),
    )

    conn.execute(
        "INSERT INTO buyer_enquiries (buyer_id, material, quantity, location, quality_requirements) VALUES (?, ?, ?, ?, ?)",
        (3, "Rice Straw", "900 kg", "Nizamabad", "Dry, no plastic contamination"),
    )
    conn.execute(
        "INSERT INTO offers (listing_id, buyer_id, offer_price, notes, status) VALUES (?, ?, ?, ?, ?)",
        (1, 3, 2600, "Available for collection from village gate", "Offer submitted"),
    )
    conn.execute(
        "INSERT INTO orders (listing_id, buyer_id, farmer_id, quantity, agreed_price, status) VALUES (?, ?, ?, ?, ?, ?)",
        (1, 3, 2, 1000, 2500, "Accepted"),
    )
    conn.execute(
        "INSERT INTO order_status_history (order_id, status, notes) VALUES (?, ?, ?)",
        (1, "Accepted", "Offer accepted for demo fulfillment"),
    )
    conn.execute(
        "INSERT INTO order_status_history (order_id, status, notes) VALUES (?, ?, ?)",
        (1, "Collection scheduled", "Pickup arranged for next week"),
    )
    conn.execute(
        "INSERT INTO delivery_records (order_id, stage, note) VALUES (?, ?, ?)",
        (1, "Collection scheduled", "Vehicle will arrive on Oct 20"),
    )
    conn.execute(
        "INSERT INTO pooling_groups (title, material, location, status) VALUES (?, ?, ?, ?)",
        ("Madhapur Straw Pool", "Rice straw", "Madhapur", "Open"),
    )
    conn.execute(
        "INSERT INTO pooling_members (group_id, user_id, quantity, material, approved, share) VALUES (?, ?, ?, ?, ?, ?)",
        (1, 2, 250, "Rice straw", 1, "25% share"),
    )
    conn.execute(
        "INSERT INTO machinery_listings (owner_id, equipment_type, location, service_radius, hourly_rate, daily_rate, operator_availability, fuel_details, availability, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (4, "Baler", "Nizamabad", "25 km", 850, 4200, "Operator available", "Diesel included", "Available in 3 days", "Available"),
    )
    conn.execute(
        "INSERT INTO machinery_bookings (machinery_id, farmer_id, requested_date, duration_days, status) VALUES (?, ?, ?, ?, ?)",
        (1, 2, "2026-10-22", 1, "Approved"),
    )
    conn.execute(
        "INSERT INTO soil_products (producer_id, product_type, product_name, quantity, unit, price_per_unit, production_method, source_material, quality_documentation, delivery_option) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (4, "Compost", "Farm Fresh Compost", "400", "kg", 18, "Windrow composting", "Crop residues and cattle manure", "Sample quality record", "Delivery"),
    )
    conn.execute(
        "INSERT INTO soil_product_orders (product_id, buyer_id, quantity, status) VALUES (?, ?, ?, ?)",
        (1, 2, "200 kg", "Delivered"),
    )
    conn.execute(
        "INSERT INTO soil_records (user_id, field_size, crop_grown, fertilizer_expenditure, soil_test_results, compost_or_biochar, application_dates, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (2, "2 acres", "Rice", 8500, "pH 6.8, N moderate", "Compost applied 2 weeks before sowing", "2026-07-12", "Soil structure improved, sample notes only"),
    )
    conn.execute(
        "INSERT INTO notifications (user_id, message, type) VALUES (?, ?, ?)",
        (2, "Buyer enquiry received for your rice straw listing.", "enquiry"),
    )
    conn.execute(
        "INSERT INTO notifications (user_id, message, type) VALUES (?, ?, ?)",
        (2, "Machinery booking approved for baler service.", "booking"),
    )
    conn.execute(
        "INSERT INTO verification_requests (user_id, category, status, notes) VALUES (?, ?, ?, ?)",
        (3, "Buyer verification", "Documents submitted", "Sample business registration is pending review.")
    )

    conn.commit()


def get_role_label(role):
    labels = {
        "farmer": "Farmer",
        "buyer": "Buyer",
        "machinery_owner": "Machinery Owner",
        "admin": "Administrator",
    }
    return labels.get(role, "User")


@app.route("/")
def home():
    conn = get_db_connection()
    counts = {
        "listings": conn.execute("SELECT COUNT(*) FROM residue_listings").fetchone()[0],
        "farmers": conn.execute("SELECT COUNT(*) FROM users WHERE role = 'farmer'").fetchone()[0],
        "buyers": conn.execute("SELECT COUNT(*) FROM users WHERE role = 'buyer'").fetchone()[0],
    }
    return render_template("index.html", counts=counts)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1",
            (email,),
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["full_name"] = user["full_name"]
            flash(f"Welcome back, {user['full_name']}.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid login details. Please try again.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/register/farmer", methods=["GET", "POST"])
def register_farmer():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        mobile = request.form.get("mobile")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password")
        village = request.form.get("village")
        district = request.form.get("district")
        state = request.form.get("state")
        pin_code = request.form.get("pin_code")
        land_area = request.form.get("land_area")
        main_crops = request.form.get("main_crops")
        language = request.form.get("language")

        conn = get_db_connection()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            flash("An account with that email already exists.", "error")
            return render_template("register_farmer.html")

        hashed = generate_password_hash(password)
        user = conn.execute(
            "INSERT INTO users (full_name, email, mobile, password_hash, role, language) VALUES (?, ?, ?, ?, 'farmer', ?)",
            (full_name, email, mobile, hashed, language),
        )
        user_id = user.lastrowid
        conn.execute(
            "INSERT INTO farmer_profiles (user_id, village, district, state, pin_code, land_area, main_crops) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, village, district, state, pin_code, land_area, main_crops),
        )
        conn.execute(
            "INSERT INTO notifications (user_id, message, type) VALUES (?, ?, ?)",
            (user_id, "Your farmer profile has been created. Start by listing your residue or checking buyer matches.", "system"),
        )
        conn.commit()
        flash("Farmer registration successful. Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register_farmer.html")


@app.route("/register/buyer", methods=["GET", "POST"])
def register_buyer():
    if request.method == "POST":
        contact_person = request.form.get("contact_person")
        organization_name = request.form.get("organization_name")
        email = request.form.get("email", "").strip().lower()
        mobile = request.form.get("mobile")
        password = request.form.get("password")
        business_category = request.form.get("business_category")
        operating_location = request.form.get("operating_location")
        required_materials = request.form.get("required_materials")
        estimated_quantity = request.form.get("estimated_quantity")
        procurement_frequency = request.form.get("procurement_frequency")
        delivery_preference = request.form.get("delivery_preference")

        conn = get_db_connection()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            flash("An account with that email already exists.", "error")
            return render_template("register_buyer.html")

        hashed = generate_password_hash(password)
        user = conn.execute(
            "INSERT INTO users (full_name, email, mobile, password_hash, role) VALUES (?, ?, ?, ?, 'buyer')",
            (contact_person, email, mobile, hashed),
        )
        user_id = user.lastrowid
        conn.execute(
            "INSERT INTO buyer_profiles (user_id, contact_person, organization_name, business_category, operating_location, required_materials, estimated_quantity, procurement_frequency, delivery_preference) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, contact_person, organization_name, business_category, operating_location, required_materials, estimated_quantity, procurement_frequency, delivery_preference),
        )
        conn.execute(
            "INSERT INTO verification_requests (user_id, category, status, notes) VALUES (?, ?, ?, ?)",
            (user_id, "Buyer verification", "Unverified", "Business details submitted for verification review."),
        )
        conn.commit()
        flash("Buyer registration successful. Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register_buyer.html")


@app.route("/register/machinery-owner", methods=["GET", "POST"])
def register_machinery_owner():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email", "").strip().lower()
        mobile = request.form.get("mobile")
        password = request.form.get("password")
        location = request.form.get("location")
        equipment_type = request.form.get("equipment_type")

        conn = get_db_connection()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            flash("An account with that email already exists.", "error")
            return render_template("register_machinery_owner.html")

        user = conn.execute(
            "INSERT INTO users (full_name, email, mobile, password_hash, role) VALUES (?, ?, ?, ?, 'machinery_owner')",
            (full_name, email, mobile, generate_password_hash(password)),
        )
        user_id = user.lastrowid
        conn.execute(
            "INSERT INTO machinery_listings (owner_id, equipment_type, location, service_radius, hourly_rate, daily_rate, operator_availability, fuel_details, availability, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, equipment_type, location, "50 km", 700, 3500, "Available on request", "Fuel details provided by owner", "Available", "Available")
        )
        conn.commit()
        flash("Machinery-owner registration successful. Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register_machinery_owner.html")


@app.route("/dashboard")
@login_required
def dashboard():
    user = get_current_user()
    role = user["role"]
    conn = get_db_connection()
    if role == "farmer":
        listings = conn.execute("SELECT * FROM residue_listings WHERE farmer_id = ? ORDER BY created_at DESC LIMIT 5", (user["id"],)).fetchall()
        orders = conn.execute("SELECT * FROM orders WHERE farmer_id = ? ORDER BY created_at DESC LIMIT 5", (user["id"],)).fetchall()
        notifications = conn.execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 5", (user["id"],)).fetchall()
        return render_template("dashboard.html", user=user, listings=listings, orders=orders, notifications=notifications, title="Farmer Dashboard")
    if role == "buyer":
        enquiries = conn.execute("SELECT * FROM buyer_enquiries WHERE buyer_id = ? ORDER BY created_at DESC LIMIT 5", (user["id"],)).fetchall()
        offers = conn.execute("SELECT * FROM offers WHERE buyer_id = ? ORDER BY created_at DESC LIMIT 5", (user["id"],)).fetchall()
        return render_template("dashboard.html", user=user, enquiries=enquiries, offers=offers, title="Buyer Dashboard")
    if role == "machinery_owner":
        listings = conn.execute("SELECT * FROM machinery_listings WHERE owner_id = ? ORDER BY created_at DESC LIMIT 5", (user["id"],)).fetchall()
        return render_template("dashboard.html", user=user, listings=listings, title="Machinery Owner Dashboard")
    if role == "admin":
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        listing_count = conn.execute("SELECT COUNT(*) FROM residue_listings").fetchone()[0]
        return render_template("admin.html", user=user, user_count=user_count, listing_count=listing_count, title="Admin Dashboard")
    return render_template("dashboard.html", user=user, title="Dashboard")


@app.route("/marketplace")
def marketplace():
    conn = get_db_connection()
    search = request.args.get("q", "")
    material = request.args.get("material", "")
    query = "SELECT * FROM residue_listings WHERE status != 'Deleted'"
    params = []
    if search:
        query += " AND (material_name LIKE ? OR crop_source LIKE ? OR district LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if material:
        query += " AND material_name = ?"
        params.append(material)
    query += " ORDER BY created_at DESC"
    listings = conn.execute(query, params).fetchall()
    categories = conn.execute("SELECT name FROM residue_categories ORDER BY name").fetchall()
    return render_template("marketplace.html", listings=listings, categories=categories, search=search, material=material)


@app.route("/listing/new", methods=["GET", "POST"])
@login_required
@role_required("farmer")
def create_listing():
    if request.method == "POST":
        material_name = request.form.get("material_name")
        crop_source = request.form.get("crop_source")
        quantity = int(request.form.get("quantity") or 0)
        unit = request.form.get("unit")
        moisture = request.form.get("moisture")
        quality_notes = request.form.get("quality_notes")
        village = request.form.get("village")
        district = request.form.get("district")
        available_date = request.form.get("available_date")
        price = float(request.form.get("price") or 0)
        negotiable = 1 if request.form.get("negotiable") == "yes" else 0
        collection_option = request.form.get("collection_option")
        min_order = int(request.form.get("min_order") or 0)
        status = request.form.get("status") or "Listed"

        conn = get_db_connection()
        listing = conn.execute(
            "INSERT INTO residue_listings (farmer_id, material_name, crop_source, quantity, unit, moisture, quality_notes, village, district, available_date, price, negotiable, collection_option, min_order, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session["user_id"], material_name, crop_source, quantity, unit, moisture, quality_notes, village, district, available_date, price, negotiable, collection_option, min_order, status),
        )
        listing_id = listing.lastrowid
        batch_id = f"RV-{listing_id:03d}"
        conn.execute(
            "INSERT INTO residue_batches (listing_id, batch_id, farmer_id, harvest_season, quantity, origin_location, quality_info, intended_use, listing_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (listing_id, batch_id, session["user_id"], "Current season", quantity, f"{village}, {district}", quality_notes, "Biomass / compost pathway", status),
        )
        conn.execute(
            "INSERT INTO notifications (user_id, message, type) VALUES (?, ?, ?)",
            (session["user_id"], f"Your {material_name} listing is live on the marketplace.", "listing"),
        )
        conn.commit()
        flash("Listing created successfully.", "success")
        return redirect(url_for("listing_detail", id=listing_id))
    return render_template("create_listing.html")


@app.route("/listing/<int:id>")
def listing_detail(id):
    conn = get_db_connection()
    listing = conn.execute("SELECT * FROM residue_listings WHERE id = ?", (id,)).fetchone()
    if not listing:
        flash("Listing not found.", "error")
        return redirect(url_for("marketplace"))
    offers = conn.execute("SELECT * FROM offers WHERE listing_id = ? ORDER BY created_at DESC", (id,)).fetchall()
    return render_template("listing_detail.html", listing=listing, offers=offers)


@app.route("/buyers/requirements", methods=["GET", "POST"])
@login_required
@role_required("buyer")
def buyer_requirements():
    conn = get_db_connection()
    if request.method == "POST":
        conn.execute(
            "INSERT INTO organization_requirements (buyer_id, material, quantity, location, quality_requirements, preferred_price) VALUES (?, ?, ?, ?, ?, ?)",
            (
                session["user_id"],
                request.form.get("material"),
                request.form.get("quantity"),
                request.form.get("location"),
                request.form.get("quality_requirements"),
                float(request.form.get("preferred_price") or 0),
            ),
        )
        conn.commit()
        flash("Your material requirement has been added.", "success")
    requirements = conn.execute("SELECT * FROM organization_requirements WHERE buyer_id = ? ORDER BY created_at DESC", (session["user_id"],)).fetchall()
    return render_template("buyers_requirements.html", requirements=requirements)


@app.route("/matches")
def matches():
    conn = get_db_connection()
    listings = conn.execute("SELECT * FROM residue_listings ORDER BY created_at DESC").fetchall()
    requirements = conn.execute("SELECT * FROM organization_requirements ORDER BY created_at DESC").fetchall()
    results = []
    for listing in listings:
        material_bonus = 25 if listing["material_name"].lower() in {"rice straw", "maize stalks", "sugarcane bagasse"} else 10
        quantity_bonus = min(20, int(listing["quantity"]) // 50)
        distance_bonus = 15 if listing["district"] in {"Nizamabad", "Medak", "Warangal"} else 8
        quality_bonus = 15 if listing["quality_notes"] and "dry" in listing["quality_notes"].lower() else 10
        buyer_demand = 20 if any(req["material"].lower() == listing["material_name"].lower() for req in requirements) else 8
        score = min(100, material_bonus + quantity_bonus + distance_bonus + quality_bonus + buyer_demand)
        reasons = [
            f"Material compatibility: +{material_bonus}",
            f"Quantity fit: +{quantity_bonus}",
            f"Distance fit: +{distance_bonus}",
            f"Quality fit: +{quality_bonus}",
            f"Buyer demand: +{buyer_demand}",
        ]
        if listing["price"]:
            net_earnings = max(listing["price"] - 350, 0)
        else:
            net_earnings = 0
        results.append({
            "listing": listing,
            "score": score,
            "reasons": reasons,
            "net_earnings": net_earnings,
        })
    results.sort(key=lambda item: item["score"], reverse=True)
    return render_template("matches.html", matches=results)


@app.route("/harvest-pool", methods=["GET", "POST"])
@login_required
@role_required("farmer")
def harvest_pool():
    conn = get_db_connection()
    if request.method == "POST":
        conn.execute(
            "INSERT INTO pooling_groups (title, material, location, status) VALUES (?, ?, ?, 'Open')",
            (request.form.get("title"), request.form.get("material"), request.form.get("location")),
        )
        conn.commit()
        flash("Pooling group created. Farmers can now join the cluster.", "success")
    groups = conn.execute("SELECT * FROM pooling_groups ORDER BY created_at DESC").fetchall()
    members = conn.execute("SELECT * FROM pooling_members ORDER BY created_at DESC").fetchall()
    return render_template("harvest_pool.html", groups=groups, members=members)


@app.route("/fodder-connect")
def fodder_connect():
    conn = get_db_connection()
    feed_materials = conn.execute("SELECT * FROM residue_listings WHERE material_name IN ('Rice Straw', 'Maize Stalks', 'Banana Stem', 'Sugarcane Bagasse') ORDER BY created_at DESC LIMIT 10").fetchall()
    requirements = conn.execute("SELECT * FROM buyer_enquiries ORDER BY created_at DESC LIMIT 10").fetchall()
    return render_template("fodder_connect.html", feed_materials=feed_materials, requirements=requirements)


@app.route("/soil-renew", methods=["GET", "POST"])
@login_required
def soil_renew():
    conn = get_db_connection()
    if request.method == "POST":
        conn.execute(
            "INSERT INTO soil_products (producer_id, product_type, product_name, quantity, unit, price_per_unit, production_method, source_material, quality_documentation, delivery_option) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session["user_id"],
                request.form.get("product_type"),
                request.form.get("product_name"),
                request.form.get("quantity"),
                request.form.get("unit"),
                float(request.form.get("price_per_unit") or 0),
                request.form.get("production_method"),
                request.form.get("source_material"),
                request.form.get("quality_documentation"),
                request.form.get("delivery_option"),
            ),
        )
        conn.commit()
        flash("Soil amendment listing created.", "success")
    products = conn.execute("SELECT * FROM soil_products ORDER BY created_at DESC").fetchall()
    return render_template("soil_renew.html", products=products)


@app.route("/farm-share", methods=["GET", "POST"])
@login_required
@role_required("machinery_owner")
def farm_share():
    conn = get_db_connection()
    if request.method == "POST":
        conn.execute(
            "INSERT INTO machinery_listings (owner_id, equipment_type, location, service_radius, hourly_rate, daily_rate, operator_availability, fuel_details, availability, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Available')",
            (
                session["user_id"],
                request.form.get("equipment_type"),
                request.form.get("location"),
                request.form.get("service_radius"),
                float(request.form.get("hourly_rate") or 0),
                float(request.form.get("daily_rate") or 0),
                request.form.get("operator_availability"),
                request.form.get("fuel_details"),
                request.form.get("availability"),
            ),
        )
        conn.commit()
        flash("Machinery listing added to FarmShare.", "success")
    listings = conn.execute("SELECT * FROM machinery_listings ORDER BY created_at DESC").fetchall()
    return render_template("farm_share.html", listings=listings)


@app.route("/soil-wise", methods=["GET", "POST"])
@login_required
@role_required("farmer")
def soil_wise():
    conn = get_db_connection()
    if request.method == "POST":
        conn.execute(
            "INSERT INTO soil_records (user_id, field_size, crop_grown, fertilizer_expenditure, soil_test_results, compost_or_biochar, application_dates, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session["user_id"],
                request.form.get("field_size"),
                request.form.get("crop_grown"),
                float(request.form.get("fertilizer_expenditure") or 0),
                request.form.get("soil_test_results"),
                request.form.get("compost_or_biochar"),
                request.form.get("application_dates"),
                request.form.get("notes"),
            ),
        )
        conn.commit()
        flash("Soil and input record saved.", "success")
    records = conn.execute("SELECT * FROM soil_records WHERE user_id = ? ORDER BY created_at DESC", (session["user_id"],)).fetchall()
    return render_template("soil_wise.html", records=records)


@app.route("/farm-loop", methods=["GET", "POST"])
def farm_loop():
    if request.method == "POST":
        crop = request.form.get("crop_grown")
        residue = request.form.get("residue_generated")
        quantity = request.form.get("approx_quantity")
        buyer = request.form.get("buyer_availability")
        machinery = request.form.get("needs_machinery")
        reuse = request.form.get("reuse_path")
        flash(f"Planner scenario generated for {crop} with {residue}. Estimated net value to compare before finalising the route.", "success")
        return render_template("farm_loop.html", scenario={"crop": crop, "residue": residue, "quantity": quantity, "buyer": buyer, "machinery": machinery, "reuse": reuse})
    return render_template("farm_loop.html")


@app.route("/orders", methods=["GET", "POST"])
@login_required
def orders():
    conn = get_db_connection()
    if request.method == "POST" and request.form.get("accept_offer"):
        offer_id = int(request.form.get("accept_offer"))
        offer = conn.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if offer:
            conn.execute(
                "INSERT INTO orders (listing_id, buyer_id, farmer_id, quantity, agreed_price, status) VALUES (?, ?, ?, ?, ?, 'Accepted')",
                (offer["listing_id"], offer["buyer_id"], session["user_id"], 1000, offer["offer_price"]),
            )
            conn.execute("UPDATE offers SET status = 'Accepted' WHERE id = ?", (offer_id,))
            conn.commit()
            flash("Offer accepted and a simulated order is now active.", "success")
    role = session.get("role")
    if role == "farmer":
        rows = conn.execute("SELECT * FROM orders WHERE farmer_id = ? ORDER BY created_at DESC", (session["user_id"],)).fetchall()
        offers = conn.execute("SELECT * FROM offers WHERE listing_id IN (SELECT id FROM residue_listings WHERE farmer_id = ?) ORDER BY created_at DESC", (session["user_id"],)).fetchall()
    elif role == "buyer":
        rows = conn.execute("SELECT * FROM orders WHERE buyer_id = ? ORDER BY created_at DESC", (session["user_id"],)).fetchall()
        offers = conn.execute("SELECT * FROM offers WHERE buyer_id = ? ORDER BY created_at DESC", (session["user_id"],)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 10").fetchall()
        offers = conn.execute("SELECT * FROM offers ORDER BY created_at DESC LIMIT 10").fetchall()
    return render_template("orders.html", orders_list=rows, offers=offers)


@app.route("/impact")
def impact():
    conn = get_db_connection()
    metrics = {
        "listed": conn.execute("SELECT SUM(quantity) FROM residue_listings").fetchone()[0] or 0,
        "sold": conn.execute("SELECT SUM(quantity) FROM orders").fetchone()[0] or 0,
        "farmers": conn.execute("SELECT COUNT(*) FROM users WHERE role = 'farmer'").fetchone()[0],
        "buyers": conn.execute("SELECT COUNT(*) FROM users WHERE role = 'buyer'").fetchone()[0],
        "complete_transactions": conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'Accepted'").fetchone()[0],
        "earnings": conn.execute("SELECT COALESCE(SUM(agreed_price),0) FROM orders").fetchone()[0],
    }
    return render_template("impact.html", metrics=metrics)


@app.route("/admin")
@login_required
@role_required("admin")
def admin_dashboard():
    conn = get_db_connection()
    users = conn.execute("SELECT id, full_name, email, role FROM users ORDER BY created_at DESC LIMIT 20").fetchall()
    complaints = conn.execute("SELECT * FROM complaints ORDER BY created_at DESC LIMIT 10").fetchall()
    verification = conn.execute("SELECT * FROM verification_requests ORDER BY submitted_at DESC LIMIT 10").fetchall()
    return render_template("admin.html", users=users, complaints=complaints, verification=verification, title="Admin Dashboard")


@app.route("/admin/approve-user/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def approve_user(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE verification_requests SET status = 'Verified' WHERE user_id = ?", (user_id,))
    conn.execute("INSERT INTO audit_logs (user_id, action, details) VALUES (?, ?, ?)", (session["user_id"], "Buyer verification approved", f"User {user_id} was marked verified."))
    conn.commit()
    flash("Verification record updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.context_processor
def context_for_templates():
    return {
        "current_user": get_current_user(),
        "session_roles": ["farmer", "buyer", "machinery_owner", "admin"],
    }


@app.route("/sample-data")
def sample_data():
    return "Demo data labels are shown throughout the prototype, and all sample records should be treated as demonstration only."



with app.app_context():
    init_db()
    create_demo_data()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
