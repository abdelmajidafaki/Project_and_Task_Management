from flask import Blueprint, render_template, request, flash, redirect, url_for,jsonify
from flask_login import login_required, current_user
from extensions import db
from functools import wraps
from modals import users, Task, TaskAssignment, Event,Task_Progression,EventEmployee, EventTeam,PersonalTask, PersonalTaskProgression,Teams,TeamsMember,Project,ProjectTeam
import secrets
from sqlalchemy.orm import joinedload
from datetime import datetime, date
from sqlalchemy import exists

employee_routes = Blueprint('employee_routes', __name__)

def employee_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.usertype != "employee":
            flash("You do not have permission to access this page.", 'danger')
            return redirect(url_for('auth_routes.loginpage'))
        return func(*args, **kwargs)
    return decorated_function

def get_task_status(task):
    today = date.today()
    status = ""
    if task.start_date > today:
        status = "Upcoming"
    elif task.start_date <= today and (task.close_date is None or task.close_date >= today) and task.status == 'In Progress':
        status = "Open"
    elif task.status == 'COMPLETED':
        status = "Closed"
    else:
        status = "Closed"

    daystoclose = (task.close_date - today).days if task.close_date else None
    
    
    return status, daystoclose

def process_date(date_str):
    if not date_str or date_str == '0000-00-00':
        return date.today()
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        return date.today()

def get_project_status(project):
    today = date.today()
    if project.start_date > today:
        return "Upcoming"
    elif project.start_date <= today and (project.end_date is None or project.end_date >= today) and project.statut == 'in progress':
        return "Open"
    else:
        return "Closed"
@employee_routes.route("/Assignedtasks", methods=['GET', 'POST'])
@login_required
@employee_required
def Assignedtasks():
    user_id = current_user.userid
    user = users.query.get(user_id)

    if user:
        assigned_tasks = db.session.query(Task) \
            .join(TaskAssignment, Task.task_id == TaskAssignment.task_id) \
            .filter(TaskAssignment.employee_id == user_id) \
            .all()

        tasks = [(task, task.admin.fulname, *get_task_status(task)) for task in assigned_tasks]

        def to_datetime(d):
            if isinstance(d, datetime):
                return d
            elif isinstance(d, date):
                return datetime.combine(d, datetime.min.time())
            return datetime.max
        
        def sort_key(task_info):
            task, _, status, daystoclose = task_info
            start_date = to_datetime(task.start_date)
            close_date = to_datetime(task.close_date)
            if status == 'Open':
                return (0, close_date)
            elif status == 'Upcoming':
                return (1, start_date)
            return (2, datetime.max)
        
        tasks.sort(key=sort_key)

        return render_template("employee/Asyntasks/employeepage.html", user=user, tasks=tasks)
    else:
        flash("User not found. Please log in again.", 'danger')
        return redirect(url_for('auth_routes.loginpage'))

@employee_routes.route("/Assignedtasks/taskdetails/<token>/<etoken>", methods=['GET', 'POST'])
@login_required
@employee_required
def taskdetails(token, etoken):
    user_id = current_user.userid
    user = users.query.get(user_id)
    task = Task.query.filter_by(token=token).first()
    employee = users.query.filter_by(Utoken=etoken).first()
    task_assignment = TaskAssignment.query.filter_by(task_id=task.task_id, employee_id=employee.userid).first()
    task_progressions = Task_Progression.query.filter_by(task_id=task.task_id).all()
    task_teams = task.project.teams if task.project else []
    is_supervisor = any(team.supervisor_id == current_user.userid for team in task_teams)
    
    if task:
        if request.method == 'POST':
            if 'mark_task_done' in request.form:
                task.status = 'COMPLETED'
                db.session.commit()
                flash('Task marked as done.', 'success')
                return redirect(url_for('employee_routes.taskdetails', token=token, etoken=etoken))
            
            progression_id = request.form.get('progression_id')
            progression = Task_Progression.query.get(progression_id)

            if progression:
                progression.end_at = date.today()
                progression.statut = 'Completed'
                db.session.commit()
                flash('Progression marked as completed.', 'success')
                return redirect(url_for('employee_routes.taskdetails', token=token, etoken=etoken))
            else:
                flash('Progression not found.', 'danger')   

        status, _ = get_task_status(task)
        
        return render_template("employee/Asyntasks/taskdetails.html",is_supervisor=is_supervisor ,user=user, task=task, task_assignment=task_assignment, task_progressions=task_progressions, status=status)
    else:
        flash("Task not found.", 'danger')
    return redirect(url_for('employee_routes.Assignedtasks'))

