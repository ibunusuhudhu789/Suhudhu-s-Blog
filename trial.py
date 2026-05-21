import sendgrid
from sendgrid.helpers.mail import Mail


sendgrid = sendgrid.SendGridAPIClient(api_key="")

mail = Mail(from_email="suhudhuthewriter@gmail.com", to_emails="suhudhuthewriter@gmail.com", subject="Trial message",
            plain_text_content="This is just the trial message.")
sendgrid.send(mail)
