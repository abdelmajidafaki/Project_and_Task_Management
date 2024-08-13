import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'test') 
    SESSION_TYPE = 'filesystem'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'mysql://root:@localhost/python_project')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
