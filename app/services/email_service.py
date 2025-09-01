"""
Email Service - SendGrid Integration for MyTypist
Handles all email communications including verification, password reset, and notifications
"""

import os
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
from jinja2 import Template
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition
import base64

from config import settings

logger = logging.getLogger(__name__)

class EmailService:
    """Comprehensive email service with SendGrid integration"""
    
    def __init__(self):
        self.client = None
        self.from_email = settings.SENDGRID_FROM_EMAIL
        self.company_name = "MyTypist"
        
        if hasattr(settings, 'SENDGRID_API_KEY') and settings.SENDGRID_API_KEY:
            try:
                self.client = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
            except Exception as e:
                logger.warning(f"SendGrid client initialization failed: {e}")
    
    async def send_email(
        self,
        to_emails: List[str],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
        template_data: Optional[Dict[str, Any]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Send email using SendGrid"""
        
        if not self.client:
            logger.error("SendGrid client not initialized - email not sent")
            return False
        
        try:
            # Process template data if provided
            if template_data:
                html_template = Template(html_content)
                html_content = html_template.render(**template_data)
                
                if text_content:
                    text_template = Template(text_content)
                    text_content = text_template.render(**template_data)
            
            # Create email
            mail = Mail(
                from_email=Email(self.from_email, self.company_name),
                to_emails=[To(email) for email in to_emails],
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            if text_content:
                mail.content.append(Content("text/plain", text_content))
            
            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    encoded = base64.b64encode(attachment['content']).decode()
                    attached_file = Attachment(
                        FileContent(encoded),
                        FileName(attachment['filename']),
                        FileType(attachment.get('type', 'application/octet-stream')),
                        Disposition('attachment')
                    )
                    mail.attachment.append(attached_file)
            
            # Send email
            response = self.client.send(mail)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent successfully to {to_emails}")
                return True
            else:
                logger.error(f"Email sending failed with status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            return False
    
    async def send_welcome_email(self, user_email: str, user_name: str, verification_token: str) -> bool:
        """Send welcome email with verification link"""
        
        verification_link = f"{settings.FRONTEND_URL}/verify-email?token={verification_token}"
        
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Welcome to MyTypist</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: #2563eb; color: white; padding: 20px; text-align: center; }
                .content { padding: 30px 20px; }
                .button { display: inline-block; padding: 12px 24px; background: #2563eb; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
                .footer { background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to MyTypist!</h1>
                </div>
                <div class="content">
                    <h2>Hi {{ user_name }},</h2>
                    <p>Thank you for joining MyTypist, Nigeria's leading document automation platform. We're excited to help you streamline your document creation process.</p>
                    
                    <p>To get started, please verify your email address by clicking the button below:</p>
                    
                    <div style="text-align: center;">
                        <a href="{{ verification_link }}" class="button">Verify Email Address</a>
                    </div>
                    
                    <p>Once verified, you can:</p>
                    <ul>
                        <li>Create and manage document templates</li>
                        <li>Generate professional documents in seconds</li>
                        <li>Use digital signatures</li>
                        <li>Access our template marketplace</li>
                    </ul>
                    
                    <p>If you have any questions, our support team is here to help at support@mytypist.com</p>
                    
                    <p>Best regards,<br>The MyTypist Team</p>
                </div>
                <div class="footer">
                    <p>© 2025 MyTypist. All rights reserved.<br>
                    If you didn't create this account, please ignore this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        text_content = """
        Welcome to MyTypist!
        
        Hi {{ user_name }},
        
        Thank you for joining MyTypist, Nigeria's leading document automation platform.
        
        Please verify your email address by visiting: {{ verification_link }}
        
        Once verified, you can create templates, generate documents, and much more.
        
        If you have questions, contact us at support@mytypist.com
        
        Best regards,
        The MyTypist Team
        """
        
        return await self.send_email(
            to_emails=[user_email],
            subject="Welcome to MyTypist - Please verify your email",
            html_content=html_content,
            text_content=text_content,
            template_data={
                "user_name": user_name,
                "verification_link": verification_link
            }
        )
    
    async def send_password_reset_email(self, user_email: str, user_name: str, reset_token: str) -> bool:
        """Send password reset email"""
        
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Reset Your MyTypist Password</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: #dc2626; color: white; padding: 20px; text-align: center; }
                .content { padding: 30px 20px; }
                .button { display: inline-block; padding: 12px 24px; background: #dc2626; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
                .footer { background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #666; }
                .warning { background: #fef2f2; border: 1px solid #fecaca; padding: 15px; border-radius: 5px; margin: 20px 0; color: #dc2626; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Reset Request</h1>
                </div>
                <div class="content">
                    <h2>Hi {{ user_name }},</h2>
                    <p>We received a request to reset your MyTypist password. If you made this request, click the button below to reset your password:</p>
                    
                    <div style="text-align: center;">
                        <a href="{{ reset_link }}" class="button">Reset Password</a>
                    </div>
                    
                    <div class="warning">
                        <strong>Important:</strong> This link will expire in 1 hour for security reasons.
                    </div>
                    
                    <p>If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.</p>
                    
                    <p>For security reasons, never share this link with anyone. If you're having trouble, contact our support team at support@mytypist.com</p>
                    
                    <p>Best regards,<br>The MyTypist Security Team</p>
                </div>
                <div class="footer">
                    <p>© 2025 MyTypist. All rights reserved.<br>
                    This is an automated security notification.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(
            to_emails=[user_email],
            subject="Reset Your MyTypist Password",
            html_content=html_content,
            template_data={
                "user_name": user_name,
                "reset_link": reset_link
            }
        )
    
    async def send_document_ready_notification(
        self, 
        user_email: str, 
        user_name: str, 
        document_title: str,
        download_url: str
    ) -> bool:
        """Send notification when document generation is complete"""
        
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Your Document is Ready</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: #16a34a; color: white; padding: 20px; text-align: center; }
                .content { padding: 30px 20px; }
                .button { display: inline-block; padding: 12px 24px; background: #16a34a; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
                .footer { background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✅ Document Ready!</h1>
                </div>
                <div class="content">
                    <h2>Hi {{ user_name }},</h2>
                    <p>Great news! Your document "<strong>{{ document_title }}</strong>" has been generated successfully and is ready for download.</p>
                    
                    <div style="text-align: center;">
                        <a href="{{ download_url }}" class="button">Download Document</a>
                    </div>
                    
                    <p>Your document will be available for download for the next 30 days. After that, it will be automatically archived for security.</p>
                    
                    <p>Need to create more documents? <a href="{{ frontend_url }}">Log in to your MyTypist account</a> to get started.</p>
                    
                    <p>Best regards,<br>The MyTypist Team</p>
                </div>
                <div class="footer">
                    <p>© 2025 MyTypist. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(
            to_emails=[user_email],
            subject=f"Your document '{document_title}' is ready",
            html_content=html_content,
            template_data={
                "user_name": user_name,
                "document_title": document_title,
                "download_url": download_url,
                "frontend_url": settings.FRONTEND_URL
            }
        )
    
    async def send_feedback_acknowledgment(
        self, 
        user_email: str, 
        user_name: str, 
        feedback_id: str
    ) -> bool:
        """Send acknowledgment email for submitted feedback"""
        
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Thank You for Your Feedback</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: #7c3aed; color: white; padding: 20px; text-align: center; }
                .content { padding: 30px 20px; }
                .footer { background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #666; }
                .feedback-id { background: #f3f4f6; padding: 10px; border-radius: 5px; font-family: monospace; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Thank You for Your Feedback!</h1>
                </div>
                <div class="content">
                    <h2>Hi {{ user_name }},</h2>
                    <p>Thank you for taking the time to share your feedback with us. Your input is invaluable in helping us improve MyTypist for all our users.</p>
                    
                    <p>Your feedback has been received and assigned the following reference ID:</p>
                    <div class="feedback-id">{{ feedback_id }}</div>
                    
                    <p>Our team will review your feedback within 1-2 business days. If you included a specific question or request that requires a response, we'll get back to you as soon as possible.</p>
                    
                    <p>In the meantime, feel free to continue using MyTypist to create amazing documents. If you need immediate assistance, you can reach us at support@mytypist.com</p>
                    
                    <p>Best regards,<br>The MyTypist Team</p>
                </div>
                <div class="footer">
                    <p>© 2025 MyTypist. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(
            to_emails=[user_email],
            subject="Thank you for your feedback - MyTypist",
            html_content=html_content,
            template_data={
                "user_name": user_name,
                "feedback_id": feedback_id
            }
        )
    
    async def send_subscription_confirmation(
        self,
        user_email: str,
        user_name: str, 
        plan_name: str,
        amount: float,
        billing_cycle: str,
        next_billing_date: str
    ) -> bool:
        """Send subscription confirmation email"""
        
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Subscription Confirmed - MyTypist</title>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: #059669; color: white; padding: 20px; text-align: center; }
                .content { padding: 30px 20px; }
                .plan-details { background: #f0fdf4; border: 1px solid #bbf7d0; padding: 20px; border-radius: 8px; margin: 20px 0; }
                .footer { background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Subscription Confirmed!</h1>
                </div>
                <div class="content">
                    <h2>Hi {{ user_name }},</h2>
                    <p>Welcome to the MyTypist family! Your subscription has been successfully activated.</p>
                    
                    <div class="plan-details">
                        <h3>Your Plan Details:</h3>
                        <ul>
                            <li><strong>Plan:</strong> {{ plan_name }}</li>
                            <li><strong>Amount:</strong> ₦{{ amount }} / {{ billing_cycle }}</li>
                            <li><strong>Next Billing:</strong> {{ next_billing_date }}</li>
                        </ul>
                    </div>
                    
                    <p>You now have access to all premium features including unlimited document generation, premium templates, priority support, and much more.</p>
                    
                    <p>Start creating professional documents today by logging into your account at <a href="{{ frontend_url }}">mytypist.com</a></p>
                    
                    <p>If you have any questions about your subscription, feel free to contact us at billing@mytypist.com</p>
                    
                    <p>Best regards,<br>The MyTypist Team</p>
                </div>
                <div class="footer">
                    <p>© 2025 MyTypist. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return await self.send_email(
            to_emails=[user_email],
            subject=f"Subscription Confirmed - {plan_name} Plan",
            html_content=html_content,
            template_data={
                "user_name": user_name,
                "plan_name": plan_name,
                "amount": amount,
                "billing_cycle": billing_cycle,
                "next_billing_date": next_billing_date,
                "frontend_url": settings.FRONTEND_URL
            }
        )

# Global email service instance
email_service = EmailService()