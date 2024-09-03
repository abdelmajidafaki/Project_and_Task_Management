from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, session
from flask_login import login_required, current_user
from extensions import db, bcrypt, ALLOWED_EXTENSIONS
from modals import users, Event, Task, TaskAssignment, Task_Progression, EventEmployee, PersonalTask, PersonalTaskProgression, Teams, TeamsMember, Project, ProjectTeam, EventTeam
from datetime import datetime, date, timezone
import secrets
from functools import wraps
from utils import get_task_status, calculate_days_to_close, sort_tasks

admin_routes = Blueprint('admin_routes', __name__)

def admin_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.usertype != "Admin":
            flash("You do not have permission to access this page.", 'danger')
            return redirect(url_for('auth_routes.loginpage'))
        return func(*args, **kwargs)
    return decorated_function

def get_user_or_redirect(user_id):
    user = users.query.get(user_id)
    if not user or user.usertype != "Admin":
        flash("You are not logged in or do not have permission to access this page.", 'danger')
        return redirect(url_for('auth_routes.loginpage'))
    return user

def get_project_status(project):
    today = date.today()
    if project.start_date > today:
        return "Upcoming"
    elif project.start_date <= today and (project.end_date is None or project.end_date >= today) and project.statut == 'in progress':
        return "Open"
    else:
        return "Closed"

#---------------------------------------------------------------users-------------------------------------------------------------------

@admin_routes.route("/usersdashboard", methods=['GET', 'POST'])
@login_required
@admin_required
def usersdashboard():
    user = get_user_or_redirect(current_user.userid)
    all_users = users.query.all()
    return render_template("admin/homepage.html", fullname=user.fulname, all_users=all_users)

@admin_routes.route('/update_status/<int:userid>', methods=['POST'])
@login_required
@admin_required
def update_status(userid):
    user = users.query.get(userid)
    if not user:
        flash("User not found.", 'danger')
        return redirect(url_for('admin_routes.usersdashboard'))

    action = request.form.get('action')
    usertype = request.form.get('usertype')

    if action == 'activate':
        user.status = 'active'
        flash("User activated successfully.", 'success')
    elif action == 'deactivate':
        user.status = 'inactive'
        flash("User deactivated successfully.", 'success')
    elif usertype in ['Admin', 'employee']:
        user.usertype = usertype
        flash(f"User type updated successfully to {usertype}.", 'success')
    else:
        flash("Invalid user type or action selected.", 'danger')

    db.session.commit()
    return redirect(url_for('admin_routes.usersdashboard'))


@admin_routes.route('/admin/personal-tasks/<string:token>')
@admin_required
@login_required
def employepertask(token):

    task = PersonalTask.query.filter_by(token=token).first() 
    
    if task is None:
        flash('Task not found.', 'danger')
        return redirect(url_for('index')) 


    task_progressions = PersonalTaskProgression.query.filter_by(Ptask_id=task.PTDID).all()
    
    return render_template('admin/employeeperstask.html', task=task, task_progressions=task_progressions)
@admin_routes.route("/usersdashboard/userdetails/<Utoken>", methods=['GET', 'POST'])
@login_required
@admin_required
def userdetails(Utoken):
    user = users.query.filter_by(Utoken=Utoken).first_or_404()
    personal_tasks = PersonalTask.query.filter_by(employee_id=user.userid).all()
    assigned_tasks = Task.query.join(TaskAssignment).filter(TaskAssignment.employee_id == user.userid).all()
    now = datetime.now(tz=timezone.utc).date()
    tasks = []
    teams = []
    supervised_teams = []

    if user.usertype == 'Admin':
        created_tasks = Task.query.filter(Task.admin_id == user.userid).all()
        for task in created_tasks:
            status = get_task_status(task)
            daystoclose = calculate_days_to_close(task, now)
            admin_name = user.fulname if user.fulname else 'No Admin'
            tasks.append((task, admin_name, status, daystoclose))
        projects = Project.query.filter(Project.created_by == user.userid).all()
    else:
        for task in assigned_tasks:
            status = get_task_status(task)
            daystoclose = calculate_days_to_close(task, now)
            admin_name = task.admin.fulname if task.admin and task.admin.fulname else 'No Admin'
            tasks.append((task, admin_name, status, daystoclose))
        teams = Teams.query.join(TeamsMember).filter(TeamsMember.userid == user.userid).all()
        team_ids = [team.team_id for team in teams]
        projects = Project.query.join(ProjectTeam).filter(ProjectTeam.team_id.in_(team_ids)).distinct().all()
        supervised_teams = Teams.query.filter_by(supervisor_id=user.userid).all()

    for project in projects:
        project.status = get_project_status(project)

    return render_template(
        "admin/userdetails.html",
        user=user,
        personal_tasks=personal_tasks,
        tasks=tasks,
        teams=teams,
        supervised_teams=supervised_teams,
        projects=projects
    )

