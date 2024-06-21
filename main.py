from flask import Flask, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_principal import Principal, Identity, AnonymousIdentity, identity_changed, RoleNeed, UserNeed, identity_loaded, Permission
from datetime import datetime
from faker import Faker  # Use for creating some products for testing ( in create_tables() )
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///your_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
principals = Principal(app)
seller_permission = Permission(RoleNeed('seller'))
cashier_permission = Permission(RoleNeed('cashier'))
accountant_permission = Permission(RoleNeed('accountant'))


users = {
    'seller': {'password': 'password1', 'roles': ['seller']},
    'cashier': {'password': 'password2', 'roles': ['cashier']},
    'accountant': {'password': 'password3', 'roles': ['accountant']}
}


class User(UserMixin):
    def __init__(self, username, roles):
        self.id = username
        self.roles = roles


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), nullable=False)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False)
    discount = db.Column(db.String(50), nullable=False)
    product = db.relationship('Product')


class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, nullable=False)
    product_name = db.Column(db.String(80), nullable=False)
    product_price = db.Column(db.Float, nullable=False)
    order_date = db.Column(db.DateTime, nullable=False)
    invoice_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


@app.before_request
def create_tables():
    db.create_all()

    # Creating some products with Faker
    '''if not Product.query.first():
        faker = Faker()
        for _ in range(50):
            product_name = faker.word().capitalize()
            product_price = round(random.uniform(50.0, 500.0), 2)
            product_date = faker.date_time_between(start_date='-1y', end_date='now')
            product = Product(name=product_name, price=product_price, date=product_date, status='Available')
            db.session.add(product)
        db.session.commit()'''


@app.route('/')
def index():
    try:
        return 'Logged in as: ' + current_user.id
    except: return jsonify({"Logout": "Success"}), 200


@app.route('/products', methods=['GET'])
def get_products():
    products = Product.query.all()
    try:
        if current_user.id == "seller" or current_user.id == "cashier" or current_user.id == "accountant":
            products = Product.query.all()
            return jsonify([{"id": p.id, "name": p.name, "price": p.price, "date": p.date.isoformat(), "status": p.status} for p in products])
    except: return jsonify([{"id": p.id, "name": p.name, "price": p.price, "date": p.date.isoformat()} for p in products if p.status != 'Ordered'])


@app.route('/products', methods=['POST'])
@login_required
def add_products():
    data = request.get_json()
    if not isinstance(data, list):
        data = request.get_json()
        name = data.get('name')
        price = data.get('price')
        date = datetime.fromisoformat(data.get('date'))
        status = data.get('status')

        new_product = Product(name=name, price=price, date=date, status=status)
        db.session.add(new_product)
        db.session.commit()

        return jsonify({"id": new_product.id, "name": new_product.name, "price": new_product.price,
                        "date": new_product.date.isoformat(), "status": new_product.status}), 201

    added_products = []
    for item in data:
        name = item.get('name')
        price = item.get('price')
        date_str = item.get('date')
        status = item.get('status')
        try:
            date = datetime.fromisoformat(date_str)
        except ValueError:
            return jsonify({"error": f"Invalid date format for product {name}"}), 400

        product = Product(name=name, price=price, date=date, status=status)
        db.session.add(product)
        added_products.append(product)

    db.session.commit()

    result = [{"id": product.id, "name": product.name, "price": product.price, "date": product.date.isoformat(), "status": product.status} for product in added_products]
    return jsonify(result), 201


@app.route('/products/<int:product_id>', methods=['PUT'])
@login_required
def update_product(product_id):

    data = request.get_json()
    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    product.name = data.get('name', product.name)
    product.price = data.get('price', product.price)
    product.date = datetime.fromisoformat(data.get('date', product.date.isoformat()))

    db.session.commit()

    return jsonify({"id": product.id, "name": product.name, "price": product.price, "date": product.date.isoformat()})


@app.route('/products/<int:product_id>', methods=['PATCH'])
@login_required
def patch_product(product_id):

    data = request.get_json()
    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    if 'name' in data:
        product.name = data['name']
    if 'price' in data:
        product.price = data['price']
    if 'date' in data:
        product.date = datetime.fromisoformat(data['date'])

    db.session.commit()

    return jsonify({"id": product.id, "name": product.name, "price": product.price, "date": product.date.isoformat()})


@app.route('/products/<int:product_id>', methods=['DELETE'])
@login_required
def delete_product(product_id):

    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    db.session.delete(product)
    db.session.commit()

    return jsonify({"Success": "Product deleted"}), 200


