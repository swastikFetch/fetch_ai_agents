from uagents import Agent, Context, Model
from uagents.setup import fund_agent_if_low
import os 
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import base64
from dotenv import load_dotenv
load_dotenv()

agent = Agent(name="Gmail", 
              port=8001, 
              endpoint=["http://localhost:8001/submit"])
fund_agent_if_low(agent.wallet.address())
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

class EmailRequest(Model):
    msg: str

def get_gmail_service():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If credentials are not valid or don't exist, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('gmail', 'v1', credentials=creds)

def send_email_notification(message):
    try:
        service = get_gmail_service()
        
        # Create the email message
        email_msg = MIMEText(message)
        email_msg['to'] = os.getenv("EMAIL_RECEIVER")
        email_msg['subject'] = "Canvas Assignments Due Tomorrow"
        
        # Encode the message
        raw_msg = base64.urlsafe_b64encode(email_msg.as_bytes()).decode('utf-8')
        
        # Send the email
        try:
            message = service.users().messages().send(
                userId='me', 
                body={'raw': raw_msg}
            ).execute()
            print(f"Email sent successfully. Message Id: {message['id']}")
            return True
        except Exception as e:
            print(f"An error occurred while sending the email: {e}")
            return False
            
    except Exception as e:
        print(f"Error in email service: {e}")
        return False
    
@agent.on_event("startup")
async def introduce_agent(ctx: Context):
    ctx.logger.info(f"Hello, I'm agent {agent.name} and my address is {agent.address}.")

@agent.on_query(model=EmailRequest)
async def handle_email_request(ctx: Context, sender: str, request: EmailRequest):
    if send_email_notification(request.msg):
        ctx.logger.info(f"Email sent successfully.")
    else:
        ctx.logger.info(f"Failed to send email.")
    ctx.logger.info(f"Received email request: {request}")

if __name__ == "__main__":
    agent.run()