@admin_routes.route('/delete_user/<int:userid>', methods=['POST'])
@login_required
@admin_required
def delete_user(userid):
    user = users.query.get(userid)
    if user:
        try:
            Project.query.filter_by(created_by=userid).update({'created_by': None})
            Task_Progression.query.filter_by(employee_id=userid).update({'employee_id': None})
            TaskAssignment.query.filter_by(employee_id=userid).update({'employee_id': None})
            Event.query.filter_by(creator_id=userid).update({'creator_id': None})
            
            # Delete records from dependent tables
            PersonalTaskProgression.query.filter_by(employee_id=userid).delete()
            PersonalTask.query.filter_by(employee_id=userid).delete()
            TeamsMember.query.filter_by(userid=userid).delete()
            EventEmployee.query.filter_by(employee_id=userid).delete()
            db.session.delete(user)
            db.session.commit()
            flash('User deleted successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting user: {str(e)}', 'danger')
    else:
        flash('User not found.', 'danger')
    return redirect(url_for('admin_routes.usersdashboard'))

#---------------------------------------------------------------teams-------------------------------------------------------------------

@admin_routes.route('/teams', methods=['GET'])
@login_required
@admin_required
def teams():
    all_teams = Teams.query.all()
    all_users = users.query.all()
    all_projects = Project.query.all()
    team_data = {}
    for team in all_teams:
        team_members = TeamsMember.query.filter_by(team_id=team.team_id).all()
        member_ids = [member.userid for member in team_members]
        members = users.query.filter(users.userid.in_(member_ids)).all()
        supervisor = users.query.get(team.supervisor_id) if team.supervisor_id else None
        associated_projects = [
            project for project in all_projects
            if ProjectTeam.query.filter_by(team_id=team.team_id, project_id=project.project_id).first()
        ]
        team_data[team] = {
            'members': members,
            'supervisor': supervisor,
            'projects': associated_projects
        }
    return render_template('admin/teams/teams.html', team_data=team_data, users=all_users)

@admin_routes.route('/teams/Create_new_team', methods=['POST', 'GET'])
@login_required
@admin_required
def add_team():
    if request.method == 'POST':
        team_name = request.form['team_name']
        team_members = request.form.getlist('team_members')
        supervisor_id = request.form.get('supervisor_id')
        new_team = Teams(team_name=team_name, supervisor_id=supervisor_id, TETOKEN=secrets.token_urlsafe())
        db.session.add(new_team)
        db.session.commit()
        for member_id in team_members:
            team_member = TeamsMember(team_id=new_team.team_id, userid=member_id)
            db.session.add(team_member)
        db.session.commit()
        flash('Team added successfully!', 'success')
        return redirect(url_for('admin_routes.teams'))
    employees = users.query.filter_by(usertype='employee').all()
    return render_template('admin/teams/addteam.html', employees=employees)

@admin_routes.route('/teams/update/<string:TETOKEN>', methods=['GET', 'POST'])
@login_required
@admin_required
def update_team(TETOKEN):
    team = Teams.query.filter_by(TETOKEN=TETOKEN).first_or_404()
    if request.method == 'POST':
        team_name = request.form['team_name']
        team_members = request.form.getlist('team_members')
        supervisor_id = request.form.get('supervisor_id')
        team.team_name = team_name
        team.supervisor_id = supervisor_id
        TeamsMember.query.filter_by(team_id=team.team_id).delete()
        for member_id in team_members:
            team_member = TeamsMember(team_id=team.team_id, userid=member_id)
            db.session.add(team_member)
        db.session.commit()
        flash('Team updated successfully!', 'success')
        return redirect(url_for('admin_routes.teams'))
    team_member_ids = [tm.userid for tm in TeamsMember.query.filter_by(team_id=team.team_id).all()]
    employees = users.query.filter_by(usertype='employee').all()
    return render_template('admin/teams/updateteam.html', team=team, employees=employees, team_member_ids=team_member_ids)