@employee_routes.route('/Assignedtasks/taskdetails/addprogression/<token>/<etoken>', methods=['GET', 'POST'])
@login_required
@employee_required
def addprogression(token, etoken):
    user_id = current_user.userid
    user = users.query.get(user_id)
    employee = users.query.filter_by(Utoken=etoken).first()
    task = Task.query.filter_by(token=token).first()
    task_assignment = TaskAssignment.query.filter_by(task_id=task.task_id, employee_id=employee.userid).first()

    if task_assignment:
        if request.method == 'POST':
            progname = request.form.get('progname')
            start_at = process_date(request.form.get('start_at'))
            
            new_progression = Task_Progression(
                progname=progname,
                start_at=start_at,
                task_id=task.task_id,
                employee_id=employee.userid
            )
            
            db.session.add(new_progression)
            db.session.commit()
            flash('Task progression added successfully.', 'success')
            return redirect(url_for('employee_routes.Assignedtasks'))
        
        return render_template('employee/Asyntasks/taskprog.html', task_id=task.task_id, employee_id=user_id)
    else:
        flash('You are not authorized to add progression for this task.', 'danger')
        return redirect(url_for('employee_routes.taskdetails', token=token, etoken=etoken))

@employee_routes.route('/Assignedtasks/delete_pertask/<string:token>')
@login_required
@employee_required
def delete_pertask(token):
    task = PersonalTask.query.filter_by(token=token).first_or_404()
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('employee_routes.personaltasks'))

@employee_routes.route('/addpersonaltask', methods=['GET', 'POST'])
@login_required
@employee_required
def addpertask():
    if request.method == 'POST':
        task_name = request.form.get('taskName')
        do_at = process_date(request.form.get('doAt'))
        completed_at = request.form.get('completedAt')
        state = request.form.get('state')
        description = request.form.get('description')           
        employee_id = current_user.userid
     
        new_task = PersonalTask(
            TaskName=task_name,
            DoAt=do_at,
            CompletedAt=completed_at if completed_at else None,
            State=state,
            employee_id=employee_id,
            Description=description if description else None,
            token=secrets.token_urlsafe()
        )

        db.session.add(new_task)
        db.session.commit()
        return redirect(url_for('employee_routes.personaltasks'))
    
    return render_template('employee/persotasks/addpertask.html')

@employee_routes.route('/toggle_pertask/<string:token>/<string:action>')
@login_required
@employee_required
def toggle_pertask(token, action):
    task = PersonalTask.query.filter_by(token=token).first_or_404()
    
    if action == 'complete':
        task.State = 'completed'
        task.CompletedAt = date.today()
        flash('Task marked as completed.', 'success')
    elif action == 'rollback':
        task.State = 'in progress'
        task.CompletedAt = None
        flash('Task mark rolled back', 'warning')  

    db.session.commit()
    return redirect(url_for('employee_routes.personaltasks'))

@employee_routes.route('/edit_pertask/<string:token>', methods=['GET', 'POST'])
@login_required
@employee_required
def edit_pertask(token):
    task = PersonalTask.query.filter_by(token=token).first_or_404()
    
    if request.method == 'POST':
        task.TaskName = request.form.get('taskName')
        task.Description = request.form.get('description') 
        task.DoAt = process_date(request.form.get('doAt'))
        task.CompletedAt = request.form.get('completedAt')
        db.session.commit()
        return redirect(url_for('employee_routes.personaltasks'))
    
    return render_template('employee/persotasks/editpertask.html', task=task)

