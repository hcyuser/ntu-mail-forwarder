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

# ==================== 設定區塊 ====================
# 台大信箱帳號清單 (支援多組帳號)
NTU_ACCOUNTS = [
    {
        "user": "XXX@ntu.edu.tw",      # 你的台大帳號
        "password": "XXX",         # 你的台大密碼/應用程式密碼
        "server_type": "ccms",             # 伺服器類型：可填 "msa" (教職員) 或 "ccms" (學生/校友/醫院帳號)
        "protocol": "pop3",                # 收信協定：必填 "pop3" 或 "imap"
        # "mail_receive_server": "ccms.ntu.edu.tw",  # 可選，手動指定收信伺服器主機名稱 (優先度最高)
        # "mail_receive_port": 995                   # 可選，手動指定收信連接埠 (預設為 pop3: 995, imap: 993)
    },
]

# 接收轉發信件的目標 Email 清單 (支援多個目標信箱)
FORWARD_TO = [
    "target@example.com"
]

SMTP_SERVER = "smtps.ntu.edu.tw"
SMTP_PORT = 465                         # SMTP via SSL
# ==================================================

# 優先讀取環境變數 (GitHub Secrets) 作為設定值
env_accounts = os.environ.get("NTU_ACCOUNTS")
if env_accounts:
    try:
        NTU_ACCOUNTS = json.loads(env_accounts)
        print("ℹ️ 已成功載入 NTU_ACCOUNTS 環境變數")
    except Exception as e:
        print(f"⚠️ 解析 NTU_ACCOUNTS 環境變數失敗: {e}，將使用程式碼內設定")

env_forward_to = os.environ.get("FORWARD_TO")
if env_forward_to:
    try:
        # 支援 JSON 陣列 (例如 ["a@b.com"]) 與逗號分隔字串 (例如 "a@b.com,b@c.com")
        stripped_val = env_forward_to.strip()
        if stripped_val.startswith("["):
            FORWARD_TO = json.loads(stripped_val)
        else:
            FORWARD_TO = [email.strip() for email in stripped_val.split(",") if email.strip()]
        print("ℹ️ 已成功載入 FORWARD_TO 環境變數")
    except Exception as e:
        print(f"⚠️ 解析 FORWARD_TO 環境變數失敗: {e}，將使用程式碼內設定")


def get_mail_receive_server(account):
    """根據帳號設定或名稱自動取得/偵測對應的台大收信伺服器"""
    # 優先檢查是否有設定 server_type
    server_type = account.get("server_type", "").lower().strip()
    if server_type == "msa":
        return "msa.ntu.edu.tw"
    elif server_type == "ccms":
        return "ccms.ntu.edu.tw"



def decode_str(header_val):
    """解析標題或寄件者字串，處理不同編碼格式"""
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


def forward_email(raw_email, ntu_user, ntu_password):
    """將收到的原始郵件轉發至目標信箱清單 (支援附件與 HTML 格式)"""
    msg = email.message_from_bytes(raw_email)

    subject = decode_str(msg.get("Subject"))
    sender = decode_str(msg.get("From"))

    # 建立轉發郵件物件 (使用 mixed 容器以包含附件與內文)
    forward_msg = MIMEMultipart("mixed")
    forward_msg["From"] = ntu_user
    forward_msg["To"] = ", ".join(FORWARD_TO)
    forward_msg["Subject"] = f"[Fwd] {subject}"

    # 建立內文容器 (使用 alternative 容器以同時支援純文字與 HTML 格式)
    body_container = MIMEMultipart("alternative")
    
    text_body = ""
    html_body = ""
    text_charset = "utf-8"
    html_charset = "utf-8"

    # 用於在 HTML 最前面插入的資訊
    html_header_info = (
        f"<div style='background-color: #f5f5f5; border-left: 4px solid #002752; padding: 10px; margin-bottom: 20px; font-family: sans-serif; color: #333;'>"
        f"<strong>--- 自動轉發訊息 ---</strong><br/>"
        f"<strong>原始寄件者:</strong> {sender}<br/>"
        f"<strong>原始主題:</strong> {subject}<br/>"
        f"</div>"
    )

    # 用於在純文字最前面插入的資訊
    text_header_info = (
        f"--- 自動轉發訊息 ---\n"
        f"原始寄件者: {sender}\n"
        f"原始主題: {subject}\n"
        f"---------------------\n\n"
    )

    if msg.is_multipart():
        for part in msg.walk():
            # 忽略容器本身，只處理葉子節點
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
                # 附件、圖片、其他媒體等，直接附加至 root (mixed) 容器
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

    # 將內文與 HTML 組裝並附加至 body_container
    if text_body:
        formatted_text = text_header_info + text_body
        body_container.attach(MIMEText(formatted_text, "plain", text_charset))
    
    if html_body:
        formatted_html = html_header_info + html_body
        body_container.attach(MIMEText(formatted_html, "html", html_charset))
    elif text_body:
        # 若只有文字，自動封裝成簡單 HTML 作為備援對稱
        simple_html = text_body.replace("\n", "<br/>")
        formatted_html = html_header_info + f"<div>{simple_html}</div>"
        body_container.attach(MIMEText(formatted_html, "html", "utf-8"))

    # 如果有任何內文，將內文容器附加至 root (mixed) 郵件物件
    if text_body or html_body:
        forward_msg.attach(body_container)

    # 送出轉發信件
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
        username = ntu_user.split("@")[0]
        smtp.login(username, ntu_password)
        smtp.send_message(forward_msg)
        print(f"✅ [{ntu_user}] 已成功轉發信件: {subject}")