@admin_routes.route('/teams/delete_team/<string:TETOKEN>', methods=['GET', 'POST'])
@login_required
@admin_required
def delete_team(TETOKEN):
    team = Teams.query.filter_by(TETOKEN=TETOKEN).first()
    if team:
        EventTeam.query.filter_by(team_id=team.team_id).delete()
        ProjectTeam.query.filter_by(team_id=team.team_id).delete()
        TeamsMember.query.filter_by(team_id=team.team_id).delete()
        db.session.delete(team)
        db.session.commit()
        flash('Team deleted successfully!', 'success')
    else:
        flash('Team not found', 'danger')
    return redirect(request.referrer)

@admin_routes.route('/teams/<int:team_id>/add_member_to_team', methods=['POST'])
@login_required
@admin_required
def add_member_to_team(team_id):
    team = Teams.query.get_or_404(team_id)
    member_ids = request.form.getlist('member_id')
    position = request.form.get('position')
    for member_id in member_ids:
        user = users.query.get(member_id)
        if user:
            if position == 'member':
                if not TeamsMember.query.filter_by(team_id=team_id, userid=member_id).first():
                    new_member = TeamsMember(team_id=team_id, userid=member_id)
                    db.session.add(new_member)
                else:
                    flash(f'User {user.fulname} is already a member of the team.', 'warning')
            if position == 'supervisor':
                team.supervisor_id = user.userid
    try:
        db.session.commit()
        flash('Members added successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while adding members.', 'danger')
    return redirect(url_for('admin_routes.teams'))

@admin_routes.route('/teams/<int:team_id>/remove_member/<int:member_id>', methods=['POST'])
@login_required
@admin_required
def remove_member_from_team(team_id, member_id):
    team_member = TeamsMember.query.filter_by(team_id=team_id, userid=member_id).first()
    if team_member:
        try:
            db.session.delete(team_member)
            db.session.commit()
            flash('Member removed and tasks unassigned successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while removing the member and unassigning tasks.', 'danger')
    else:
        flash('Member not found in this team.', 'danger')
    return redirect(request.referrer)

#---------------------------------------------------------------tasks-------------------------------------------------------------------

@admin_routes.route("/tasks/taskdetail/<token>", methods=['GET', 'POST'])
@login_required
@admin_required
def taskdetail(token):
    task = Task.query.filter_by(token=token).first()
    if not task:
        flash("Task not found.", 'danger')
        return redirect(url_for('admin_routes.tasks'))
    status = get_task_status(task)
    task_assignment = TaskAssignment.query.filter_by(task_id=task.task_id).first()
    task_progressions = Task_Progression.query.filter_by(task_id=task.task_id).all()
    project = Project.query.get(task.project_id) if task.project_id else None
    return render_template("admin/tasks/taskdetail.html", task=task, task_assignment=task_assignment, task_progressions=task_progressions, status=status, project=project)

@admin_routes.route("/tasks", methods=['GET', 'POST'])
@login_required
@admin_required
def tasks():
    today = date.today()
    projects = db.session.query(Project.project_name).distinct().all()
    project_names = [p[0] for p in projects]
    tasksq = Task.query.all()
    tasks = []

    for task in tasksq:
        admin_name = task.admin.fulname if task.admin else 'No Admin'
        project_name = task.project.project_name if task.project else 'No Project'
        employee_names = [assignment.employee.fulname for assignment in task.assignments if assignment.employee]

        status = get_task_status(task)
        daystoclose = calculate_days_to_close(task, today)
        task_tuple = (task, admin_name, ', '.join(employee_names), status, daystoclose, project_name)
        tasks.append(task_tuple)

    tasks = sort_tasks(tasks)

    return render_template("admin/tasks/tasks.html", tasks=tasks, projects=project_names)

@admin_routes.route('/update_task_statut', methods=['POST'])
@login_required
@admin_required
def update_task_statut():
    task_id = request.form.get('task_id')
    task = Task.query.get(task_id)
    if not task:
        flash('Task not found', 'danger')
        return redirect(request.referrer)

    status = get_task_status(task)

    if 'opentask' in request.form:
        if status in ['Upcoming', 'Closed']:
            task.start_date = datetime.today().date()
        task.status = 'In Progress'
    elif 'closetask' in request.form:
        task.status = 'Closed by Admin'

    db.session.commit()
    flash(f'Task is now {task.status.lower()}', 'success')

    return redirect(request.referrer)

