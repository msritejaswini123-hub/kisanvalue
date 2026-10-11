import os

import pytest

from app import app, create_demo_data, init_db


@pytest.fixture
def client():
    db_path = os.path.join(os.path.dirname(__file__), 'test_kisanvalue.db')
    if os.path.exists(db_path):
        os.remove(db_path)

    app.config['TESTING'] = True
    app.config['DATABASE'] = db_path
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        with app.app_context():
            init_db()
            create_demo_data()
        yield client


def test_homepage(client):
    response = client.get('/')
    assert response.status_code == 200
    assert b'KisanValue' in response.data


def test_farmer_registration_and_login(client):
    response = client.post('/register/farmer', data={
        'full_name': 'Asha Farmer',
        'mobile': '9876543210',
        'email': 'asha@example.com',
        'password': 'secret123',
        'village': 'Sangareddy',
        'district': 'Medak',
        'state': 'Telangana',
        'pin_code': '500001',
        'land_area': '3',
        'main_crops': 'Rice',
        'language': 'English'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Login' in response.data or b'Welcome' in response.data

    login = client.post('/login', data={
        'email': 'asha@example.com',
        'password': 'secret123'
    }, follow_redirects=True)
    assert login.status_code == 200
    assert b'Farmer Dashboard' in login.data


def test_marketplace_listing_creation(client):
    client.post('/login', data={'email': 'farmer@demo.in', 'password': 'demo123'}, follow_redirects=True)
    response = client.post('/listing/new', data={
        'material_name': 'Rice Straw',
        'crop_source': 'Rice',
        'quantity': '1000',
        'unit': 'kg',
        'moisture': '12',
        'quality_notes': 'Dry and clean',
        'village': 'Madhapur',
        'district': 'Nizamabad',
        'available_date': '2026-10-20',
        'price': '2200',
        'negotiable': 'yes',
        'collection_option': 'Pickup',
        'min_order': '200',
        'status': 'Listed'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Rice Straw' in response.data


def test_matching_and_order_workflow(client):
    login = client.post('/login', data={'email': 'farmer@demo.in', 'password': 'demo123'}, follow_redirects=True)
    assert login.status_code == 200

    matches = client.get('/matches')
    assert matches.status_code == 200
    assert b'Match Score' in matches.data

    orders = client.get('/orders')
    assert orders.status_code == 200
    assert b'Orders' in orders.data


def test_admin_access(client):
    client.post('/login', data={'email': 'admin@kisanvalue.in', 'password': 'admin123'}, follow_redirects=True)
    response = client.get('/admin')
    assert response.status_code == 200
    assert b'Admin Dashboard' in response.data
