import os
import pytest
import tempfile
import json
import uuid

from app import app, db, User, Products, ROLES

@pytest.fixture
def client():
    # Store original configuration
    original_db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    original_testing = app.config.get('TESTING', False)
    original_jwt_key = app.config.get('JWT_SECRET_KEY')
    
    # Create a temporary database file
    db_fd, db_path = tempfile.mkstemp()
    
    # Override app configuration for testing
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['JWT_SECRET_KEY'] = 'test-secret-key'
    
    # Create test client
    test_client = app.test_client()
    
    # Create the database and tables
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        # Create test users
        admin_username = 'admin_test'
        admin_email = f'admin_{uuid.uuid4()}@test.com'
        
        admin = User(
            username=admin_username,
            email=admin_email,
            role=ROLES['admin']
        )
        admin.set_password('admin123')
        
        user_username = 'user_test'
        user_email = f'user_{uuid.uuid4()}@test.com'
        
        user = User(
            username=user_username,
            email=user_email,
            role=ROLES['user']
        )
        user.set_password('user123')
        
        db.session.add(admin)
        db.session.add(user)
        db.session.commit()
    
    # Pass admin and user credentials to tests
    test_client.admin_credentials = {
        'username': admin_username,
        'email': admin_email,
        'password': 'admin123'
    }
    
    test_client.user_credentials = {
        'username': user_username,
        'email': user_email,
        'password': 'user123'
    }
    
    yield test_client
    
    # Clean up and restore original configuration
    with app.app_context():
        db.session.remove()
        db.drop_all()
    
    app.config['TESTING'] = original_testing
    app.config['SQLALCHEMY_DATABASE_URI'] = original_db_uri
    app.config['JWT_SECRET_KEY'] = original_jwt_key
    
    # Close and remove the temporary database
    os.close(db_fd)
    os.unlink(db_path)

def get_auth_headers(client, username, password):
    """Helper function to get JWT auth headers"""
    response = client.post('/api/login', json={
        'username': username,
        'password': password
    })
    data = json.loads(response.data)
    return {
        'Authorization': f'Bearer {data["access_token"]}'
    }

# ===== AUTHENTICATION TESTS =====

def test_home_endpoint(client):
    """Test the home endpoint"""
    response = client.get('/')
    assert response.status_code == 200
    assert b"Catalog API is running" in response.data

def test_register_success(client):
    """Test successful user registration"""
    response = client.post('/api/register', json={
        'username': f'newuser_{uuid.uuid4().hex[:8]}',
        'email': f'new_{uuid.uuid4().hex[:8]}@user.com',
        'password': 'password123'
    })
    assert response.status_code == 201
    assert b"User created successfully" in response.data

def test_register_missing_fields(client):
    """Test registration with missing fields"""
    # Missing password
    response = client.post('/api/register', json={
        'username': 'another',
        'email': 'another@user.com'
    })
    assert response.status_code == 400
    assert b"password is required" in response.data
    
    # Missing email
    response = client.post('/api/register', json={
        'username': 'another',
        'password': 'password123'
    })
    assert response.status_code == 400
    assert b"email is required" in response.data

def test_register_duplicate_username(client):
    """Test registration with duplicate username"""
    unique_username = f'duplicate_{uuid.uuid4().hex[:8]}'
    
    # First registration
    client.post('/api/register', json={
        'username': unique_username,
        'email': f'first_{uuid.uuid4().hex[:8]}@user.com',
        'password': 'password123'
    })
    
    # Second registration with same username
    response = client.post('/api/register', json={
        'username': unique_username,
        'email': f'second_{uuid.uuid4().hex[:8]}@user.com',
        'password': 'password123'
    })
    
    assert response.status_code == 400
    assert b"Username already exists" in response.data

