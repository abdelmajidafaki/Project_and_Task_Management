# utils.py
from datetime import datetime, date

def get_task_status(task):
    today = date.today()
    if task.start_date > today:
        return "Upcoming"
    elif task.start_date <= today and (task.close_date is None or task.close_date >= today) and task.status == 'In Progress':
        return "Open"
    elif task.status == 'COMPLETED':
        return "Closed"
    else:
        return "Closed"

def calculate_days_to_close(task, today):
    if task.close_date and task.status == "In Progress":
        return (task.close_date - today).days
    return None

def sort_tasks(tasks):
    def to_datetime(d):
        return datetime.combine(d, datetime.min.time()) if isinstance(d, date) else d or datetime.max

    def sort_key(task_info):
        task, _, _, _, status, _ = task_info  # Adjust to 6 elements
        start_date = to_datetime(task.start_date)
        close_date = to_datetime(task.close_date)
        if status == 'Open':
            return (0, close_date)
        elif status == 'Upcoming':
            return (1, start_date)
        else:
            return (2, datetime.max)

    tasks.sort(key=sort_key)
    return tasks