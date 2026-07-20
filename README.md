# NTU Mail Forwarder

A robust, lightweight Python tool designed to monitor multiple National Taiwan University (NTU) email mailboxes and forward incoming emails to multiple target mailboxes. It fully preserves email rich text formatting (HTML) and attachments.

## Features

- **Multi-Account Support**: Check multiple NTU email accounts concurrently.
- **Multi-Recipient Forwarding**: Forward emails to one or more destination email addresses.
- **Dual-Protocol Support**: Supports both **POP3** and **IMAP** protocols, automatically switching protocols based on the configured ports or settings.
- **Rich Mail Content Preservation**: Reconstructs email payloads into `multipart/mixed` and `multipart/alternative` structures to keep original HTML formatting, inline images, and file attachments (e.g., PDFs, spreadsheets, documents) intact.
- **GitHub Actions Automation**: Built-in workflow template to run the forwarder automatically on a daily schedule (or manually) using GitHub Actions.
- **Secret Integration**: Supports reading credentials securely from environment variables / GitHub Secrets as high-priority inputs, falling back to in-code settings if not present.

---

## Configuration (`mail_forwarder.py`)

You can configure the tool directly in the configuration section of `mail_forwarder.py` for local testing:

```python
NTU_ACCOUNTS = [
    {
        "user": "your_account@ntu.edu.tw",
        "password": "your_password_or_app_password",
        "server_type": "ccms",  # "msa" for staff, "ccms" for student/alumni/hospital accounts
        "protocol": "pop3",     # "pop3" or "imap" (Mandatory)
        # "mail_receive_server": "ccms.ntu.edu.tw", # Optional override
        # "mail_receive_port": 995                 # Optional override (default: POP3=995, IMAP=993)
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
   - **`NTU_ACCOUNTS`**: A JSON string containing the account list. E.g.:
     ```json
     [
       {
         "user": "your_account@ntu.edu.tw",
         "password": "your_secret_password",
         "server_type": "ccms",
         "protocol": "pop3"
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
