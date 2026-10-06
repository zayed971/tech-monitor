"""Connect an owned Telegram bot without logging its token or private messages."""
import getpass
import os
import shlex

import httpx

class TelegramSetupError(Exception):
    pass

def load_settings(root):
    path=root/'.env'
    if not path.exists(): return
    for line in path.read_text().splitlines():
        if '=' not in line or line.lstrip().startswith('#'): continue
        key,value=line.split('=',1)
        if key.strip() not in {'TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'}: continue
        try: values=shlex.split(value)
        except ValueError: continue
        if len(values)==1: os.environ.setdefault(key.strip(),values[0])

def api(token,method,payload=None):
    try:
        r=httpx.post(f'https://api.telegram.org/bot{token}/{method}',json=payload or {},timeout=20)
        if r.status_code!=200: raise TelegramSetupError(f'Telegram rejected {method} (HTTP {r.status_code}); check the bot token and press Start in your bot.')
        result=r.json()
        if not result.get('ok'): raise TelegramSetupError(f'Telegram rejected {method}.')
        return result.get('result')
    except (httpx.HTTPError,ValueError):
        raise TelegramSetupError('Telegram network/response error; token was not logged.') from None

def private_chat_ids(updates):
    # Do not print or store usernames, names, or message contents.
    return sorted({str(u['message']['chat']['id']) for u in updates or []
                   if isinstance(u,dict) and isinstance(u.get('message'),dict)
                   and u['message'].get('chat',{}).get('type')=='private'})

def setup(root,send_test=True):
    load_settings(root)
    from_environment=bool(os.environ.get('TELEGRAM_BOT_TOKEN'))
    token=os.environ.get('TELEGRAM_BOT_TOKEN') or getpass.getpass('BotFather token (hidden): ').strip()
    if not token: raise TelegramSetupError('No bot token supplied.')
    bot=api(token,'getMe')
    chat=os.environ.get('TELEGRAM_CHAT_ID')
    if not chat:
        ids=private_chat_ids(api(token,'getUpdates',{'timeout':0,'allowed_updates':['message']}))
        if not ids: raise TelegramSetupError('Open your bot in Telegram, press Start, and run this command again.')
        if len(ids)==1: chat=ids[0]
        else:
            print('Private chat IDs available: '+', '.join(ids))
            chat=input('Your chat ID: ').strip()
            if chat not in ids: raise TelegramSetupError('Choose one of the available private chat IDs.')
    path=root/'.env'
    existing=path.read_text().splitlines() if path.exists() else []
    retained=[line for line in existing if line.split('=',1)[0].strip() not in {'TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'}]
    if not from_environment: retained.append('TELEGRAM_BOT_TOKEN='+shlex.quote(token))
    # Environment-managed tokens remain in the cloud secret binding.
    elif path.exists():
        retained.extend(line for line in existing if line.split('=',1)[0].strip()=='TELEGRAM_BOT_TOKEN')
    retained.append('TELEGRAM_CHAT_ID='+shlex.quote(chat))
    path.write_text('\n'.join(retained)+'\n');path.chmod(0o600)
    os.environ['TELEGRAM_CHAT_ID']=chat
    if send_test:
        api(token,'sendMessage',{'chat_id':chat,'text':'Egypt Deals bot connected. Price alerts will be sent here when a verified tracked offer matches your rules.'})
    return {'bot_username':bot.get('username'),'chat_id':chat,'test_sent':send_test,'status':'connected'}