@admin_routes.route("/tasks/Create_new_task", methods=['GET', 'POST'])
@login_required
@admin_required
def addnewtask():
    project_token = request.args.get('project_token')
    project_id = None

    if request.method == 'POST':
        task_name = request.form['task_name']
        start_date_str = request.form['start_date']
        description = request.form.get('description')

        if project_token:
            project = Project.query.filter_by(token=project_token).first()
            if project:
                project_id = project.project_id
                project_start_date = project.start_date
            else:
                flash('Invalid project token.', 'danger')
                return redirect(url_for('admin_routes.addnewtask'))
        else:
            project_token = request.form.get('project_token')
            if project_token:
                project = Project.query.filter_by(token=project_token).first()
                if not project:
                    flash('Invalid project selected.', 'danger')
                    return redirect(url_for('admin_routes.addnewtask'))
                project_id = project.project_id
                project_start_date = project.start_date
            else:
                project_start_date = None

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid start date format.', 'danger')
            return render_template(
                "admin/tasks/addtasks.html",
                employees=[{'userid': e.userid, 'fulname': e.fulname} for e in users.query.filter_by(usertype='employee').all()],
                projects=Project.query.all(),
                selected_project_token=project_token
            )

        if start_date < date.today():
            flash('Start date cannot be in the past.', 'danger')
            return render_template(
                "admin/tasks/addtasks.html",
                employees=[{'userid': e.userid, 'fulname': e.fulname} for e in users.query.filter_by(usertype='employee').all()],
                projects=Project.query.all(),
                selected_project_token=project_token
            )

        if project_start_date and start_date < project_start_date:
            flash(f'Task start date cannot be earlier than the project start date ({project_start_date.strftime("%Y-%m-%d")}).', 'danger')
            return redirect(request.referrer)

        close_date = request.form.get('close_date')
        if close_date:
            close_date = datetime.strptime(close_date, '%Y-%m-%d').date()
            if close_date < start_date:
                flash('Close date cannot be earlier than the start date.', 'danger')
                return render_template(
                    "admin/tasks/addtasks.html",
                    employees=[{'userid': e.userid, 'fulname': e.fulname} for e in users.query.filter_by(usertype='employee').all()],
                    projects=Project.query.all(),
                    selected_project_token=project_token
                )
        else:
            close_date = None

        if not project_id:
            project_id = None
        selected_employee_ids = request.form.getlist('employees[]')
        new_task = Task(
            task_name=task_name,
            start_date=start_date,
            close_date=close_date,
            admin_id=current_user.userid,
            description=description,
            token=secrets.token_urlsafe(),
            project_id=project_id
        )
        db.session.add(new_task)
        db.session.commit()

        for employee_id in selected_employee_ids:
            assignment = TaskAssignment(task_id=new_task.task_id, employee_id=employee_id)
            db.session.add(assignment)

        db.session.commit()
        flash('New task added successfully!', 'success')
        return redirect(url_for('admin_routes.tasks'))

    employees = [{'userid': e.userid, 'fulname': e.fulname} for e in users.query.filter_by(usertype='employee').all()]
    projects = Project.query.all()

    project_teams = {}
    for project in projects:
        teams = Teams.query.join(ProjectTeam).filter(ProjectTeam.project_id == project.project_id).all()
        team_members = []
        for team in teams:
            team_members.extend([{'userid': member.userid, 'fulname': member.fulname} for member in team.members])
        project_teams[project.token] = team_members or []

    return render_template(
        "admin/tasks/addtasks.html",
        employees=employees,
        projects=projects,
        project_teams=project_teams,
        selected_project_token=project_token
    )

@admin_routes.route("/tasks/delete/<int:task_id>", methods=['POST'])
@login_required
@admin_required
def delete_task(task_id):
    task = Task.query.get(task_id)
    if task:
        db.session.query(Task_Progression).filter(Task_Progression.task_id == task_id).delete(synchronize_session='fetch')
        db.session.query(TaskAssignment).filter(TaskAssignment.task_id == task_id).delete(synchronize_session='fetch')
        db.session.query(Task).filter(Task.task_id == task_id).delete(synchronize_session='fetch')
        db.session.commit()
        flash('Task deleted successfully!', 'success')
    else:
        flash('Task not found.', 'danger')
    return redirect(request.referrer)