def check_and_forward_account(ntu_user, ntu_password, mail_receive_server, mail_receive_port, protocol=None):
    """檢查單一台大信箱帳號的未讀信件並轉發 (支援 POP3 與 IMAP)"""
    
    if protocol == "pop3":
        try:
            mail = poplib.POP3_SSL(mail_receive_server, mail_receive_port)
            username = ntu_user.split("@")[0]
            mail.user(username)
            mail.pass_(ntu_password)
            
            num_messages, _ = mail.stat()
            if num_messages == 0:
                print(f"ℹ️ [{ntu_user}] 目前沒有未讀新信件")
                mail.quit()
                return

            print(f"📩 [{ntu_user}] 收到 {num_messages} 封未讀信件，準備處理...")

            for i in range(1, num_messages + 1):
                # 1. 取得整封信件內容
                _, lines, _ = mail.retr(i)
                raw_email = b"\n".join(lines)

                # 2. 進行轉發
                forward_email(raw_email, ntu_user, ntu_password)

                # 3. 標記刪除
                mail.dele(i)
                print(f"🗑️ [{ntu_user}] 已標記信件 {i} 為刪除")

            # 4. 登出並執行刪除
            mail.quit()
            print(f"✅ [{ntu_user}] POP3 處理完成並登出")

        except Exception as e:
            print(f"❌ [{ntu_user}] POP3 發生錯誤: {e}")
            traceback.print_exc()
    else:
        try:
            mail = imaplib.IMAP4_SSL(mail_receive_server, mail_receive_port)
            username = ntu_user.split("@")[0]
            mail.login(username, ntu_password)
            mail.select("INBOX")

            status, messages = mail.search(None, "UNSEEN")
            if status != "OK":
                print(f"⚠️ [{ntu_user}] 無法讀取收件匣")
                return

            mail_ids = messages[0].split()
            if not mail_ids:
                print(f"ℹ️ [{ntu_user}] 目前沒有未讀新信件")
                return

            print(f"📩 [{ntu_user}] 收到 {len(mail_ids)} 封未讀信件，準備處理...")

            for mail_id in mail_ids:
                # 1. 取得整封信件內容
                _, data = mail.fetch(mail_id, "(RFC822)")
                raw_email = data[0][1]

                # 2. 進行轉發
                forward_email(raw_email, ntu_user, ntu_password)

                # 3. 將信件複製到垃圾桶資料夾 (台大信箱預設通常為 Trash)
                result = mail.copy(mail_id, "Trash")
                
                if result[0] == "OK":
                    # 4. 複製成功後，標記原收件匣信件為刪除狀態
                    mail.store(mail_id, "+FLAGS", "\\Deleted")
                    print(f"🗑️ [{ntu_user}] 已將信件 ID {mail_id.decode()} 移至垃圾桶")
                else:
                    print(f"⚠️ [{ntu_user}] 移至垃圾桶失敗，僅標示為已讀")
                    mail.store(mail_id, "+FLAGS", "\\Seen")

            # 5. 永久刪除所有標記為 \Deleted 的信件（完成移動作業）
            mail.expunge()
            mail.logout()

        except Exception as e:
            print(f"❌ [{ntu_user}] IMAP 發生錯誤: {e}")
            traceback.print_exc()


def check_and_forward_all():
    """檢查所有設定的台大信箱帳號"""
    if not NTU_ACCOUNTS:
        print("⚠️ 未設定 any 台大信箱帳號")
        return
    if not FORWARD_TO:
        print("⚠️ 未設定 any 接收轉發的信箱")
        return

    for account in NTU_ACCOUNTS:
        ntu_user = account.get("user")
        ntu_password = account.get("password")
        if not ntu_user or not ntu_password:
            print("⚠️ 帳號設定不完整，跳過此項目")
            continue
        
        protocol = account.get("protocol", "").lower().strip()
        if not protocol:
            print(f"⚠️ [{ntu_user}] 未設定收信協定 (protocol 必填)，跳過此項目")
            continue
        
        # 取得指定的收信伺服器，若無則自動偵測
        mail_receive_server = account.get("mail_receive_server") or get_mail_receive_server(account)
        
        # 取得指定的收信連接埠，若無則依協定預設值 (pop3: 995, imap: 993)
        default_port = 995 if protocol == "pop3" else 993
        mail_receive_port = account.get("mail_receive_port") or default_port
        
        check_and_forward_account(ntu_user, ntu_password, mail_receive_server, mail_receive_port, protocol)


if __name__ == "__main__":
    # 執行一次檢查，若要定期自動執行可搭配 cron 或 time.sleep 迴圈
    check_and_forward_all()