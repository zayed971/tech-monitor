"""Connect after the owner starts the bot, then run the bounded price watcher.

Run with the project's Python under flock. Credentials stay in .env or the
environment. The background process depends on the cloud workspace staying up.
"""
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timedelta, timezone

from egypt_deals.cli import write_json
from egypt_deals.model import date_value, now
from egypt_deals.storage import Database
from egypt_deals.alerts import send_pending
from egypt_deals.telegram_setup import load_settings, api, private_chat_ids, setup, TelegramSetupError


def main():
    root=Path(__file__).resolve().parents[1]
    os.chdir(root)
    data=root/'data'
    data.mkdir(exist_ok=True)
    deadline=data/'watch.json'
    if not deadline.exists():
        write_json(deadline,{'started_at':now(),'stop_at':(datetime.now(timezone.utc)+timedelta(days=21)).isoformat()})
    end=date_value(json.loads(deadline.read_text())['stop_at'])

    def status(state, **details):
        record={'status':state,'checked_at':now(),'monitor_pid':os.getpid(),'stop_at':end.isoformat(),**details}
        write_json(data/'telegram-status.json',record)
        print(json.dumps(record),flush=True)

    load_settings(root)
    token=os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        status('credentials_missing',test_sent=False)
        return
    try:
        api(token,'getMe')
    except TelegramSetupError as error:
        status('token_error',message=str(error),test_sent=False)
        return
    status('waiting_for_start',token_authenticated=True,test_sent=False)
    while datetime.now(timezone.utc)<end:
        try:
            chat=os.environ.get('TELEGRAM_CHAT_ID')
            if not chat:
                ids=private_chat_ids(api(token,'getUpdates',{'timeout':0,'allowed_updates':['message']}))
                if len(ids)>1:
                    status('chat_identification_required',private_chat_count=len(ids),test_sent=False)
                    return
                if ids:
                    chat=ids[0]
                    os.environ['TELEGRAM_CHAT_ID']=chat
            if chat:
                setup(root,send_test=True)
                db=Database(data/'deals.sqlite3')
                try:
                    delivery=send_pending(db)
                finally:
                    db.close()
                status('connected',token_authenticated=True,test_sent=True,alert_delivery=delivery)
                # Replace this process, preserving the flock and process ID.
                os.execv(sys.executable,[sys.executable,'-m','egypt_deals.cli','watch',
                    '--root',str(root),'--scope','hardware','--max-pages','150',
                    '--max-details','100','--workers','4','--delay','4',
                    '--cache-ttl','0','--send','--days','21','--bootstrap','--poll-seconds','60'])
        except TelegramSetupError as error:
            status('connection_retry',message=str(error),test_sent=False)
        time.sleep(15)
    status('stopped_at_deadline',test_sent=False)


if __name__=='__main__':
    main()