@admin_routes.route("/tasks/update/<string:token>", methods=['GET', 'POST'])
@login_required
@admin_required
def update_task(token):
    task = Task.query.filter_by(token=token).first()
    projects = Project.query.all()
    employees = users.query.filter_by(usertype='employee').all()

    employees_list = [{'userid': emp.userid, 'fullname': emp.fulname} for emp in employees]

    project_teams = {}
    for project in projects:
        teams = Teams.query.join(ProjectTeam).filter(ProjectTeam.project_id == project.project_id).all()
        team_members = []
        for team in teams:
            team_members.extend([{'userid': member.userid, 'fullname': member.fulname} for member in team.members])
        project_teams[project.project_id] = team_members

    if not task:
        flash('Task not found or you do not have permission to update it.', 'danger')
        return redirect(request.referrer)

    selected_employee_ids = [assignment.employee_id for assignment in TaskAssignment.query.filter_by(task_id=task.task_id).all()]

    if request.method == 'POST':
        task_name = request.form['task_name']
        start_date_str = request.form['start_date']
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid start date format.', 'danger')
            return render_template("admin/tasks/update_task.html", task=task, project_teams=project_teams, employees=employees_list, projects=projects, selected_employee_ids=selected_employee_ids)

        if start_date < date.today():
            flash('Start date cannot be in the past.', 'danger')
            return render_template("admin/tasks/update_task.html", task=task, project_teams=project_teams, employees=employees_list, projects=projects, selected_employee_ids=selected_employee_ids)

        if task.project_id:
            project = Project.query.get(task.project_id)
            if project and start_date < project.start_date:
                flash(f'Task start date cannot be earlier than the project start date ({project.start_date.strftime("%Y-%m-%d")}).', 'danger')
                return redirect(request.referrer)

        close_date = request.form.get('close_date')
        if close_date:
            close_date = datetime.strptime(close_date, '%Y-%m-%d').date()
            if close_date < start_date:
                flash('Close date cannot be earlier than the start date.', 'danger')
                return redirect(request.referrer)
        else:
            close_date = None

        selected_employee_ids = request.form.getlist('employees[]')
        task.task_name = task_name
        task.start_date = start_date
        task.close_date = close_date

        TaskAssignment.query.filter_by(task_id=task.task_id).delete()
        for employee_id in selected_employee_ids:
            assignment = TaskAssignment(task_id=task.task_id, employee_id=employee_id)
            db.session.add(assignment)

        db.session.commit()
        flash('Task updated successfully!', 'success')
        return redirect(request.referrer)

    return render_template("admin/tasks/update_task.html", task=task, employees=employees_list, project_teams=project_teams, projects=projects, selected_employee_ids=selected_employee_ids)

#---------------------------------------------------------------projects-------------------------------------------------------------------

@admin_routes.route('/projects', methods=['GET', 'POST'])
@login_required
@admin_required
def projects():
    if request.method == 'POST':
        project_id = request.form.get('project_id')
        project = Project.query.get(project_id)

        if project:
            today = datetime.today().date()
            if 'open' in request.form:
                if project.end_date and project.end_date > today:
                    project.start_date = today
                project.statut = 'in progress'
                status = 'Open'
            elif 'close' in request.form:
                project.statut = 'Closed'
                status = 'Closed'

            db.session.commit()
            flash(f'Project is now {project.statut.lower()}', 'success')
        else:
            flash('Project not found', 'danger')

        return redirect(url_for('admin_routes.projects'))

    projectsq = Project.query.all()
    projects = []

    for project in projectsq:
        status = get_project_status(project)
        teams = [pt.team_name for pt in project.teams]
        project_tuple = (project, status, teams)
        projects.append(project_tuple)

    return render_template("admin/projects/projects.html", projects=projects)

@admin_routes.route('/projects/create_project', methods=['GET', 'POST'])
@login_required
@admin_required
def create_project():
    if request.method == 'POST':
        project_name = request.form['project_name']
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        description = request.form.get('description')
        selected_teams = request.form.getlist('teams')
        created_by = current_user.userid

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid start date format.', 'danger')
            return render_template('admin/projects/addproject.html', teams=Teams.query.all())

        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid end date format.', 'danger')
            return render_template('admin/projects/addproject.html', teams=Teams.query.all())

        if start_date < date.today():
            flash('Start date cannot be in the past.', 'danger')
            return render_template('admin/projects/addproject.html', teams=Teams.query.all())

        if end_date < start_date:
            flash('End date cannot be earlier than the start date.', 'danger')
            return render_template('admin/projects/addproject.html', teams=Teams.query.all())

        new_project = Project(
            project_name=project_name,
            start_date=start_date,
            end_date=end_date,
            description=description,
            created_by=created_by
        )

        db.session.add(new_project)
        db.session.flush()

        for team_id in selected_teams:
            project_team = ProjectTeam(project_id=new_project.project_id, team_id=team_id)
            db.session.add(project_team)

        db.session.commit()

        flash('Project created successfully!', 'success')
        return redirect(url_for('admin_routes.projects'))

    teams = Teams.query.all()
    return render_template('admin/projects/addproject.html', teams=teams)

