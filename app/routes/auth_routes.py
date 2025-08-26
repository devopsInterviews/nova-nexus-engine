from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash
from app.database import get_db_session, User
import jwt
import datetime
import os
from functools import wraps

auth_bp = Blueprint('auth_bp', __name__)

SECRET_KEY = os.getenv("SECRET_KEY", "your_default_secret_key")

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            session = get_db_session()
            current_user = session.query(User).filter_by(id=data['user_id']).first()
            session.close()
        except:
            return jsonify({'message': 'Token is invalid!'}), 401

        return f(current_user, *args, **kwargs)
    return decorated

@auth_bp.route('/login', methods=['POST'])
def login():
    auth = request.json
    if not auth or not auth.get('username') or not auth.get('password'):
        return jsonify({'message': 'Could not verify'}), 401

    session = get_db_session()
    user = session.query(User).filter_by(username=auth['username']).first()

    if not user:
        session.close()
        return jsonify({'message': 'User not found'}), 401

    if user.check_password(auth['password']):
        user.last_login = datetime.datetime.utcnow()
        user.login_count += 1
        session.commit()
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, SECRET_KEY, "HS256")
        session.close()
        return jsonify({'token': token})

    session.close()
    return jsonify({'message': 'Could not verify'}), 401

@auth_bp.route('/users', methods=['GET'])
@token_required
def get_all_users(current_user):
    if current_user.username != 'admin':
        return jsonify({'message': 'Cannot perform that function!'})
        
    session = get_db_session()
    users = session.query(User).all()
    session.close()
    
    output = []
    for user in users:
        user_data = {}
        user_data['id'] = user.id
        user_data['username'] = user.username
        user_data['creation_date'] = user.creation_date
        user_data['last_login'] = user.last_login
        user_data['login_count'] = user.login_count
        output.append(user_data)

    return jsonify({'users': output})

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    user_data = {
        'id': current_user.id,
        'username': current_user.username,
        'creation_date': current_user.creation_date,
        'last_login': current_user.last_login,
        'login_count': current_user.login_count
    }
    return jsonify(user_data)
