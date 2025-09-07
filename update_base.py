import psycopg2
import sqlalchemy
from sql_base import create_tabele, delete_tabele
from token_keys import dns



engine = sqlalchemy.create_engine(dns)
delete_tabele(engine)
create_tabele(engine)

# from sqlalchemy import create_engine, text
#
# engine = sqlalchemy.create_engine(dns)
#
# with engine.connect() as conn:
#     conn.execute(text("DROP SCHEMA public CASCADE"))
#     conn.execute(text("CREATE SCHEMA public"))
#     conn.commit()