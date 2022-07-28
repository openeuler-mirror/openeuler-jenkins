import os
import smtplib
from email.mime.text import MIMEText


def msg_body(account, password):
    body = """
    你好，如果你已有该Jenkins账号，请忽略这封邮件。以下是为你自动创建的Jenkins账号，密码为随机生成，请在首次登录后更改密码
    
    账号: {0}
    密码: {1}
    
    
    Hi, ignore the message if you had the Jenkins account. The following is the Jenkins account automatically created 
    for you. The password is randomly generated. Please change the password after the first login.
    
    Account: {0}
    Password: {1}
    """.format(account, int(password))
    return body


def sendmail(account, password, receiver):
    smtp_server_host = os.getenv('SMTP_SERVER_HOST', '')
    smtp_server_port = os.getenv('SMTP_SERVER_POST', '')
    smtp_server_user = os.getenv('SMTP_SERVER_USER', '')
    smtp_server_pass = os.getenv('SMTP_SERVER_PASS', '')

    body = msg_body(account, password)
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = 'openEuler门禁工程Jenkins账号配置'
    msg['From'] = '{}<openEuler Infrastructure>'.format(smtp_server_user)
    msg['To'] = receiver

    server = smtplib.SMTP(smtp_server_host, smtp_server_port)
    server.ehlo()
    server.starttls()
    server.login(smtp_server_user, smtp_server_pass)
    server.sendmail(smtp_server_user, receiver, msg.as_string())
