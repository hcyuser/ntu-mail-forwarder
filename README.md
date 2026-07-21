# General Mail Forwarder

A robust, lightweight Python tool designed to monitor multiple email mailboxes (e.g., Gmail, Outlook, Yahoo, or custom domain mailboxes) and forward incoming emails to multiple target mailboxes. It fully preserves email rich text formatting (HTML), inline images, and attachments.

## Features

- **Multi-Account Support**: Check multiple email accounts concurrently (even from different providers).
- **Multi-Recipient Forwarding**: Forward emails to one or more destination email addresses.
- **Dual-Protocol Support**: Supports both **POP3** and **IMAP** protocols.
- **Rich Mail Content Preservation**: Reconstructs email payloads into `multipart/mixed` and `multipart/alternative` structures to keep original HTML formatting and file attachments intact.
- **GitHub Actions Automation**: Built-in workflow template to run the forwarder automatically on a daily schedule (or manually) using GitHub Actions.
- **Secret Integration**: Supports reading credentials securely from environment variables / GitHub Secrets as high-priority inputs.

---

## Configuration (`mail_forwarder.py`)

You can configure the tool directly in the configuration section of `mail_forwarder.py` for local testing. All mail accounts require explicit mail server settings:

```python
MAIL_ACCOUNTS = [
    # Example 1: Gmail (IMAP)
    {
        "user": "your_account@gmail.com",
        "password": "your_gmail_app_password", # Gmail requires an App Password
        "protocol": "imap",
        "mail_receive_server": "imap.gmail.com",
        "mail_receive_port": 993,
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 465
    },
    # Example 2: Outlook / Hotmail (IMAP)
    {
        "user": "your_account@outlook.com",
        "password": "your_outlook_app_password",
        "protocol": "imap",
        "mail_receive_server": "outlook.office365.com",
        "mail_receive_port": 993,
        "smtp_server": "smtp.office365.com",
        "smtp_port": 587 # Outlook uses STARTTLS 587
    },
    # Example 3: Custom mail server
    {
        "user": "user@customdomain.com",
        "password": "your_password",
        "protocol": "imap",
        "mail_receive_server": "imap.customdomain.com",
        "mail_receive_port": 993,
        "smtp_server": "smtp.customdomain.com",
        "smtp_port": 465, # Can be 465 (SSL) or 587 (STARTTLS)
        "trash_folder": "Trash"
    }
]

FORWARD_TO = [
    "target1@gmail.com",
    "target2@gmail.com"
]
```

---

## Deployment via GitHub Actions

To automate this script to run daily (default: UTC 03:00 / Taiwan 11:00) without running a local server:

1. Push this project to your private GitHub repository.
2. Go to your repository settings: **Settings** -> **Secrets and variables** -> **Actions**.
3. Create the following two **Repository Secrets**:
   - **`MAIL_ACCOUNTS`**: A JSON string containing the account list. E.g.:
     ```json
     [
       {
         "user": "your_account@gmail.com",
         "password": "your_gmail_app_password",
         "protocol": "imap",
         "mail_receive_server": "imap.gmail.com",
         "mail_receive_port": 993,
         "smtp_server": "smtp.gmail.com",
         "smtp_port": 465
       }
     ]
     ```
   - **`FORWARD_TO`**: The target email addresses, formatted as a JSON array (e.g., `["target1@gmail.com", "target2@gmail.com"]`) or a comma-separated list (e.g., `target1@gmail.com, target2@gmail.com`).
4. The workflow in `.github/workflows/mail_forwarder.yml` will automatically trigger according to the cron schedule. You can also trigger it manually from the **Actions** tab on GitHub.

---

## Local Usage

Run the script using Python 3:

```bash
python3 mail_forwarder.py
```