@admin_routes.route('/projects/update/<string:token>', methods=['GET', 'POST'])
@login_required
@admin_required
def update_project(token):
    project = Project.query.filter_by(token=token).first_or_404()
    all_teams = Teams.query.all()

    if request.method == 'POST':
        project_name = request.form['project_name']
        start_date_str = request.form['start_date']
        end_date_str = request.form['end_date']
        description = request.form['description']
        selected_team_ids = request.form.getlist('teams')

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid start date format.', 'danger')
            return render_template('admin/projects/addproject.html', teams=Teams.query.all())

        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid end date format.', 'danger')
            return render_template('admin/projects/addproject.html', teams=Teams.query.all())

        if start_date < date.today():
            flash('Start date cannot be in the past.', 'danger')
            return render_template('admin/projects/addproject.html', teams=Teams.query.all())

        if end_date < start_date:
            flash('End date cannot be earlier than the start date.', 'danger')
            return render_template('admin/projects/addproject.html', teams=Teams.query.all())
        project.project_name = project_name
        project.start_date = start_date
        project.end_date = end_date
        project.description = description

        ProjectTeam.query.filter_by(project_id=project.project_id).delete()
        for team_id in selected_team_ids:
            project_team = ProjectTeam(project_id=project.project_id, team_id=team_id)
            db.session.add(project_team)

        db.session.commit()
        flash('Project updated successfully!', 'success')
        return redirect(url_for('admin_routes.projects'))

    return render_template('admin/projects/update_project.html', project=project, all_teams=all_teams)

@admin_routes.route('/projects/delete/<int:project_id>', methods=['POST'])
@login_required
@admin_required
def delete_project(project_id):
    project_teams = ProjectTeam.query.filter_by(project_id=project_id).all()
    for project_team in project_teams:
        db.session.delete(project_team)

    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted successfully!', 'success')
    return redirect(request.referrer)

@admin_routes.route("/projects/project_details/<string:token>", methods=['GET', 'POST'])
@login_required
@admin_required
def project_details(token):
    if request.method == 'POST':
        project_id = request.form.get('project_id')
        project = Project.query.get(project_id)
        if project:
            if 'open' in request.form:
                project.statut = 'in progress'
                status = 'Open'
            elif 'close' in request.form:
                project.statut = 'Closed'
                status = 'Closed'
            db.session.commit()
            flash(f'Project status updated to {project.statut.lower()}', 'success')
        else:
            flash('Project not found.', 'danger')
        return redirect(url_for('admin_routes.project_details', token=token))
    project = Project.query.filter_by(token=token).first()
    if not project:
        flash('Project not found.', 'danger')
        return redirect(url_for('admin_routes.projects'))

    tasks = Task.query.filter_by(project_id=project.project_id).all()
    teams = Teams.query.join(ProjectTeam).filter(ProjectTeam.project_id == project.project_id).all()
    status = get_project_status(project)
    team_ids = db.session.query(Teams.team_id).join(ProjectTeam).filter(ProjectTeam.project_id == project.project_id).all()
    team_ids = [team_id for (team_id,) in team_ids]
    is_supervisor = db.session.query(Teams).filter(Teams.team_id.in_(team_ids), Teams.supervisor_id == current_user.userid).first() is not None

    team_details = []
    for team in teams:
        supervisor = users.query.filter_by(userid=team.supervisor_id).first()
        members = [{'userid': member.userid, 'fullname': member.fulname, 'Utoken': member.Utoken} for member in team.members]
        team_details.append({
            'team_name': team.team_name,
            'supervisor': supervisor,
            'members': members
        })

    return render_template('admin/projects/projectdetails.html', project=project, status=status, tasks=tasks, team_details=team_details)

@admin_routes.route('/update_project_statut', methods=['POST'])
@login_required
@admin_required
def update_project_statut():
    if request.method == 'POST':
        project_id = request.form.get('project_id')
        project = Project.query.get(project_id)
        status = get_project_status(project)
        if project:
            if 'open' in request.form:
                if status in ['Upcoming', 'Closed']:
                    project.start_date = datetime.today().date()
                    Task.query.filter_by(project_id=project_id).update({'start_date': project.start_date})
                project.statut = 'in progress'
                status = 'Open'
            elif 'close' in request.form:
                project.statut = 'Closed'
                status = 'Closed'
            db.session.commit()
            flash(f'Project status updated to {project.statut.lower()}', 'success')
        else:
            flash('Project not found.', 'danger')
        return redirect(request.referrer)

#---------------------------------------------------------------calendar-------------------------------------------------------------------