@employee_routes.route('/personaltasks')
@login_required
@employee_required
def personaltasks():
    tasks = PersonalTask.query.filter(PersonalTask.employee_id == current_user.userid).all()
    return render_template('employee/persotasks/personalstask.html', tasks=tasks)

@employee_routes.route('/personaltasks/personaltaskdetail/<Ptoken>', methods=['GET', 'POST'])
@login_required
@employee_required
def personaltaskdetail(Ptoken):
    task = PersonalTask.query.filter_by(token=Ptoken).first()
    task_progressions = PersonalTaskProgression.query.filter_by(Ptask_id=task.PTDID).all()

    if request.method == 'POST':
        if 'mark_task_done' in request.form:
            task.State = 'completed'
            task.CompletedAt = date.today()
            db.session.commit()
            flash('Task marked as completed.', 'success')
            return redirect(url_for('employee_routes.personaltaskdetail', Ptoken=Ptoken))
        if 'Task_not_done' in request.form:
            task.State = 'in progress'
            task.CompletedAt = None
            db.session.commit()
            flash('Task mark rolled back.', 'success')
            return redirect(url_for('employee_routes.personaltaskdetail', Ptoken=Ptoken))

        if 'progression_id' in request.form:
            progression_id = request.form.get('progression_id')
            progression = PersonalTaskProgression.query.get(progression_id)

            if progression:
                progression.completed_at = date.today()
                progression.status = 'Completed'
                db.session.commit()
                flash('Progression marked as completed.', 'success')
                return redirect(url_for('employee_routes.personaltaskdetail', Ptoken=Ptoken))
            else:
                flash('Progression not found.', 'danger')
    
    return render_template('employee/persotasks/personal_taskdetail.html', task=task, task_progressions=task_progressions)

@employee_routes.route('/personaltasks/personaltaskdetail/addpersonalprogression/<Ptoken>', methods=['GET', 'POST'])
@login_required
@employee_required
def addpersonalprogression(Ptoken):
    task = PersonalTask.query.filter_by(token=Ptoken).first()

    if not task:
        flash('Personal Task not found.', 'danger')
        return redirect(url_for('employee_routes.personaltasks'))

    if request.method == 'POST':
        progname = request.form.get('progname')
        start_at = process_date(request.form.get('start_at'))
        
        if not progname:
            flash('Progress name is required.', 'danger')
            return redirect(url_for('employee_routes.addpersonalprogression', Ptoken=Ptoken))
        
        new_progression = PersonalTaskProgression(
            Ptask_id=task.PTDID,
            progname=progname,
            status='in progress',
            start_at=start_at,
            employee_id=current_user.userid
        )
        
        db.session.add(new_progression)
        db.session.commit()
        flash('Personal Task Progression added successfully.', 'success')
        return redirect(url_for('employee_routes.personaltaskdetail', Ptoken=Ptoken))
    
    return render_template('employee/persotasks/add_personal_progression.html', task=task)

@employee_routes.route('/teams', methods=['GET'])
@employee_required
@login_required
def employee_teams():
    user_id = current_user.userid
    teams = db.session.query(Teams).join(TeamsMember).filter(TeamsMember.userid == user_id).union(
        db.session.query(Teams).filter(Teams.supervisor_id == user_id)
    ).all()
    team_data = {}
    for team in teams:
        team_members = [{'fullname': member.fulname, 'email': member.email} for member in team.members]
        supervisor_info = {
            'fullname': team.supervisor.fulname if team.supervisor else None,
            'email': team.supervisor.email if team.supervisor else None
        } if team.supervisor else None
        team_data[team] = {
            'members': team_members,
            'supervisor': supervisor_info,
            'projects': [project.project_name for project in team.projects]
        }
    supervisor_teams = [team for team in teams if team.supervisor and team.supervisor.userid == user_id]
    member_teams = [team for team in teams if team.supervisor and team.supervisor.userid != user_id]

    return render_template('employee/empteam/myteam.html', supervisor_teams=supervisor_teams, member_teams=member_teams, team_data=team_data)

