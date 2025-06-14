                                                    
from flask import Flask, jsonify, request, make_response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import os
from functools import wraps
from flasgger import Swagger, swag_from
from flask_cors import CORS

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(os.path.abspath(os.path.dirname(__file__)), "catalog.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "your-secret-key-here")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)

# Swagger configuration
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
    "title": "Catalog API",
    "version": "1.0.0",
    "description": "A Flask API with JWT authentication and CRUD operations",
    "termsOfService": "",
    "contact": {
        "email": "admin@example.com"
    },
    "license": {
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    },
}

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)
swagger = Swagger(app, config=swagger_config)

# Enable CORS for all routes and origins
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

@app.route('/api/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh access token using valid refresh token
    ---
    tags:
      - Authentication
    security:
      - JWT: []
    responses:
      200:
        description: Access token refreshed
        schema:
          type: object
          properties:
            access_token:
              type: string
              description: New JWT access token
      401:
        description: Invalid or expired refresh token
    """
    try:
        current_user = get_jwt_identity()
        new_access_token = create_access_token(identity=current_user)
        return jsonify(access_token=new_access_token), 200
    except Exception as e:
        return jsonify(msg="Token refresh failed", error=str(e)), 401

# User roles
ROLES = {
    'admin': 'admin',
    'user': 'user'
}

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLES['user'])
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Products(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    product_image_url = db.Column(db.String(500))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

# Helper function for role-based access
def role_required(role):
    def wrapper(fn):
        @wraps(fn)
        @jwt_required()
        def decorator(*args, **kwargs):
            current_user = User.query.get(get_jwt_identity())
            if current_user.role != role:
                return jsonify({"msg": "Insufficient permissions"}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper

# Initialize the database
with app.app_context():
    db.create_all()
    # Create admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@example.com',
            role=ROLES['admin']
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

@app.route("/", methods=["GET"])
@swag_from({
    "responses": {
        "200": {
            "description": "Welcome message",
            "schema": {
                "type": "object",
                "properties": {
                    "msg": {"type": "string"}
                }
            }
        }
    }
})
def home():
    """Home endpoint
    This is the home endpoint of our API
    ---
    """
    return jsonify({"msg": "Welcome to the Products API!"})

# Auth endpoints
@app.route("/api/register", methods=["POST"])
@swag_from({
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "email": {"type": "string"},
                    "password": {"type": "string"},
                    "role": {"type": "string", "enum": ["admin", "user"]}
                },
                "required": ["username", "email", "password"]
            }
        }
    ],
    "responses": {
        "201": {
            "description": "User registered successfully"
        },
        "400": {
            "description": "Missing required fields or duplicate username/email"
        }
    }
})
def register():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['username', 'email', 'password']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"msg": f"{field} is required"}), 400
    
    # Check if username or email already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({"msg": "Username already exists"}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"msg": "Email already registered"}), 400
        
    user = User(
        username=data['username'],
        email=data['email'],
        role=ROLES.get(data.get('role', 'user'))
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({"msg": "User created successfully"}), 201

@app.route("/api/login", methods=["POST"])
@swag_from({
    "parameters": [
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "password": {"type": "string"}
                },
                "required": ["username", "password"]
            }
        }
    ],
    "responses": {
        "200": {
            "description": "Login successful",
            "schema": {
                "type": "object",
                "properties": {
                    "access_token": {"type": "string"},
                    "refresh_token": {"type": "string"},
                    "user": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "username": {"type": "string"},
                            "email": {"type": "string"},
                            "role": {"type": "string"}
                        }
                    }
                }
            }
        },
        "401": {
            "description": "Invalid username or password"
        }
    }
})
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data.get('username')).first()
    
    if not user or not user.check_password(data.get('password')):
        return jsonify({"msg": "Invalid username or password"}), 401
        
    access_token = create_access_token(identity=user.username)
    refresh_token = create_refresh_token(identity=user.username)
    
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    }), 200

# Product endpoints
@app.route("/api/products", methods=["GET"])
@jwt_required(optional=True)
@swag_from({
    "parameters": [
        {
            "name": "Authorization",
            "in": "header",
            "type": "string",
            "required": False,
            "description": "Bearer {token}"
        }
    ],
    "responses": {
        "200": {
            "description": "List of products",
            "schema": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "price": {"type": "number"},
                        "product_image_url": {"type": "string"},
                        "created_by": {"type": "integer"},
                        "created_at": {"type": "string"},
                        "updated_at": {"type": "string"}
                    }
                }
            }
        }
    }
})
def get_products():
    try:
        products = Products.query.all()
        return jsonify([{
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "price": p.price,
            "product_image_url": p.product_image_url,
            "created_by": p.created_by,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None
        } for p in products])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/products/<int:product_id>", methods=["GET"])
@jwt_required(optional=True)
@swag_from({
    "parameters": [
        {
            "name": "product_id",
            "in": "path",
            "type": "integer",
            "required": True
        }
    ],
    "responses": {
        "200": {
            "description": "Product details",
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "price": {"type": "number"},
                    "product_image_url": {"type": "string"},
                    "created_by": {"type": "integer"},
                    "created_at": {"type": "string"},
                    "updated_at": {"type": "string"}
                }
            }
        },
        "404": {
            "description": "Product not found"
        }
    }
})
def get_product(product_id):
    product = Products.query.get_or_404(product_id)
    return jsonify({
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "product_image_url": product.product_image_url,
        "created_by": product.created_by,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None
    })

@app.route("/api/products", methods=["POST"])
@jwt_required()
@swag_from({
    "parameters": [
        {
            "name": "Authorization",
            "in": "header",
            "type": "string",
            "required": True,
            "description": "Bearer {token}"
        },
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "price": {"type": "number"},
                    "product_image_url": {"type": "string"}
                },
                "required": ["name", "price"]
            }
        }
    ],
    "responses": {
        "201": {
            "description": "Product created",
            "schema": {
                "type": "object",
                "properties": {
                    "msg": {"type": "string"},
                    "id": {"type": "integer"}
                }
            }
        },
        "401": {
            "description": "Unauthorized"
        }
    }
})
def create_product():
    data = request.get_json()
    username = get_jwt_identity()
    user = User.query.filter_by(username=username).first()
    
    product = Products(
        name=data['name'],
        description=data.get('description', ''),
        price=data['price'],
        product_image_url=data.get('product_image_url', ''),
        created_by=user.id
    )
    
    db.session.add(product)
    db.session.commit()
    
    return jsonify({"msg": "Product created", "id": product.id}), 201

@app.route("/api/products/<int:product_id>", methods=["PUT"])
@jwt_required()
@swag_from({
    "parameters": [
        {
            "name": "Authorization",
            "in": "header",
            "type": "string",
            "required": True,
            "description": "Bearer {token}"
        },
        {
            "name": "product_id",
            "in": "path",
            "type": "integer",
            "required": True
        },
        {
            "name": "body",
            "in": "body",
            "required": True,
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "price": {"type": "number"},
                    "product_image_url": {"type": "string"}
                }
            }
        }
    ],
    "responses": {
        "200": {
            "description": "Product updated"
        },
        "403": {
            "description": "Forbidden - Not authorized to update this product"
        },
        "404": {
            "description": "Product not found"
        }
    }
})
def update_product(product_id):
    data = request.get_json()
    username = get_jwt_identity()
    user = User.query.filter_by(username=username).first()
    product = Products.query.get_or_404(product_id)
    
    # Only allow the creator or admin to update
    if product.created_by != user.id and user.role != ROLES['admin']:
        return jsonify({"msg": "Not authorized to update this product"}), 403
    
    product.name = data.get('name', product.name)
    product.description = data.get('description', product.description)
    product.price = data.get('price', product.price)
    product.product_image_url = data.get('product_image_url', product.product_image_url)
    
    db.session.commit()
    return jsonify({"msg": "Product updated"})

@app.route("/api/products/<int:product_id>", methods=["DELETE"])
@jwt_required()
@swag_from({
    "parameters": [
        {
            "name": "Authorization",
            "in": "header",
            "type": "string",
            "required": True,
            "description": "Bearer {token}"
        },
        {
            "name": "product_id",
            "in": "path",
            "type": "integer",
            "required": True
        }
    ],
    "responses": {
        "200": {
            "description": "Product deleted"
        },
        "403": {
            "description": "Forbidden - Not authorized to delete this product"
        },
        "404": {
            "description": "Product not found"
        }
    }
})
def delete_product(product_id):
    username = get_jwt_identity()
    user = User.query.filter_by(username=username).first()
    product = Products.query.get_or_404(product_id)
    
    # Only allow the creator or admin to delete
    if product.created_by != user.id and user.role != ROLES['admin']:
        return jsonify({"msg": "Not authorized to delete this product"}), 403
    
    db.session.delete(product)
    db.session.commit()
    return jsonify({"msg": "Product deleted"})

# Static file serving for development
@app.route('/static/<path:path>')
def serve_static(path):
    """
    Serve static files during development.
    In production, static files should be served from S3 directly.
    """
    return send_from_directory('static', path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)





