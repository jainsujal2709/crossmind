import sys,os
sys.path.insert(0,os.path.join(os.path.dirname(__file__),"..","backend"))
from main import *
print("Admin ready:",config.ADMIN_EMAIL or "set ADMIN_EMAIL/ADMIN_PASSWORD in .env")
