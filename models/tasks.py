# coding: utf8
import os
from spiaceReport import spiaceReport

def autoSync():
    print 'SYNCING ...'
    filename = os.path.join(request.folder, 'modules\spiaceReport', 'spiaceConfig.ini')
    spiaceReport.runSync(filename)
    print 'SYNC Complete'
    return True

def emailNotification():
    print "NOTIFYING ..."
    filename = os.path.join(request.folder, 'modules\spiaceReport', 'spiaceConfig.ini')
    spiaceReport.emailNotification(filename)
    print 'NOTIFICATION Complete'
    return True

from gluon.scheduler import Scheduler
Scheduler(db, dict(autoSync=autoSync, emailNotification=emailNotification))