@employee_routes.route('/team_projects', methods=['GET'])
@employee_required
@login_required
def employee_projects():
    user_id = current_user.userid
    team_ids = db.session.query(Teams.team_id).join(TeamsMember).filter(
        TeamsMember.userid == user_id
    ).union(
        db.session.query(Teams.team_id).filter(Teams.supervisor_id == user_id)
    ).all()
    team_ids = [team_id for (team_id,) in team_ids]
    project_ids = db.session.query(ProjectTeam.project_id).filter(
        ProjectTeam.team_id.in_(team_ids)
    ).all()
    project_ids = [project_id for (project_id,) in project_ids]
    projects = Project.query.filter(Project.project_id.in_(project_ids)).options(joinedload(Project.teams)).all()
    project_data = [
        (
            project, 
            get_project_status(project), 
            [team.team_name for team in project.teams], 
            any(team.supervisor_id == user_id for team in project.teams)
        )
        for project in projects
    ]
    


    return render_template('employee/teamprojects/Tprojects.html', projects=project_data, user_id=user_id)

@employee_routes.route('/team_projects/project_details/<token>', methods=['GET'])
@employee_required
@login_required
def project_details(token):
    project = Project.query.filter_by(token=token).first_or_404()
    team_details = db.session.query(Teams).join(ProjectTeam).filter(ProjectTeam.project_id == project.project_id).all()
    is_supervisor = any(team.supervisor_id == current_user.userid for team in team_details)
    tasks = Task.query.filter_by(project_id=project.project_id).all()
    tasks_with_status = []
    for task in tasks:
        task_status, daystoclose = get_task_status(task)
        tasks_with_status.append({
            'task': task,
            'status': task_status,  
            'daystoclose': daystoclose  
        })
    return render_template('employee/teamprojects/Tprojectsdetails.html', project=project, status=get_project_status(project), team_details=team_details, tasks=tasks_with_status, is_supervisor=is_supervisor)

@employee_routes.route('/projects/create_new_task/<project_token>', methods=['GET', 'POST'])
@employee_required
@login_required
def create_project_task(project_token):
    project = Project.query.filter_by(token=project_token).first_or_404()

    teams = Teams.query.join(ProjectTeam).filter(ProjectTeam.project_id == project.project_id).all()
    employees = users.query.join(TeamsMember).filter(TeamsMember.team_id.in_([team.team_id for team in teams])).all()

    if request.method == 'POST':
        task_name = request.form['task_name']
        start_date = request.form['start_date']
        close_date = request.form.get('close_date')
        description = request.form.get('description')
        employee_ids = request.form.getlist('employees[]')

        if not task_name or not start_date:
            flash('Task name and start date are required.', 'danger')
            return redirect(request.url)

        new_task = Task(
            task_name=task_name,
            start_date=start_date,
            close_date=close_date,
            description=description,
            project_id=project.project_id,
            admin_id=current_user.userid
        )
        db.session.add(new_task)
        db.session.commit()

        for emp_id in employee_ids:
            db.session.add(TaskAssignment(task_id=new_task.task_id, employee_id=emp_id))
        db.session.commit()

        flash('Task created successfully!', 'success')
        return redirect(url_for('employee_routes.employee_projects'))

    return render_template('employee/teamprojects/addproject_tasks.html', selected_project_token=project_token, employees=employees)

