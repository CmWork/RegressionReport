import sys, getopt
import re
import sqlite3
from bs4 import BeautifulSoup
'''
open regression db
select all testcaseName, testcaseLink
parse both for <a href=...>
replace with contents (remove anchor tag)
'''

def fixRegDb(filename):
    db = sqlite3.connect(filename)
    c = db.cursor()
    c.execute('SELECT * FROM testcases')
    rows = c.fetchall()
    for row in rows:
        id = row[0]
        tc = row[1]
        tcLink = row[2]
        tcSoup = BeautifulSoup(str(tc))

        needsUpdate = False
        tcA = tcSoup.find('a')
        if tcA is not None:
            tc = tcA.renderContents().strip()
            tcLink = 'http://smarttestdb.cal.ci.spirentcom.com/stapp/result_table/?f=1e' + tc
            needsUpdate = True

        if needsUpdate:
            c.execute("UPDATE testcases SET testcaseName=?, testcaseLink=? WHERE id=?", (tc, tcLink, id))
            db.commit()
    db.close()

def main(argv):
    db = ''
    try:
        opts, args = getopt.getopt(argv, "hd:", ["db="])
    except getopt.GetoptError:
        print 'python FixRegressionDb.py -d <database file>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == "-h":
            print 'python FixRegressionDb.py -d <database file>'
            sys.exit()
        elif opt in ("-d", "--db"):
            db = arg
    fixRegDb(db)

if __name__ == '__main__':
    main(sys.argv[1:])