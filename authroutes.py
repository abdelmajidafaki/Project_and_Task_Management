from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, bcrypt
from modals import users

auth_routes = Blueprint('auth_routes', __name__)

@auth_routes.route("/", methods=['GET', 'POST'])
def indexpage():
    return redirect(url_for('auth_routes.loginpage'))

@auth_routes.route("/register", methods=['GET', 'POST'])
def registerpage():
    if request.method == 'POST':
        fullname = request.form['fullname']
        email = request.form['email']
        password = request.form['password']
        cpassword = request.form['cpassword']
        if fullname and email:
            if password == cpassword:
                hashed_password = bcrypt.generate_password_hash(cpassword).decode('utf-8')
                new_user = users(fulname=fullname, email=email, Pasword=hashed_password)
                db.session.add(new_user)
                db.session.commit()
                flash("Registration successful!", 'success')
                return redirect(url_for('auth_routes.loginpage'))
            else:
                flash("Passwords do not match. Please try again.", 'danger')
        else:
            flash("You must fill all inputs.", 'danger')
    return render_template("registerpage.html")

@auth_routes.route("/logout", methods=['GET'])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", 'info')
    return redirect(url_for('auth_routes.loginpage'))

@auth_routes.route("/login", methods=['GET', 'POST'])
def loginpage():
    if current_user.is_authenticated:
        if current_user.usertype == "Admin":
            return redirect(url_for('admin_routes.usersdashboard'))  
        elif current_user.usertype == "employee":
            return redirect(url_for('employee_routes.Assignedtasks'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = users.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.Pasword, password):
            if user.status == "active":
                login_user(user)
                flash("Login successful!", 'success')
                if user.usertype == "Admin":
                    return redirect(url_for('admin_routes.usersdashboard'))
                elif user.usertype == "employee":
                    return redirect(url_for('employee_routes.Assignedtasks'))
            elif user.status == "inactive":
                flash("Your account is inactive. Please contact administration to activate your account.", 'danger')
            else:
                flash("Your account should be activated.", 'danger')
        else:
            flash("Invalid email or password. Please try again.", 'danger')

    if current_user.is_authenticated and request.method == 'GET':
        return redirect(url_for('admin_routes.homepage'))
    return render_template("loginpage.html")
