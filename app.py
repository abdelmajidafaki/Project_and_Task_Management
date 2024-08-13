from flask import Flask
from config import Config  
from extensions import db, bcrypt, login_manager
from adminroutes import admin_routes
from authroutes import auth_routes  
from employeeroutes import employee_routes  
from modals import users

webapp = Flask(__name__)
webapp.config.from_object(Config)

db.init_app(webapp)
bcrypt.init_app(webapp)
login_manager.init_app(webapp)

@login_manager.user_loader
def load_user(user_id):
    return users.query.get(int(user_id))

webapp.register_blueprint(auth_routes)
webapp.register_blueprint(employee_routes, url_prefix='/employee')
webapp.register_blueprint(admin_routes, url_prefix='/admin')

if __name__ == '__main__':
    with webapp.app_context():
        db.create_all()
    webapp.run(debug=True)
