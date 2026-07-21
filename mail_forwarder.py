import imaplib
import poplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
import time
import traceback
import re
import os
import json

# ==================== Configuration Section ====================
# Email account list (Supports multiple accounts, e.g., Gmail, Outlook, etc.)
MAIL_ACCOUNTS = [
    {
        "user": "your_account@example.com",          # Your Email address
        "password": "your_password_or_app_password", # Your password or app password
        "protocol": "imap",                          # Receive protocol: "imap" or "pop3"
        "mail_receive_server": "imap.example.com",   # Manually specify receive mail server
        "smtp_server": "smtp.example.com",           # Manually specify SMTP server
        # "use_username_only": False,                 # Optional. If True, logs in using only the local-part before @
        # "mail_receive_port": 993,                   # Optional. Manually specify receive port (default IMAP: 993, POP3: 995)
        # "smtp_port": 465,                           # Optional. Manually specify SMTP port (default 465, supports 587 STARTTLS)
        # "trash_folder": "Trash"                     # Optional. Folder to move forwarded messages to in IMAP mode (default "Trash")
    },
]

# Recipient list to forward emails to (Supports multiple target mailboxes)
FORWARD_TO = [
    "target@example.com"
]
# ===============================================================

# Read environment variables (GitHub Secrets) as configuration first
env_accounts = os.environ.get("MAIL_ACCOUNTS")
if env_accounts:
    try:
        MAIL_ACCOUNTS = json.loads(env_accounts)
        print("ℹ️ Successfully loaded MAIL_ACCOUNTS environment variable")
    except Exception as e:
        print(f"⚠️ Failed to parse accounts environment variable: {type(e).__name__}, falling back to code settings")

env_forward_to = os.environ.get("FORWARD_TO")
if env_forward_to:
    try:
        # Supports JSON arrays (e.g. ["a@b.com"]) and comma-separated lists (e.g. "a@b.com,b@c.com")
        stripped_val = env_forward_to.strip()
        if stripped_val.startswith("["):
            FORWARD_TO = json.loads(stripped_val)
        else:
            FORWARD_TO = [email.strip() for email in stripped_val.split(",") if email.strip()]
        print("ℹ️ Successfully loaded FORWARD_TO environment variable")
    except Exception as e:
        print(f"⚠️ Failed to parse FORWARD_TO environment variable: {type(e).__name__}, falling back to code settings")


def get_account_settings(account):
    """Retrieve mail server configurations for an account"""
    user = account.get("user", "")
    protocol = account.get("protocol", "").lower().strip()
    
    use_username_only = account.get("use_username_only", False)
    mail_receive_server = account.get("mail_receive_server")
    mail_receive_port = account.get("mail_receive_port")
    smtp_server = account.get("smtp_server")
    smtp_port = account.get("smtp_port")
    trash_folder = account.get("trash_folder", "Trash")

    # Fallback default ports if not specified
    if not mail_receive_port:
        mail_receive_port = 995 if protocol == "pop3" else 993
        
    if not smtp_port:
        smtp_port = 465  # Default to SSL port

    return {
        "user": user,
        "password": account.get("password", ""),
        "protocol": protocol,
        "use_username_only": bool(use_username_only),
        "mail_receive_server": mail_receive_server,
        "mail_receive_port": int(mail_receive_port),
        "smtp_server": smtp_server,
        "smtp_port": int(smtp_port),
        "trash_folder": trash_folder
    }


def decode_str(header_val):
    """Decode header or sender strings, handling different character sets"""
    if not header_val:
        return ""
    decoded_list = decode_header(header_val)
    header_str = ""
    for text, charset in decoded_list:
        if isinstance(text, bytes):
            if charset:
                header_str += text.decode(charset, errors="ignore")
            else:
                header_str += text.decode("utf-8", errors="ignore")
        else:
            header_str += text
    return header_str


def mask_email(email_str):
    """Mask the local-part of an email address for privacy (e.g. abcde@example.com -> ab***@example.com)"""
    if not email_str:
        return ""
    if "@" in email_str:
        user, domain = email_str.split("@", 1)
        if len(user) <= 2:
            return user + "***" + "@" + domain
        return user[:2] + "***" + user[-1] + "@" + domain
    else:
        if len(email_str) <= 2:
            return email_str + "***"
        return email_str[:2] + "***" + email_str[-1]


