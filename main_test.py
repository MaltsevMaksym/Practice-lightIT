import pytest
from flask import json
from main import app, db, Product, Order, Invoice, User
from flask_principal import Identity, identity_changed, RoleNeed, Permission
from datetime import datetime

# Настройка тестового пользователя
users = {
    'accountant': {'password': 'password3', 'roles': ['accountant']}
}
accountant_permission = Permission(RoleNeed('accountant'))

# Фикстура для создания тестового клиента
@pytest.fixture(scope='module')
def test_client():
    flask_app = app
    flask_app.config['TESTING'] = True
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
    flask_app.config['WTF_CSRF_ENABLED'] = False

    with flask_app.app_context():
        db.create_all()


    testing_client = flask_app.test_client()

    yield testing_client

    with flask_app.app_context():
        db.drop_all()

def login(test_client):
    test_client.post('/login', data=dict(
        username='accountant',
        password='password3'
    ), follow_redirects=True)

def test_create_order(test_client):
    with app.app_context():
        login(test_client)
        # Добавляем тестовый продукт
        product = Product(name='Product 1', price=100.0, date=datetime.utcnow(), status='Available')
        db.session.add(product)
        db.session.commit()

        # Создаем заказ
        response = test_client.post('/orders', json={
            'product_id': product.id,
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['status'] == 'Just Created'

def test_accept_order(test_client):
    with app.app_context():
        login(test_client)
        # Добавляем тестовый продукт и заказ
        product = Product(name='Product 2', price=150.0, date=datetime.utcnow(), status='Available')
        db.session.add(product)
        db.session.commit()
        order = Order(product_id=product.id, price=150.0, date=datetime.utcnow(), status='Just Created',discount = 'Without discount')
        db.session.add(order)
        db.session.commit()

        # Принимаем заказ
        response = test_client.post('/orders/accept', json={
            'order_id': order.id
        })
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'Accepted'

def test_generate_invoice(test_client):
    with app.app_context():
        login(test_client)
        # Добавляем тестовый продукт и заказ
        product = Product(name='Product 3', price=200.0, date=datetime.utcnow(), status='Available')
        db.session.add(product)
        db.session.commit()
        order = Order(product_id=product.id, price=200.0, date=datetime.utcnow(), status='Accepted', discount = 'Without discount')
        db.session.add(order)
        db.session.commit()

        # Генерируем счет
        response = test_client.post('/orders/invoice', json={
            'order_id': order.id
        })
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['message'] == 'Invoice created'
        assert data['status'] == 'paid'

def test_view_invoices(test_client):
    with app.app_context():
        login(test_client)
        # Просматриваем все счета
        response = test_client.get('/invoices')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

def test_delete_all_data(test_client):
    with app.app_context():
        login(test_client)
        db.session.query(Order).delete()
        db.session.query(Product).delete()
        db.session.query(Invoice).delete()
        # Добавляем тестовые данные в базу данных
        product = Product(name='Product to delete', price=50.0, date=datetime.utcnow(), status='Available')
        db.session.add(product)
        db.session.commit()
        order = Order(product_id=product.id, price=50.0, date=datetime.utcnow(), status='Accepted', discount = 'Without discount')
        db.session.add(order)
        db.session.commit()
        invoice = Invoice(order_id=order.id, product_name=product.name, product_price=order.price, order_date=order.date, invoice_date=datetime.utcnow())
        db.session.add(invoice)
        db.session.commit()

        # Очищаем базу данных
        response = test_client.delete('/delete')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['message'] == 'All data deleted successfully'
        assert data['orders_deleted'] == 1
        assert data['invoices_deleted'] == 1
        assert data['products_deleted'] == 1
