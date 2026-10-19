from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_asset_stats(mongo):
    pipeline = [
        {
            '$group': {
                '_id': '$asset_type',
                'count': {'$sum': 1},
                'available': {
                    '$sum': {'$cond': [{'$eq': ['$status', 'Available']}, 1, 0]}
                },
                'assigned': {
                    '$sum': {'$cond': [{'$eq': ['$status', 'Assigned']}, 1, 0]}
                }
            }
        }
    ]
    return list(mongo.db.assets.aggregate(pipeline))

def get_department_stats(mongo):
    pipeline = [
        {
            '$group': {
                '_id': '$department',
                'count': {'$sum': 1}
            }
        }
    ]
    return list(mongo.db.employees.aggregate(pipeline))