@admin_routes.route('/calendar')
@login_required
@admin_required
def calendar():
    tasks = Task.query.all()
    projects = Project.query.all()
    events = Event.query.all()
    calendar_events = []
    user = current_user
    for task in tasks:
        calendar_events.append({
            'id': f'task-{task.token}',
            'title': task.task_name,
            'start': task.start_date.isoformat(),
            'end': task.close_date.isoformat(),
            'color': '#33ff00'
        })
    for project in projects:
        calendar_events.append({
            'id': f'project-{project.token}',
            'title': project.project_name,
            'start': project.start_date.isoformat(),
            'end': project.end_date.isoformat(),
            'color': "#0066ff"
        })

    for event in events:
        event_teams = EventTeam.query.filter_by(event_id=event.id).all()
        team_ids = [et.team_id for et in event_teams]
        teams = Teams.query.filter(Teams.team_id.in_(team_ids)).all()
        team_names = ', '.join([team.team_name for team in teams])
        event_employees = EventEmployee.query.filter_by(event_id=event.id).all()
        employee_ids = [ee.employee_id for ee in event_employees]
        employees = users.query.filter(users.userid.in_(employee_ids)).all()
        employee_names = ', '.join([employee.fulname for employee in employees])
        calendar_events.append({
            'id': f'event-{event.token}',
            'title': event.title,
            'start': event.At.isoformat(),
            'salle': event.salle,
            'teams': team_names if team_names else 'No Team Assigned',
            'employees': employee_names if employee_names else 'No Employees Assigned',
            'color': '#ff0000'
        })

    return render_template('components/calendar.html', calendar_events=calendar_events, user=user)

@admin_routes.route('/calendar/events/update/<string:token>', methods=['GET', 'POST'])
@login_required
@admin_required
def update_event(token):
    event = Event.query.filter_by(token=token).first_or_404()

    if request.method == 'POST':
        event.title = request.form.get('title')
        event.At = datetime.strptime(request.form.get('start'), '%Y-%m-%dT%H:%M')
        event.salle = request.form.get('salle')
        if event.At < date.today():
            flash('Start date cannot be in the past.', 'danger')
            return redirect(request.referrer)
        EventTeam.query.filter_by(event_id=event.id).delete()
        team_ids = request.form.getlist('teams[]')
        for team_id in team_ids:
            team_id = int(team_id)
            db.session.add(EventTeam(event_id=event.id, team_id=team_id))

        EventEmployee.query.filter_by(event_id=event.id).delete()
        employee_ids = request.form.getlist('employees[]')
        for emp_id in employee_ids:
            emp_id = int(emp_id)
            db.session.add(EventEmployee(event_id=event.id, employee_id=emp_id))

        try:
            db.session.commit()
            flash('Event updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {e}', 'danger')

        return redirect(request.referrer)

    teams = Teams.query.all()
    teams_data = [{'team_id': team.team_id, 'team_name': team.team_name, 'supervisor_id': team.supervisor_id} for team in teams]

    employees = users.query.all()
    employees_data = [{'userid': emp.userid, 'fulname': emp.fulname, 'usertype': emp.usertype, 'teams': [team.team_id for team in emp.team_memberships]} for emp in employees]

    event_teams = [et.team_id for et in EventTeam.query.filter_by(event_id=event.id).all()]
    event_employees = [ee.employee_id for ee in EventEmployee.query.filter_by(event_id=event.id).all()]

    return render_template('admin/update_event.html', event=event, teams_data=teams_data, employees_data=employees_data, event_teams=event_teams, event_employees=event_employees)

@admin_routes.route('/calendar/events/delete/<string:token>', methods=['POST'])
@login_required
@admin_required
def delete_event(token):
    try:
        event = Event.query.filter_by(token=token).first_or_404()
        EventTeam.query.filter_by(event_id=event.id).delete()
        EventEmployee.query.filter_by(event_id=event.id).delete()
        db.session.delete(event)
        db.session.commit()
        return flash({'Event updated successfully!': 'success'})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting event: {e}")
        return jsonify({'status': 'error', 'message': 'An error occurred while deleting the event.'}), 500

