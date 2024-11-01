from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from flask import render_template
import os

class EmailService:
    def __init__(self):
        self.client = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        self.from_email = os.getenv('FROM_EMAIL')

    def send_confirmation_email(self, to_email):
        html_content = render_template('subscription_confirmation.html')
        message = Mail(
            from_email=self.from_email,
            to_emails=to_email,
            subject='Subscription Confirmed - Event Updates',
            html_content=html_content
        )
        response = self.client.send(message)
        return response.status_code

    def send_weekly_update(self, subscriber, events):
        html_content = render_template('email_template.html',
                                       events=events,
                                       email=subscriber.email)
        message = Mail(
            from_email=self.from_email,
            to_emails=subscriber.email,
            subject='Weekly Event Update',
            html_content=html_content
        )
        response = self.client.send(message)
        return response.status_code