from extensions import db
import secrets
from flask_login import UserMixin
from sqlalchemy import LargeBinary

class users(db.Model, UserMixin):
    __tablename__ = 'users'
    userid = db.Column(db.Integer, primary_key=True)
    fulname = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    Pasword = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='inprogress')
    usertype = db.Column(db.String(20), default='not defined')
    Utoken = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe())
    profile_picture = db.Column(LargeBinary, nullable=True)
    assigned_tasks = db.relationship('TaskAssignment', back_populates='employee')
    tasks_assigned = db.relationship('Task', back_populates='admin')
    task_progressions = db.relationship('Task_Progression', back_populates='employee')
    personal_tasks = db.relationship('PersonalTask', back_populates='employee')
    personal_task_progressions = db.relationship('PersonalTaskProgression', back_populates='employee')
    teams_supervised = db.relationship('Teams', foreign_keys='Teams.supervisor_id', back_populates='supervisor')
    team_memberships = db.relationship('Teams', secondary='teams_member', back_populates='members')

    def get_id(self):
        return str(self.userid)

class Task(db.Model):
    __tablename__ = 'tasks'
    task_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date)
    close_date = db.Column(db.Date)
    description = db.Column(db.Text, nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.userid'), nullable=False)
    status = db.Column(db.String(20), default='In Progress')
    token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe())
    project_id = db.Column(db.Integer, db.ForeignKey('projects.project_id'), nullable=True)

    admin = db.relationship("users", foreign_keys=[admin_id], back_populates="tasks_assigned")
    project = db.relationship("Project", back_populates="tasks")
    assignments = db.relationship("TaskAssignment", back_populates="task", cascade="all, delete-orphan")
    task_progressions = db.relationship('Task_Progression', back_populates='task_ref', lazy=True)

class TaskAssignment(db.Model):
    __tablename__ = 'task_assignments'
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.task_id'), primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('users.userid'), primary_key=True)

    task = db.relationship("Task", back_populates="assignments")
    employee = db.relationship("users", back_populates="assigned_tasks")

class Task_Progression(db.Model):
    __tablename__ = 'task_progression'
    prog_id = db.Column(db.Integer, primary_key=True)
    progname = db.Column(db.String(255), nullable=False)
    start_at = db.Column(db.Date, nullable=False)
    end_at = db.Column(db.Date, nullable=True)
    statut = db.Column(db.String(255), nullable=True, default='inprogress')
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.task_id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('users.userid'), nullable=False)

    task_ref = db.relationship('Task', back_populates='task_progressions')
    employee = db.relationship('users', back_populates='task_progressions')

class PersonalTask(db.Model):
    __tablename__ = 'PersonalTasks'
    PTDID = db.Column(db.Integer, primary_key=True, autoincrement=True)
    TaskName = db.Column(db.String(255), nullable=False)
    DoAt = db.Column(db.Date)
    CompletedAt = db.Column(db.Date)
    Description = db.Column(db.Text, nullable=True)
    State = db.Column(db.String(255), nullable=False, default='in progress')
    employee_id = db.Column(db.Integer, db.ForeignKey('users.userid'), nullable=True)
    token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe())

    employee = db.relationship('users', back_populates='personal_tasks')

class PersonalTaskProgression(db.Model):
    __tablename__ = 'personal_task_progression'
    prog_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    Ptask_id = db.Column(db.Integer, db.ForeignKey('PersonalTasks.PTDID'), nullable=False)
    progname = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(255), nullable=False)
    start_at = db.Column(db.Date, nullable=False)
    completed_at = db.Column(db.Date, nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('users.userid'), nullable=True)

    employee = db.relationship('users', back_populates='personal_task_progressions')

class Teams(db.Model):
    __tablename__ = 'teams'
    team_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_name = db.Column(db.String(255), nullable=False)
    supervisor_id = db.Column(db.Integer, db.ForeignKey('users.userid'))
    TETOKEN = db.Column(db.String(255), unique=True, nullable=False)

    supervisor = db.relationship('users', foreign_keys=[supervisor_id], back_populates='teams_supervised')
    members = db.relationship('users', secondary='teams_member', back_populates='team_memberships')
    team_projects = db.relationship('ProjectTeam', back_populates='team')
    events = db.relationship('EventTeam', back_populates='team')  # Added this relationship

class TeamsMember(db.Model):
    __tablename__ = 'teams_member'
    team_id = db.Column(db.Integer, db.ForeignKey('teams.team_id'), primary_key=True)
    userid = db.Column(db.Integer, db.ForeignKey('users.userid'), primary_key=True)

class Project(db.Model):
    __tablename__ = 'projects'
    project_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    project_name = db.Column(db.String(255), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    statut = db.Column(db.String(255), nullable=False, default='in progress')
    description = db.Column(db.Text, nullable=True)
    token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe())
    created_by = db.Column(db.Integer, db.ForeignKey('users.userid'), nullable=False)

    tasks = db.relationship('Task', back_populates='project')
    project_teams = db.relationship('ProjectTeam', back_populates='project')
    teams = db.relationship('Teams', secondary='project_team', backref=db.backref('projects', lazy=True))

class ProjectTeam(db.Model):
    __tablename__ = 'project_team'
    project_id = db.Column(db.Integer, db.ForeignKey('projects.project_id'), primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.team_id'), primary_key=True)

    project = db.relationship('Project', back_populates='project_teams')
    team = db.relationship('Teams', back_populates='team_projects')

class Event(db.Model):
    __tablename__ = 'meeting_event'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    At = db.Column(db.DateTime, nullable=False)
    salle = db.Column(db.String(100), nullable=False)
    token = db.Column(db.String(36), unique=True, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.userid'), nullable=False)

    event_teams = db.relationship('EventTeam', back_populates='event')
    event_employees = db.relationship('EventEmployee', back_populates='event')
    creator = db.relationship('users', backref='events_created')

class EventEmployee(db.Model):
    __tablename__ = 'event_employees'
    event_id = db.Column(db.Integer, db.ForeignKey('meeting_event.id'), primary_key=True, nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('users.userid'), primary_key=True, nullable=False)

    event = db.relationship('Event', back_populates='event_employees')
    employee = db.relationship('users')

class EventTeam(db.Model):
    __tablename__ = 'event_team'
    event_id = db.Column(db.Integer, db.ForeignKey('meeting_event.id'), primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.team_id'), primary_key=True)

    event = db.relationship('Event', back_populates='event_teams')
    team = db.relationship('Teams', back_populates='events')
