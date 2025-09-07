from keys import token_bot, token, admin_name, password_admin, ip_address, port, basa_name

token_bot = token_bot
# токен внизу для переводчика яндекс
token = token

admin_name = admin_name
password_admin = password_admin
ip_address = ip_address
port = port
basa_name = basa_name

dns = f"postgresql://{admin_name}:{password_admin}@{ip_address}:{port}/{basa_name}"