@admin_routes.route('/calendar/calendar/add_event', methods=['GET', 'POST'])
@login_required
@admin_required
def add_event():
    if request.method == 'POST':
        title = request.form['title']
        start_date = request.form['start_date']
        salle = request.form['salle']
        team_ids = request.form.getlist('teams[]')
        employee_ids = request.form.getlist('employees[]')

        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%dT%H:%M')
            if start_date < datetime.combine(date.today(), datetime.min.time()):
                flash('Start date cannot be in the past.', 'danger')
                return render_template('admin/addevent.html', teams_data=teams_data, employees_data=employees_data)
            new_event = Event(title=title, At=start_date, token=secrets.token_urlsafe(), salle=salle, creator_id=current_user.userid)
            db.session.add(new_event)
            db.session.commit()
            for team_id in team_ids:
                team_id = int(team_id)
                db.session.add(EventTeam(event_id=new_event.id, team_id=team_id))
            for emp_id in employee_ids:
                emp_id = int(emp_id)
                if not EventEmployee.query.filter_by(event_id=new_event.id, employee_id=emp_id).first():
                    db.session.add(EventEmployee(event_id=new_event.id, employee_id=emp_id))
            db.session.commit()
            flash('Event added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {e}', 'danger')
        return redirect(request.referrer)
    teams = Teams.query.all()
    teams_data = [{'team_id': team.team_id, 'team_name': team.team_name, 'supervisor_id': team.supervisor_id} for team in teams]
    employees = users.query.all()
    employees_data = [{'userid': emp.userid, 'fulname': emp.fulname, 'usertype': emp.usertype, 'teams': [team.team_id for team in emp.team_memberships]} for emp in employees]

    return render_template('admin/addevent.html', teams_data=teams_data, employees_data=employees_data)
#----------------------------------------------------account----------------------------------------------------------------------------------
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@admin_routes.route('/profile/<string:Utoken>', methods=['GET', 'POST'])
@login_required
def profile(Utoken):
    user = users.query.filter_by(Utoken=Utoken).first()

    if request.method == 'POST':
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and allowed_file(file.filename):
                image_binary = file.read()
                print(len(image_binary))
                user.profile_picture = image_binary
                db.session.commit()

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'status': 'success'}), 200

                return redirect(url_for('employee_routes.profile', Utoken=user.Utoken))

    return render_template('components/account.html', user=user)

@admin_routes.route('/change_full_name/<Utoken>', methods=['POST'])
@login_required
def change_full_name(Utoken):
    user = users.query.filter_by(Utoken=Utoken).first()

    new_full_name = request.form.get('new_full_name')
    current_password = request.form.get('current_password')

    if bcrypt.check_password_hash(user.Pasword, current_password):
        user.fulname = new_full_name
        db.session.commit()
        flash('Full name updated successfully', 'success')
    else:
        flash('Current password is incorrect', 'danger')

    return redirect(url_for('employee_routes.profile', Utoken=Utoken))

@admin_routes.route('/change_email/<Utoken>', methods=['POST'])
@login_required
def change_email(Utoken):
    user = users.query.filter_by(Utoken=Utoken).first()
    new_email = request.form.get('new_email')
    password_confirmation = request.form.get('password_confirmation')

    if bcrypt.check_password_hash(user.Pasword, password_confirmation):
        user.email = new_email
        db.session.commit()
        flash('Email updated successfully', 'success')
    else:
        flash('Password confirmation is incorrect', 'danger')

    return redirect(url_for('employee_routes.profile', Utoken=Utoken))

@admin_routes.route('/change_password/<Utoken>', methods=['POST'])
@login_required
def change_password(Utoken):
    user = users.query.filter_by(Utoken=Utoken).first()
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_new_password = request.form.get('confirm_new_password')
    if bcrypt.check_password_hash(user.Pasword, current_password):
        if new_password == confirm_new_password:
            user.Pasword = bcrypt.generate_password_hash(new_password)
            db.session.commit()
            flash('Password updated successfully', 'success')
        else:
            flash('New passwords do not match', 'danger')
    else:
        flash('Current password is incorrect', 'danger')

    return redirect(url_for('employee_routes.profile', Utoken=Utoken))

@admin_routes.route('/update_email/<Utoken>', methods=['POST'])
@login_required
def update_Eemail(Utoken):
    user = users.query.filter_by(Utoken=Utoken).first()
    new_email = request.form.get('new_email')
    
    if new_email:
        user.email = new_email
        db.session.commit()
        flash('Email updated successfully', 'success')

    
    return redirect(request.referrer)

@admin_routes.route('/update_password/<Utoken>', methods=['POST'])
@login_required
def update_Epassword(Utoken):
    user = users.query.filter_by(Utoken=Utoken).first()
    new_password = request.form.get('new_password')
    confirm_new_password = request.form.get('confirm_new_password')

    if new_password == confirm_new_password:
        user.Pasword = bcrypt.generate_password_hash(new_password)
        db.session.commit()
        flash('Password updated successfully', 'success')
    else:
        flash('New passwords do not match', 'danger')

    return redirect(request.referrer)
