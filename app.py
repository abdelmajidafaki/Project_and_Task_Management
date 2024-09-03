from flask import Flask
from config import Config  
from extensions import db, bcrypt, login_manager
from adminroutes import admin_routes
from authroutes import auth_routes  
from employeeroutes import employee_routes  
from modals import users
import base64
webapp = Flask(__name__)
webapp.config.from_object(Config)
UPLOAD_FOLDER = 'static/uploads/'
webapp.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
db.init_app(webapp)
bcrypt.init_app(webapp)
login_manager.init_app(webapp)

@login_manager.user_loader
def load_user(user_id):
    return users.query.get(int(user_id))
def b64encode(value):
    return base64.b64encode(value).decode('utf-8')
webapp.register_blueprint(auth_routes)
webapp.register_blueprint(employee_routes, url_prefix='/employee')
webapp.register_blueprint(admin_routes, url_prefix='/admin')

webapp.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 
webapp.jinja_env.filters['b64encode'] = b64encode

if __name__ == '__main__':
    with webapp.app_context():
        db.create_all()
    webapp.run(debug=True)