def mask_subject(subject_str):
    """Mask the email subject, showing only the first two characters for identification"""
    if not subject_str:
        return "(No Subject)"
    if len(subject_str) <= 2:
        return "**"
    return subject_str[:2] + "..."


def forward_email(raw_email, account_settings):
    """Forward the raw email to the target recipient list (preserves attachments and HTML formatting)"""
    msg = email.message_from_bytes(raw_email)

    subject = decode_str(msg.get("Subject"))
    sender = decode_str(msg.get("From"))

    user = account_settings["user"]
    password = account_settings["password"]
    smtp_server = account_settings["smtp_server"]
    smtp_port = account_settings["smtp_port"]
    use_username_only = account_settings["use_username_only"]

    # Create a multipart/mixed message container for attachments and body
    forward_msg = MIMEMultipart("mixed")
    forward_msg["From"] = user
    forward_msg["To"] = ", ".join(FORWARD_TO)
    forward_msg["Subject"] = f"[Fwd] {subject}"

    # Create a multipart/alternative container to support both plain text and HTML
    body_container = MIMEMultipart("alternative")
    
    text_body = ""
    html_body = ""
    text_charset = "utf-8"
    html_charset = "utf-8"

    # Information info block prepended to the HTML body
    html_header_info = (
        f"<div style='background-color: #f5f5f5; border-left: 4px solid #002752; padding: 10px; margin-bottom: 20px; font-family: sans-serif; color: #333;'>"
        f"<strong>--- Automatically Forwarded Message ---</strong><br/>"
        f"<strong>Original Sender:</strong> {sender}<br/>"
        f"<strong>Original Subject:</strong> {subject}<br/>"
        f"</div>"
    )

    # Information info block prepended to the plain text body
    text_header_info = (
        f"--- Automatically Forwarded Message ---\n"
        f"Original Sender: {sender}\n"
        f"Original Subject: {subject}\n"
        f"---------------------\n\n"
    )

    if msg.is_multipart():
        for part in msg.walk():
            # Skip container parts, process leaf nodes only
            if part.is_multipart():
                continue

            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if content_type == "text/plain" and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    text_charset = charset
                    text_body += payload.decode(charset, errors="ignore")
            elif content_type == "text/html" and "attachment" not in content_disposition:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_charset = charset
                    html_body += payload.decode(charset, errors="ignore")
            else:
                # Attachments, inline images, or other media are attached directly to root (mixed) container
                forward_msg.attach(part)
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            if content_type == "text/html":
                html_charset = charset
                html_body = payload.decode(charset, errors="ignore")
            else:
                text_charset = charset
                text_body = payload.decode(charset, errors="ignore")

    # Assemble and attach plain text / HTML bodies to alternative container
    if text_body:
        formatted_text = text_header_info + text_body
        body_container.attach(MIMEText(formatted_text, "plain", text_charset))
    
    if html_body:
        formatted_html = html_header_info + html_body
        body_container.attach(MIMEText(formatted_html, "html", html_charset))
    elif text_body:
        # If only plain text is present, wrap it in a simple HTML body for compatibility
        simple_html = text_body.replace("\n", "<br/>")
        formatted_html = html_header_info + f"<div>{simple_html}</div>"
        body_container.attach(MIMEText(formatted_html, "html", "utf-8"))

    # If there is any text or HTML content, attach the alternative container to the root
    if text_body or html_body:
        forward_msg.attach(body_container)

    # Determine the username used for SMTP login
    login_user = user.split("@")[0] if use_username_only else user

    # Send the forwarded message (Supports SSL and STARTTLS)
    if smtp_port == 465:
        smtp_client = smtplib.SMTP_SSL(smtp_server, smtp_port)
    else:
        smtp_client = smtplib.SMTP(smtp_server, smtp_port)
        smtp_client.starttls()

    with smtp_client as smtp:
        smtp.login(login_user, password)
        smtp.send_message(forward_msg)
        print(f"✅ [{mask_email(user)}] Successfully forwarded email: {mask_subject(subject)}")