# Order creating
@app.route('/orders', methods=['POST'])
def create_order():

    data = request.get_json()
    product_id = data['product_id']
    status = "Just Created"
    product = Product.query.get(product_id)
    discount = 'Without discount'

    if not product:
        return jsonify({"error": "Product not found"}), 404
    price = product.price
    order_time = datetime.utcnow()

    if (order_time - product.date).days >= 30:
        price *= 0.8
        discount = 'With discount'
    order = Order(product_id=product_id, price=price, date=order_time, status=status, discount=discount)
    db.session.add(order)
    db.session.commit()

    product.status = "Ordered"
    db.session.commit()
    return jsonify({"order_id": order.id, "product_id": order.product_id, "price": order.price,
                    "date": order.date.isoformat(), "status": order.status, "discount": order.discount}), 201


@app.route('/orders', methods=['GET'])
def get_orders():
    orders = Order.query.all()
    return jsonify([{"order_id": o.id, "product_id": o.product_id, "price": o.price, "date": o.date.isoformat(),
                     "status": o.status, "discount": o.discount} for o in orders])


@app.route('/orders/<int:order_id>', methods=['PATCH'])
def edit_order(order_id):
    data = request.get_json()
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    if 'status' in data:
        order.status = data['status']
    db.session.commit()
    return jsonify({"order_id": order.id, "product_id": order.product_id, "price": order.price,
                    "date": order.date.isoformat(), "status": order.status})


# Looking for products by date (only for accountant)
@app.route('/orders/find', methods=['GET'])
@accountant_permission.require(http_exception=403)
def find_orders():
    from_date_str = request.args.get('from_date')
    to_date_str = request.args.get('to_date')

    if not from_date_str or not to_date_str:
        return jsonify({"error": "from_date and to_date parameters are required"}), 400

    try:
        from_date = datetime.fromisoformat(from_date_str)
        to_date = datetime.fromisoformat(to_date_str)
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    orders = Order.query.filter(Order.date > from_date, Order.date < to_date).all()
    return jsonify([{"order_id": o.id, "product_id": o.product_id, "price": o.price, "date": o.date.isoformat(),
                     "status": o.status} for o in orders])


@app.route('/orders/accept', methods=['POST'])
@login_required
@accountant_permission.require(http_exception=403)
def accept_order():
    data = request.get_json()
    order_id = data.get('order_id')
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404

    order.status = "Accepted"
    db.session.commit()
    return jsonify({"message": "Order accepted", "order_id": order.id, "status": order.status})


@app.route('/orders/invoice', methods=['POST'])
@login_required
@accountant_permission.require(http_exception=403)
def create_invoice1():
    data = request.get_json()
    order_id = data.get('order_id')
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    if order.status != "Accepted":
        return jsonify({"error": "Cannot generate invoice for this order"}), 400

    product = Product.query.get(order.product_id)
    invoice = Invoice(
        order_id=order_id,
        product_name=product.name,
        product_price=order.price,
        order_date=order.date,
        invoice_date=datetime.utcnow()
    )
    order.status = "paid"
    db.session.add(invoice)
    db.session.commit()
    return jsonify({"message": "Invoice created", "invoice_id": invoice.id, "order_id": invoice.order_id, "status": order.status}), 201


@app.route('/invoices', methods=['GET'])
@login_required
@accountant_permission.require(http_exception=403)
def get_invoices():
    invoices = Invoice.query.all()
    return jsonify([{
        "id": invoice.id,
        "order_id": invoice.order_id,
        "product_name": invoice.product_name,
        "product_price": invoice.product_price,
        "order_date": invoice.order_date.isoformat(),
        "invoice_date": invoice.invoice_date.isoformat()
    } for invoice in invoices])


@app.route('/delete', methods=['DELETE'])
@login_required
@accountant_permission.require(http_exception=403)
def delete_all_data():
    try:
        num_orders_deleted = db.session.query(Order).delete()
        num_invoices_deleted = db.session.query(Invoice).delete()
        num_products_deleted = db.session.query(Product).delete()
        db.session.commit()

        return jsonify({
            "message": "All data deleted successfully",
            "orders_deleted": num_orders_deleted,
            "invoices_deleted": num_invoices_deleted,
            "products_deleted": num_products_deleted
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_info = users.get(username)
        if user_info and user_info['password'] == password:
            user = User(username, user_info['roles'])
            login_user(user)
            identity_changed.send(app, identity=Identity(username))
            return redirect(url_for('index'))
    return '''
        <form method="post">
            <p><input type=text name=username>
            <p><input type=password name=password>
            <p><input type=submit value=Login>
        </form>
    '''


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    for key in ('identity.name', 'identity.auth_type'):
        session.pop(key, None)
    identity_changed.send(app, identity=AnonymousIdentity())
    return redirect(url_for('index'))


@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    identity.user = current_user
    if hasattr(current_user, 'roles'):
        for role in current_user.roles:
            identity.provides.add(RoleNeed(role))


@login_manager.user_loader
def load_user(user_id):
    user_info = users.get(user_id)
    if user_info:
        return User(user_id, user_info['roles'])
    return None


if __name__ == '__main__':
    app.run(debug=True)
