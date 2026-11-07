"""Reset or create the database from schema.sql + seed_data/*.csv.

    python seed.py --reset     delete salon.db and rebuild it (all added/changed data is lost)
    python seed.py             build it only if it does not exist yet
Stop the running app first (Ctrl+C) so the file is not locked.
"""
import os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "salon.db")

if "--reset" in sys.argv:
    if os.path.exists(DB):
        try:
            os.remove(DB)
        except PermissionError:
            sys.exit("Could not delete salon.db - stop the app (Ctrl+C) and try again.")
    print("Old database deleted.")
elif os.path.exists(DB):
    sys.exit("salon.db already exists. Use:  python seed.py --reset")

import app                      # importing app builds salon.db from the seed files when it is missing
if not os.path.exists(DB):
    app.init_db()
import sqlite3
con = sqlite3.connect(DB)
print("Database ready from seed data:", ", ".join("{} {}".format(con.execute("SELECT COUNT(*) FROM " + t).fetchone()[0], t)
      for t in ("users", "customers", "pets", "appointments", "opportunities", "tickets", "interactions")))
