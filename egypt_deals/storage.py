import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .model import Listing, date_value, now

class Database:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path,timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS listings(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS observations(
                listing_id TEXT NOT NULL, observed_at TEXT NOT NULL, price REAL, eligible INTEGER NOT NULL,
                PRIMARY KEY(listing_id, observed_at));
            CREATE INDEX IF NOT EXISTS observation_lookup ON observations(listing_id, observed_at);
            CREATE TABLE IF NOT EXISTS source_runs(source TEXT, ran_at TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS alerts(key TEXT PRIMARY KEY, created_at TEXT, message TEXT, sent_at TEXT, listing_id TEXT, price REAL, expired_at TEXT);
        ''')
        columns={row['name'] for row in self.db.execute('PRAGMA table_info(alerts)')}
        for name,kind in [('listing_id','TEXT'),('price','REAL'),('expired_at','TEXT')]:
            if name not in columns: self.db.execute(f'ALTER TABLE alerts ADD COLUMN {name} {kind}')

    def save(self, listings, status):
        with self.db:
            for l in listings:
                self.db.execute('INSERT OR REPLACE INTO listings VALUES(?,?)', (l.identity,json.dumps(l.dict(),ensure_ascii=False)))
                self.db.execute('INSERT OR IGNORE INTO observations VALUES(?,?,?,?)', (l.identity,l.observed_at,l.price_egp,int(l.eligible())))
            self.db.execute('INSERT INTO source_runs VALUES(?,?,?)', (status['source'],now(),json.dumps(status)))

    def listings(self):
        allowed = Listing.__dataclass_fields__
        return [Listing(**{k:v for k,v in json.loads(r[0]).items() if k in allowed}).refresh_on_read() for r in self.db.execute('SELECT payload FROM listings')]

    def previous(self, listing, hours=24):
        end = date_value(listing.observed_at)
        start = end-timedelta(hours=hours)
        row = self.db.execute('SELECT price FROM observations WHERE listing_id=? AND observed_at>=? AND observed_at<? AND eligible=1 AND price>0 ORDER BY observed_at DESC LIMIT 1',
            (listing.identity,start.isoformat(),end.isoformat())).fetchone()
        return row[0] if row else None

    def history(self, listing, days):
        start = (datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
        r = self.db.execute('SELECT MIN(price), COUNT(*), MIN(observed_at), MAX(observed_at) FROM observations WHERE listing_id=? AND observed_at>=? AND eligible=1 AND price>0',
            (listing.identity,start)).fetchone()
        return {'low_egp':r[0], 'observations':r[1], 'first_observed_at':r[2], 'last_observed_at':r[3]}

    def due(self, source):
        row = self.db.execute('SELECT ran_at,payload FROM source_runs WHERE source=? ORDER BY rowid DESC LIMIT 1',(source['id'],)).fetchone()
        if not row:return True
        status=json.loads(row[1]);interval=source.get('interval_hours',24)
        if source.get('revision',0)>status.get('source_configuration_revision',0):return True
        failed=status.get('status')=='blocked_or_failed' or any(any(word in error for word in ['HTTP 401','HTTP 403','HTTP 429','robots','adapter needs review']) for error in status.get('errors',[]))
        if not failed and status.get('discovered_product_urls') and source.get('rotate_inventory',True):
            if status.get('never_attempted_product_urls',0):interval=min(interval,source.get('backlog_interval_hours',0.05))
            else:interval=min(interval,interval*max(status.get('detail_limit',1),1)/status['discovered_product_urls'])
        began=date_value(status.get('started_at')) or date_value(row[0])
        return (datetime.now(timezone.utc)-began).total_seconds()>=interval*3600

    def statuses(self):
        return [{**json.loads(row[0]),'last_saved_at':row[1]} for row in self.db.execute('SELECT payload,ran_at FROM source_runs WHERE rowid IN (SELECT MAX(rowid) FROM source_runs GROUP BY source) ORDER BY source')]

    def queue(self, key, message, listing_id=None, price=None):
        with self.db:
            cursor = self.db.execute('''INSERT INTO alerts(key,created_at,message,sent_at,listing_id,price,expired_at) VALUES(?,?,?,NULL,?,?,NULL)
                ON CONFLICT(key) DO UPDATE SET created_at=excluded.created_at,message=excluded.message,sent_at=NULL,
                listing_id=excluded.listing_id,price=excluded.price,expired_at=NULL WHERE alerts.expired_at IS NOT NULL''',(key,now(),message,listing_id,price))
        return cursor.rowcount > 0

    def pending(self):
        return self.db.execute('SELECT * FROM alerts WHERE sent_at IS NULL AND expired_at IS NULL ORDER BY created_at').fetchall()

    def expire_invalid(self):
        if not self.pending():return 0
        listings={l.identity:l for l in self.listings()}
        keys=[]
        for row in self.pending():
            l=listings.get(row['listing_id'])
            if l is None or not l.eligible() or l.price_egp!=row['price']: keys.append(row['key'])
        with self.db:
            self.db.executemany('UPDATE alerts SET expired_at=? WHERE key=?',[(now(),key) for key in keys])
        return len(keys)

    def sent(self, key):
        with self.db:
            self.db.execute('UPDATE alerts SET sent_at=? WHERE key=?',(now(),key))

    def close(self):
        self.db.close()
