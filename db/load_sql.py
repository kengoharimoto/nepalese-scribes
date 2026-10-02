"""Load the NGMCP title-list MySQL dump (data/ngmcpdb_production.sql.bz2) into SQLite.

Account tables (users, roles, permissions) are skipped.
"""
import bz2, os, re, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'data', 'ngmcpdb_production.sql.bz2')
SKIP = {'users', 'roles', 'roles_users', 'permissions', 'permissions_roles', 'schema_info'}
ESC = {'0': '\0', 'n': '\n', 'r': '\r', 't': '\t', 'Z': '\x1a', 'b': '\b'}


def create_stmt(name, body):
    cols = []
    for line in body.splitlines():
        m = re.match(r'\s*`([^`]+)`\s+(\w+)', line)
        if not m:
            continue
        typ = m.group(2).lower()
        aff = 'INTEGER' if 'int' in typ else 'REAL' if typ in ('float', 'double', 'decimal') else 'TEXT'
        pk = ' PRIMARY KEY' if m.group(1) == 'id' and 'AUTO_INCREMENT' in line else ''
        cols.append(f'"{m.group(1)}" {aff}{pk}')
    return f'CREATE TABLE "{name}" ({", ".join(cols)})'


def rows(s):
    """Parse the VALUES part of a MySQL extended INSERT."""
    i, n = 0, len(s)
    while i < n:
        if s[i] != '(':
            i += 1
            continue
        i += 1
        row, cur = [], None
        while True:
            c = s[i]
            if c == "'":
                i += 1
                buf = []
                while True:
                    c = s[i]
                    if c == '\\':
                        buf.append(ESC.get(s[i + 1], s[i + 1]))
                        i += 2
                    elif c == "'":
                        if s[i + 1] == "'":
                            buf.append("'"); i += 2
                        else:
                            i += 1
                            break
                    else:
                        buf.append(c); i += 1
                cur = ''.join(buf)
            elif c in ',)':
                row.append(cur)
                cur = None
                i += 1
                if c == ')':
                    yield row
                    break
            else:
                j = i
                while s[j] not in ',)':
                    j += 1
                tok = s[i:j].strip()
                i = j
                if tok == 'NULL':
                    cur = None
                else:
                    try:
                        cur = int(tok)
                    except ValueError:
                        cur = float(tok)


def load(dbpath):
    con = sqlite3.connect(dbpath)
    text = bz2.open(SRC, 'rt', encoding='utf-8').read()
    for m in re.finditer(r'CREATE TABLE `(\w+)` \((.*?)\n\) ENGINE', text, re.S):
        if m.group(1) in SKIP:
            continue
        con.execute(f'DROP TABLE IF EXISTS "{m.group(1)}"')
        con.execute(create_stmt(m.group(1), m.group(2)))
    for m in re.finditer(r'^INSERT INTO `(\w+)` VALUES (.*);$', text, re.M):
        name = m.group(1)
        if name in SKIP:
            continue
        data = list(rows(m.group(2)))
        con.executemany(f'INSERT INTO "{name}" VALUES ({",".join("?" * len(data[0]))})', data)
    con.commit()
    return con


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'ngmcp_titlelist.sqlite')
    if os.path.exists(out):
        os.remove(out)
    con = load(out)
    for (t,) in con.execute("select name from sqlite_master where type='table' order by name"):
        print(t, con.execute(f'select count(*) from "{t}"').fetchone()[0])
