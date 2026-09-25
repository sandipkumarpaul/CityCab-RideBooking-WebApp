import os
import sys

# Point the app at a throwaway in-memory database before it is imported, so the
# test suite never touches (or wipes) the local development database.
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['CITYCAB_AUTO_SEED'] = '0'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
