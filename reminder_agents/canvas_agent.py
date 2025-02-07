#TODO: use agent storage to store the last time the email was sent
from uagents import Agent, Context, Model
import dotenv
import os
from canvasapi import Canvas
from datetime import datetime, timedelta, timezone
from datetime import datetime, timedelta, timezone
from canvasapi import Canvas
import os 
import dotenv
import pytz 
from uagents.setup import fund_agent_if_low
from local_cache import NotificationCache
from fetchai import fetch
from fetchai.crypto import Identity
from fetchai.communication import (
    send_message_to_agent
)

class EmailRequest(Model):
    msg: str

dotenv.load_dotenv()
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
API_URL = "https://umd.instructure.com"

canvas = Canvas(API_URL, ACCESS_TOKEN)
eastern = pytz.timezone('America/New_York')

agent = Agent(name="Canvas", 
              port=8000, 
              endpoint=["http://localhost:8000/submit"])
fund_agent_if_low(agent.wallet.address())

notification_cache = NotificationCache()

  
@agent.on_event("startup")
async def introduce_agent(ctx: Context):
    ctx.logger.info(f"Hello, I'm agent {agent.name} and my address is {agent.address}.")
 
 
@agent.on_interval(period=15.0) #make it like 15 minutes when actually deployed
async def get_courses(ctx: Context):

    now = datetime.now(eastern)
    
    # Define time windows
    six_hours = now + timedelta(hours=6)
    twelve_hours = now + timedelta(hours=12)
    twenty_four_hours = now + timedelta(hours=120)

    # Initialize dictionaries for each time window
    assignments_by_window = {
        '6h': [],
        '12h': [],
        '72h': []
    }

    # Fetch all active courses
    courses = canvas.get_courses(enrollment_state="active", include=['favorites'])
    starred_courses = [course for course in courses if getattr(course, 'is_favorite', False)]
    print(starred_courses)

    for course in starred_courses:
        assignments = course.get_assignments()
        for assignment in assignments:
            if assignment.due_at:  # Check if due date exists
                due_date = datetime.strptime(assignment.due_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                due_date = due_date.astimezone(eastern)
                
                assignment_info = {
                    'course': course.name,
                    'id': assignment.id,
                    'assignment': assignment.name,
                    'due_time': due_date.strftime("%Y-%m-%d %I:%M %p EST")
                }

                if now <= due_date <= six_hours and not notification_cache.has_been_sent(assignment_info['id'], '6h'):
                    assignments_by_window['6h'].append(assignment_info)
                elif six_hours < due_date <= twelve_hours and not notification_cache.has_been_sent(assignment_info['id'], '12h'):
                    assignments_by_window['12h'].append(assignment_info)
                elif twelve_hours < due_date <= twenty_four_hours and not notification_cache.has_been_sent(assignment_info['id'], '72h'):
                    assignments_by_window['72h'].append(assignment_info)


    all_assignments = assignments_by_window['6h'] + assignments_by_window['12h'] + assignments_by_window['72h']
    print(all_assignments)
    
    if all_assignments:
        gmail_agent_address = "agent1qv8wv3yq3l9ph60fnlmly3l3ms3w77yzv9z0hmxjdmu54tr6xwa4gk7uk5w" 
        email_request = EmailRequest(msg=format_assignments(assignments_by_window))
        response = await ctx.send(gmail_agent_address, email_request)
        

    ctx.logger.info(format_assignments(assignments_by_window))

def format_assignments(assignments_by_window):
    if not any(assignments_by_window.values()):
        return "No assignments due in the next 120 hours in your starred courses!"
    
    formatted_output = "Upcoming Assignments:\n\n"
    
    # Format 6-hour window assignments
    if assignments_by_window['6h']:
        formatted_output += "Due in the next 6 hours:\n"
        for assignment in assignments_by_window['6h']:
            notification_cache.mark_as_sent(assignment['id'], '6h')
            formatted_output += f"Course: {assignment['course']}\n"
            formatted_output += f"Assignment: {assignment['assignment']}\n"
            formatted_output += f"Due: {assignment['due_time']}\n\n"
    
    # Format 12-hour window assignments
    if assignments_by_window['12h']:
        formatted_output += "Due in 6-12 hours:\n"
        for assignment in assignments_by_window['12h']:
            notification_cache.mark_as_sent(assignment['id'], '12h')
            formatted_output += f"Course: {assignment['course']}\n"
            formatted_output += f"Assignment: {assignment['assignment']}\n"
            formatted_output += f"Due: {assignment['due_time']}\n\n"
    
    # Format 120-hour window assignments
    if assignments_by_window['72h']:
        formatted_output += "Due in 12-120 hours:\n"
        for assignment in assignments_by_window['72h']:
            notification_cache.mark_as_sent(assignment['id'], '72h')
            formatted_output += f"Course: {assignment['course']}\n"
            formatted_output += f"Assignment: {assignment['assignment']}\n"
            formatted_output += f"Due: {assignment['due_time']}\n\n"
    
    return formatted_output.rstrip()


if __name__ == "__main__":
    agent.run()