def test_login_success(client):
    """Test successful login"""
    response = client.post('/api/login', json={
        'username': client.admin_credentials['username'],
        'password': client.admin_credentials['password']
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["username"] == "admin_test"
    assert data["user"]["role"] == "admin"

def test_login_invalid_credentials(client):
    """Test login with invalid credentials"""
    response = client.post('/api/login', json={
        'username': client.admin_credentials['username'],
        'password': 'wrong_password'
    })
    assert response.status_code == 401
    assert b"Invalid username or password" in response.data

# ===== PRODUCT CRUD TESTS =====

def test_get_products_unauthorized(client):
    """Test getting products without authentication"""
    response = client.get('/api/products')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)

def test_create_product_success(client):
    """Test creating a product with authentication"""
    headers = get_auth_headers(client, client.admin_credentials['username'], client.admin_credentials['password'])
    
    response = client.post('/api/products', json={
        'name': 'Test Product',
        'description': 'A test product',
        'price': 99.99,
        'product_image_url': 'http://example.com/image.jpg'
    }, headers=headers)
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert "id" in data

def test_create_product_unauthorized(client):
    """Test creating a product without authentication"""
    response = client.post('/api/products', json={
        'name': 'Unauthorized Product',
        'description': 'Should not be created',
        'price': 50.00
    })
    
    assert response.status_code == 401

def test_get_single_product(client):
    """Test getting a single product"""
    # First create a product
    headers = get_auth_headers(client, 'admin_test', 'admin123')
    
    create_response = client.post('/api/products', json={
        'name': 'Get Single Test',
        'description': 'Testing get single product',
        'price': 29.99
    }, headers=headers)
    
    product_id = json.loads(create_response.data)["id"]
    
    # Now get the product
    response = client.get(f'/api/products/{product_id}')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["name"] == "Get Single Test"
    assert data["price"] == 29.99

def test_update_product(client):
    """Test updating a product"""
    # First create a product as admin
    admin_headers = get_auth_headers(client, client.admin_credentials['username'], client.admin_credentials['password'])
    
    create_response = client.post('/api/products', json={
        'name': 'Update Test',
        'description': 'Original description',
        'price': 59.99
    }, headers=admin_headers)
    
    product_id = json.loads(create_response.data)["id"]
    
    # Update the product
    update_response = client.put(f'/api/products/{product_id}', json={
        'name': 'Updated Name',
        'price': 69.99
    }, headers=admin_headers)
    
    assert update_response.status_code == 200
    
    # Check that the product was updated
    get_response = client.get(f'/api/products/{product_id}')
    data = json.loads(get_response.data)
    assert data["name"] == "Updated Name"
    assert data["price"] == 69.99
    assert data["description"] == "Original description"  # Unchanged

def test_delete_product(client):
    """Test deleting a product"""
    # First create a product as admin
    admin_headers = get_auth_headers(client, client.admin_credentials['username'], client.admin_credentials['password'])
    
    create_response = client.post('/api/products', json={
        'name': 'Delete Test',
        'price': 19.99
    }, headers=admin_headers)
    
    product_id = json.loads(create_response.data)["id"]
    
    # Delete the product
    delete_response = client.delete(f'/api/products/{product_id}', headers=admin_headers)
    assert delete_response.status_code == 200
    
    # Check that the product is gone
    get_response = client.get(f'/api/products/{product_id}')
    assert get_response.status_code == 404

# ===== RBAC TESTS =====

def test_rbac_regular_user_cannot_delete_admin_product(client):
    """Test that a regular user cannot delete a product created by an admin"""
    # Create product as admin
    admin_headers = get_auth_headers(client, client.admin_credentials['username'], client.admin_credentials['password'])
    
    create_response = client.post('/api/products', json={
        'name': 'Admin Product',
        'price': 149.99
    }, headers=admin_headers)
    
    product_id = json.loads(create_response.data)["id"]
    
    # Try to delete as regular user
    user_headers = get_auth_headers(client, client.user_credentials['username'], client.user_credentials['password'])
    delete_response = client.delete(f'/api/products/{product_id}', headers=user_headers)
    
    assert delete_response.status_code == 403
    assert b"Not authorized to delete this product" in delete_response.data

def test_rbac_admin_can_delete_user_product(client):
    """Test that an admin can delete a product created by a regular user"""
    # Create product as regular user
    user_headers = get_auth_headers(client, client.user_credentials['username'], client.user_credentials['password'])
    
    create_response = client.post('/api/products', json={
        'name': 'User Product',
        'price': 39.99
    }, headers=user_headers)
    
    product_id = json.loads(create_response.data)["id"]
    
    # Delete as admin
    admin_headers = get_auth_headers(client, client.admin_credentials['username'], client.admin_credentials['password'])
    delete_response = client.delete(f'/api/products/{product_id}', headers=admin_headers)
    
    assert delete_response.status_code == 200
    assert b"Product deleted" in delete_response.data

def test_rbac_user_can_modify_own_product(client):
    """Test that a user can modify their own product"""
    # Create product as regular user
    user_headers = get_auth_headers(client, client.user_credentials['username'], client.user_credentials['password'])
    
    create_response = client.post('/api/products', json={
        'name': 'My Product',
        'description': 'Original description',
        'price': 89.99
    }, headers=user_headers)
    
    product_id = json.loads(create_response.data)["id"]
    
    # Update own product
    update_response = client.put(f'/api/products/{product_id}', json={
        'name': 'My Updated Product',
        'price': 94.99
    }, headers=user_headers)
    
    assert update_response.status_code == 200
    
    # Check that the product was updated
    get_response = client.get(f'/api/products/{product_id}')
    data = json.loads(get_response.data)
    assert data["name"] == "My Updated Product"
