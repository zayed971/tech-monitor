"""Reparse saved titles without fetching pages or refreshing price timestamps.

Stop the monitor before running this script; it takes the same exclusive lock.
"""
import fcntl
import json
import argparse
import re
from pathlib import Path

from egypt_deals.catalog_report import export_hardware
from egypt_deals.metrics import apply_references
from egypt_deals.storage import Database


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--categories',help='comma-separated categories to reparse; default all saved rows')
    parser.add_argument('--title-regex',help='reparse only saved titles matching this expression')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    with (root/'data/monitor.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('Stop the active monitor before rebuilding saved records.')
        db=Database(root/'data/deals.sqlite3')
        try:
            listings=db.listings()
            selected=[item for item in listings if (not args.categories or item.category in args.categories.split(',')) and (not args.title_regex or re.search(args.title_regex,item.raw_title,re.I))]
            for item in selected:
                if '?variant=' in item.url and not item.parent_title:
                    title,separator,variant=item.raw_title.rpartition(' — ')
                    item.parent_title=title if separator else item.raw_title
                    item.variant_title=variant if separator else None
                item.specs={};item.spec_sources={};item.finish()
            apply_references(selected,root/'references.json')
            with db.db:
                db.db.executemany('UPDATE listings SET payload=? WHERE id=?',
                    [(json.dumps(item.dict(),ensure_ascii=False),item.identity) for item in selected])
            summary=export_hardware(listings,root,db.statuses())
            print(json.dumps({'reparsed_saved_rows':len(selected),'observation_timestamps_preserved':True,**summary}),flush=True)
        finally:db.close()


if __name__=='__main__':main()