@employee_routes.route('/projects/update_task/<task_token>', methods=['GET', 'POST'])
@employee_required
@login_required
def update_project_task(task_token):
    task = Task.query.filter_by(token=task_token).first_or_404()
    project = task.project
    team_ids = db.session.query(Teams.team_id).join(ProjectTeam).filter(ProjectTeam.project_id == project.project_id).all()
    team_ids = [team_id for (team_id,) in team_ids]
    is_supervisor = db.session.query(Teams).filter(Teams.team_id.in_(team_ids), Teams.supervisor_id == current_user.userid).first()

    if not is_supervisor:
        flash('You are not authorized to update this task.', 'danger')
        return redirect(url_for('employee_routes.employee_projects'))

    if request.method == 'POST':
        task.task_name = request.form['task_name']
        task.start_date = request.form['start_date']
        task.close_date = request.form.get('close_date')
        selected_employee_ids = request.form.getlist('employees[]')
        TaskAssignment.query.filter_by(task_id=task.task_id).delete()
        for employee_id in selected_employee_ids:
            assignment = TaskAssignment(task_id=task.task_id, employee_id=employee_id)
            db.session.add(assignment)

        db.session.commit()
        flash('Task updated successfully!', 'success')
        return redirect(url_for('employee_routes.project_details', token=project.token))
    employees = users.query.join(TeamsMember).filter(TeamsMember.team_id.in_(team_ids)).all()
    selected_employee_ids = [assignment.employee_id for assignment in task.assignments]

    return render_template('employee/teamprojects/update_team_ptasks.html', task=task, employees=employees, selected_employee_ids=selected_employee_ids)

@employee_routes.route("/projects/delete/<int:task_id>", methods=['GET','POST'])
@login_required
@employee_required
def delete_project_task(task_id):
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

@employee_routes.route('/update_project_task_statut', methods=['POST'])
@login_required
@employee_required
def update_project_task_statut():
    task_id = request.form.get('task_id')
    task = Task.query.get(task_id)
    if not task:
        flash('Task not found', 'danger')
        return redirect(request.referrer)  
    
    status, daystoclose = get_task_status(task)
    
    if 'opentask' in request.form:
        if status in ['Upcoming', 'Closed']:
            task.start_date = datetime.today().date()
        task.status = 'In Progress'
    elif 'closetask' in request.form:
        task.status = 'Closed by Admin'

    db.session.commit()
    flash(f'Task is now {task.status.lower()}', 'success')
    
    return redirect(request.referrer)
  
@employee_routes.route('/calendar')
@login_required
@employee_required
def calendar():
    user = current_user
    team_ids = [team.team_id for team in user.team_memberships]
    relevant_projects = Project.query.join(Project.teams).filter(
        (Teams.team_id.in_(team_ids)) |
        (Teams.supervisor_id == user.userid)
    ).distinct().all()

    assigned_task_ids_subquery = db.session.query(TaskAssignment.task_id).filter_by(employee_id=user.userid).subquery()
    project_ids = [project.project_id for project in relevant_projects]
    relevant_tasks = Task.query.filter(
        (Task.task_id.in_(assigned_task_ids_subquery)) |
        (Task.project_id.in_(project_ids))
    ).all()

    invited_event_ids = db.session.query(EventEmployee.event_id).filter_by(employee_id=user.userid).subquery()
    team_event_ids = db.session.query(EventTeam.event_id).filter(
        EventTeam.team_id.in_(team_ids)
    ).subquery()
    supervised_team_event_ids = db.session.query(EventTeam.event_id).join(Teams).filter(
        Teams.supervisor_id == user.userid,
        EventTeam.team_id == Teams.team_id
    ).subquery()

    combined_event_ids = db.session.query(Event.id).filter(
        Event.id.in_(invited_event_ids)
    ).union(
        db.session.query(Event.id).filter(
            Event.id.in_(team_event_ids)
        )
    ).union(
        db.session.query(Event.id).filter(
            Event.id.in_(supervised_team_event_ids)
        )
    ).subquery()

    relevant_events = Event.query.filter(Event.id.in_(combined_event_ids)).all()

    calendar_events = []

    for task in relevant_tasks:
        calendar_events.append({
            'id': f'task-{task.token}',
            'title': task.task_name,
            'start': task.start_date.isoformat(),
            'end': task.close_date.isoformat(),
            'color': '#33ff00'
        })

    for project in relevant_projects:
        calendar_events.append({
            'id': f'project-{project.token}',
            'title': project.project_name,
            'start': project.start_date.isoformat(),
            'end': project.end_date.isoformat(),
            'color': '#0066ff'
        })

    for event in relevant_events:
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