def check_and_forward_account(account_settings):
    """Check unread emails for a single account and forward them (supports POP3 and IMAP)"""
    user = account_settings["user"]
    password = account_settings["password"]
    mail_receive_server = account_settings["mail_receive_server"]
    mail_receive_port = account_settings["mail_receive_port"]
    protocol = account_settings["protocol"]
    use_username_only = account_settings["use_username_only"]
    trash_folder = account_settings["trash_folder"]

    login_user = user.split("@")[0] if use_username_only else user

    if not mail_receive_server:
        print(f"❌ [{mask_email(user)}] No receive mail server specified, skipping this account")
        return

    if not account_settings.get("smtp_server"):
        print(f"❌ [{mask_email(user)}] No SMTP server specified, skipping this account")
        return

    if protocol == "pop3":
        try:
            mail = poplib.POP3_SSL(mail_receive_server, mail_receive_port)
            mail.user(login_user)
            mail.pass_(password)
            
            num_messages, _ = mail.stat()
            if num_messages == 0:
                print(f"ℹ️ [{mask_email(user)}] No new/unread emails found")
                mail.quit()
                return

            print(f"📩 [{mask_email(user)}] Received {num_messages} unread email(s), processing...")

            for i in range(1, num_messages + 1):
                # 1. Retrieve raw email content
                _, lines, _ = mail.retr(i)
                raw_email = b"\n".join(lines)

                # 2. Forward the email
                forward_email(raw_email, account_settings)

                # 3. Mark the email for deletion
                mail.dele(i)
                print(f"🗑️ [{mask_email(user)}] Marked email {i} for deletion")

            # 4. Logout and commit deletions
            mail.quit()
            print(f"✅ [{mask_email(user)}] POP3 processing complete. Logged out.")

        except Exception as e:
            print(f"❌ [{mask_email(user)}] POP3 error: {e}")
            traceback.print_exc()
    else:
        try:
            mail = imaplib.IMAP4_SSL(mail_receive_server, mail_receive_port)
            mail.login(login_user, password)
            mail.select("INBOX")

            status, messages = mail.search(None, "UNSEEN")
            if status != "OK":
                print(f"⚠️ [{mask_email(user)}] Failed to select INBOX")
                return

            mail_ids = messages[0].split()
            if not mail_ids:
                print(f"ℹ️ [{mask_email(user)}] No new/unread emails found")
                return

            print(f"📩 [{mask_email(user)}] Received {len(mail_ids)} unread email(s), processing...")

            for mail_id in mail_ids:
                # 1. Retrieve raw email content
                _, data = mail.fetch(mail_id, "(RFC822)")
                raw_email = data[0][1]

                # 2. Forward the email
                forward_email(raw_email, account_settings)

                # 3. Copy the email to the trash folder (supports custom trash folders)
                result = mail.copy(mail_id, trash_folder)
                
                if result[0] == "OK":
                    # 4. Once copied, mark the original email as deleted
                    mail.store(mail_id, "+FLAGS", "\\Deleted")
                    print(f"🗑️ [{mask_email(user)}] Moved email ID {mail_id.decode()} to trash ({trash_folder})")
                else:
                    print(f"⚠️ [{mask_email(user)}] Failed to move to trash ({trash_folder}), marking as read only")
                    mail.store(mail_id, "+FLAGS", "\\Seen")

            # 5. Expunge to permanently delete all messages marked as \Deleted
            mail.expunge()
            mail.logout()

        except Exception as e:
            print(f"❌ [{mask_email(user)}] IMAP error: {e}")
            traceback.print_exc()


def check_and_forward_all():
    """Check and forward emails for all configured mail accounts"""
    accounts = globals().get("MAIL_ACCOUNTS") or []
    if not accounts:
        print("⚠️ No email accounts configured")
        return
    if not FORWARD_TO:
        print("⚠️ No forward recipients configured")
        return

    for account in accounts:
        user = account.get("user")
        password = account.get("password")
        if not user or not password:
            print("⚠️ Account configuration incomplete, skipping this account")
            continue
        
        protocol = account.get("protocol", "").lower().strip()
        if not protocol:
            print(f"⚠️ [{mask_email(user)}] Receive protocol not configured (protocol is required), skipping this account")
            continue
        
        # Resolve complete settings for the account
        account_settings = get_account_settings(account)
        check_and_forward_account(account_settings)


if __name__ == "__main__":
    # Perform a check; schedule with cron or run in a loop with time.sleep for periodic execution
    check_and_forward_all()