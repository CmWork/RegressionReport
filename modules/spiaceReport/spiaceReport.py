import os
import sys
import smtplib
import datetime
import requests
import re
import xlsxwriter
import ConfigParser
from pytz import timezone
from bs4 import BeautifulSoup

from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email import Encoders

from gluon import current
from gluon.dal import DAL, Field
from gluon.sqlhtml import SQLFORM
from gluon.validators import IS_NOT_EMPTY, IS_EMAIL, IS_LENGTH
from io import BytesIO
import sys

jobList = list()
beingFixedList = list()
devJobList = dict()
emailList = list()

occurList = [
    'Constant',
    'Intermittent',
    'Don\'t Know'
    ]

actionList = [
    'BDC to investigate',
    'HNL to investigate',
    'IDC to investigate',
    'Other to investigate',
    'Set to Being Fixed',
    'Create CR',
    'Modify Script',
    'Instrument Code',
    'Replicate Failure',
    'No Action'
    ]

now = datetime.datetime.now(timezone('UTC'))
lastSyncSmt = now - datetime.timedelta(1)
lastSyncDev = now - datetime.timedelta(1)
latestResultsSmt = now - datetime.timedelta(1)
latestResultsDev = now - datetime.timedelta(1)

class TestJob():
    def __init__(self, build, link, title, startTime, isSmt = True):
        self.build = build
        self.link = link
        self.title = title
        self.startTime = startTime
        self.isSmt = isSmt
        self.failList = list()

    def addFailure(self, tcname, link, txt, module):
        self.failList.append((tcname, link, txt, module))


def httpRequest(url):
    headers = {'accept': 'application/json'}
    service = requests.get(url, headers=headers)
    if service.status_code != 200:
        print "ERROR: " + str(service.status_code)
        return None
    else:
        content = service.content.replace("'", '"')
        return content

def getJobs():
    job_list = list()
    url = 'http://smarttestdb.cal.ci.spirentcom.com/stapp/front_end/'
    soup = BeautifulSoup(httpRequest(url))
    tag_li = soup.findAll('li')

    for li in tag_li:
        soup = BeautifulSoup(str(li))
        job = parseJob(soup)
        if job is not None:
            job_list.append(job)
    return job_list

def parseJob(html):
    global latestResultsSmt
    tj = None
    soup = BeautifulSoup(str(html))
    case = soup.findAll(['a', 'span', 'b'])
    link = case[0]['href']
    link = re.sub('suite_result', 'suite_summary_detail_table', link)
    title = case[0].renderContents()
    date = case[1].renderContents()
    complete = int(re.match('(?:<b>)([0-9]+)', case[2].renderContents()).group(1))

    build = ''

    for tag in case:
        m = re.match('^([0-9]{1}.[0-9]{2}.[0-9]{4})$', tag.renderContents())
        if m is not None:
            build = m.group(0)
            break
    dt = timezone('UTC').localize(datetime.datetime.strptime(date, '%Y.%m.%d %H:%M:%S'))
    if title in jobList and complete > 25 and dt > lastSyncSmt and dt <= now:
        tj = TestJob(build, link, title, date)
        if not latestResultsSmt or dt > latestResultsSmt:
            latestResultsSmt = dt
    return tj

def getFmcFailures(newJobs):
    hasFailed = False
    baseUrl = 'http://smarttestdb.cal.ci.spirentcom.com'
    mstAddon = '&mst=FMC'
    detailAddon = '&detail=AllFails'

    for job in newJobs:
        moduleList = list()
        url = baseUrl + job.link + mstAddon + detailAddon

        # Store link to main results view after getting detailed view
        job.link = re.sub('suite_summary_detail_table', 'suite_result', url)

        html = httpRequest(url)
        if html is None:
            continue
        soup = BeautifulSoup(html)
        # Module
        thead = soup.findAll(id="head_tr")
        sthead = BeautifulSoup(str(thead))
        tdata = sthead.findAll('b')
        for hdr in tdata:
            hdrVal = re.sub(r'(<br/>)', '', hdr.renderContents())
            moduleList.append(hdrVal)

        # Failure
        tbody = soup.findAll(id="detail_tbody_AllFails")
        stbody = BeautifulSoup(str(tbody))
        trows = stbody.findAll('tr')
        for tr in trows:
            strow = BeautifulSoup(str(tr))
            tds = strow.findAll('td')
            for (idx, td) in enumerate(tds):
                if idx is 0:
                    tcLink = td.find('a')
                    tcname = tcLink.renderContents()
                    print tcname
                else:
                    stdata = BeautifulSoup(str(td))
                    link = stdata.find('a')
                    if link is not None:
                        href = link['href']
                        txt = link.renderContents()
                        module = moduleList[idx]
                        break
            job.addFailure(tcname, href, txt, module)
            hasFailed = True
    return hasFailed

def getMbhFailures(newJobs):
    global latestResultsDev
    hasFailed = False
    baseUrl = 'http://jenkins-pv.cal.ci.spirentcom.com:8080/view/dev_regressions/job/'
    htmlAddon = '/HTML_Report/'

    for key, value in devJobList.items():
        url = baseUrl + key + htmlAddon
        for val in value:
            html = httpRequest(url + val)
            if html is None:
                continue
            soup = BeautifulSoup(html)

            # Job Name
            jobNameTr = soup.find('tr', 'strow1')
            jobNameCont = BeautifulSoup(str(jobNameTr)).find('td', 'stcontent')
            jobNameHref = jobNameCont.find('a')
            jobName = jobNameHref.renderContents()

            # Build
            build = ''
            titleRaw = jobNameHref['title']
            m = re.match('^(.*)([0-9]{1}.[0-9]{2}.[0-9]{4})', titleRaw)
            if m is not None:
                build = m.group(2)

            # End Date
            endDateTr = soup.find('tr', 'strow6')
            endDateCont = BeautifulSoup(str(endDateTr)).find('td', 'stcontent')
            endDate = endDateCont.find('span').renderContents()
            dt = timezone('UTC').localize(datetime.datetime.strptime(endDate, '%m/%d/%Y %H:%M:%S %p'))
            endDate = dt.strftime('%Y.%m.%d %H:%M:%S')

            if dt > lastSyncDev and dt <= now:
                tj = TestJob(build, url, jobName, endDate, False)
                if parseMbhFailures(tj, soup):
                    newJobs.append(tj)
                    hasFailed = True
                    if not latestResultsDev or dt > latestResultsDev:
                        latestResultsDev = dt
    return hasFailed

def parseMbhFailures(job, html):
    hasFailed = False
    trows = BeautifulSoup(str(html)).findAll('tr')
    for tr in trows:
        strow = BeautifulSoup(str(tr))
        ahref = strow.find('a', href=True)
        if ahref is not None:
            span = ahref.find('span')

            # Failed test cases
            if span is not None and span.renderContents() != 'P':
                # tcname, href, txt, module
                m = re.match('F|NA', span.get_text(strip=True))
                txt = 'NA'
                if m is not None:
                    txt = m.group(0)

                tcname = ''
                tcNameRaw = strow.find('p', 'MsoNormal').find('span')
                if tcNameRaw is not None:
                    tcname = tcNameRaw.renderContents()

                href = ahref['href']
                job.addFailure(tcname, href, txt, '')
                hasFailed = True
    return hasFailed


def exportFailuresToDb(newJobs):
    db = current.db
    jobs = db.jobs
    runs = db.runs
    modules = db.modules
    testcases = db.testcases
    failures = db.failures
    reviews = db.reviews

    for job in newJobs:
        jobId = None
        jobName = job.title
        jobLink = job.link
        build = job.build
        date = job.startTime
        isSmt = job.isSmt
        isBeingFixed = False

        if jobName in beingFixedList:
            isBeingFixed = True

        select = db((jobs.jobName==jobName) & (jobs.beingFixed==isBeingFixed)).select(jobs.id)
        if len(select) > 0:
            print "found jobs: " + jobName
            jobId = select[0].id
        else:
            print "update jobs: " + jobName
            jobId = jobs.update_or_insert((jobs.jobName==jobName) & (jobs.beingFixed==isBeingFixed), jobName=jobName, beingFixed=isBeingFixed)
        print jobId
            
        # Add run
        runId = None
        select = db((runs.build==build) & (runs.date == date)).select(runs.id)
        if len(select) > 0:
            print "found runs"
            runId = select[0].id
        else:
            print "update runs"
            runId = runs.update_or_insert((runs.build == build) & (runs.date == date), jobId=jobId, build=build, date=date, runLink=jobLink)

        for fail in job.failList:
            tcName = fail[0]
            tcLink = None
            if isSmt:
                tcLink = 'http://smarttestdb.cal.ci.spirentcom.com/stapp/result_table/?f=1e' + tcName
            tcStatusLink = fail[1]
            tcStatus = fail[2]
            module = fail[3]

            # Add module
            moduleId = None
            select = db(modules.moduleName==module).select(modules.id)
            if len(select) > 0:
                print "found modules: " + module
                moduleId = select[0].id
            else:
                print "update modules"
                moduleId = modules.update_or_insert(modules.moduleName == module, moduleName=module)

            # Add testcase
            tcId = None
            select = db(testcases.testcaseName==tcName).select(testcases.id)
            if len(select) > 0:
                print "found tcs"
                tcId = select[0].id
            else:
                print "update tcs"
                tcId = testcases.update_or_insert(testcases.testcaseName == tcName, testcaseName=tcName, testcaseLink=tcLink)

            # Add failure
            failId = None
            select = db((failures.testcaseId == tcId) & (failures.runId == runId) & (failures.moduleId == moduleId)).select(failures.id)
            if len(select) > 0:
                print "found failures"
                failId = select[0].id
            else:
                print "update failures"
                failId = failures.update_or_insert((failures.testcaseId == tcId) & (failures.runId == runId) & (failures.moduleId == moduleId), testcaseId=tcId, runId=runId, moduleId=moduleId, failStatus=tcStatus, failLink=tcStatusLink)
            print failId
                
            # Add review
            failure = ''
            occurrence = ''
            reason = ''
            action = ''
            notes = ''
            date = ''
            reviewId = None
            select = db(reviews.failureId == failId).select(reviews.id)
            if len(select) > 0:
                print "found reviews"
                reviewId = select[0].id
            else:
                print "update reviews"
                reviewId = reviews.update_or_insert(reviews.failureId == failId, reviewDate=date, failureId=failId, failure=failure, occurrence=occurrence, reason=reason, action=action, notes=notes)
    db.commit()


def parseIni(filename, hnlOnly = False):
    global jobList
    global beingFixedList
    global devJobList
    global emailList
    config = ConfigParser.ConfigParser()
    config.optionxform = str    # To keep case sensitivity on

    config.read(filename)

    # Job Lists
    jobList = list()
    jobList = config.get('configLists', 'smtList').splitlines()

    beingFixedList = list()
    beingFixedList = config.get('configLists', 'beingFixedList').splitlines()

    # Dev Regressions
    devJobList = dict()
    hnlRegList = ['hnl_fmc_regressions', 'hnl_regressions_1', 'hnl_regressions_2', 'hnl_regressions_intermittent_failures']
    for reg in hnlRegList:
        devJobList[reg] = list()
        for key, val in config.items(reg):
            if not hnlOnly or val == 'True':
                devJobList[reg].append(key)

    # Email Lists
    emailList = list()
    if hnlOnly:
        emailList = config.get('emailLists', 'hnlEmail').splitlines()
    else:
        emailList = config.get('emailLists', 'spiaceEmail').splitlines()

    return True

def writeIni(hnlOnly = False):
    filename = os.path.join(request.folder, 'modules/spiaceReport', 'spiaceConfig.ini')
    config = ConfigParser.ConfigParser()
    config.optionxform = str    # To keep case sensitivity on

    config.read(filename)
    key = 'syncTimestamp'
    if hnlOnly:
        key = 'syncTimestampHnl'
    if latestResultsSmt is not None:
        config.set(key, 'lastSyncSmt', latestResultsSmt.strftime('%Y.%m.%d %H:%M:%S'))
    if latestResultsDev is not None:
        config.set(key, 'lastSyncDev', latestResultsDev.strftime('%Y.%m.%d %H:%M:%S'))

    f = open(filename, 'w')
    config.write(f)
    f.close()

def send_mail(send_from, send_to, subject, text, files=[], server="localhost"):
    assert isinstance(send_to, list)
    assert isinstance(files, list)

    msg = MIMEMultipart()
    msg['From'] = send_from
    msg['To'] = COMMASPACE.join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject

    msg.attach( MIMEText(text) )

    for f in files:
        part = MIMEBase('application', "octet-stream")
        part.set_payload( open(f,"rb").read() )
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(f))
        msg.attach(part)

    smtp = smtplib.SMTP(server)
    smtp.sendmail(send_from, send_to, msg.as_string())
    smtp.close()


def runSync(filename):
    parseIni(filename, False)
    newJobs = getJobs()
    hasFailed = False
    hasFailedSmt = getFmcFailures(newJobs)
    hasFailedDev = getMbhFailures(newJobs)
    if hasFailedSmt or hasFailedDev:
        hasFailed = True
        exportFailuresToDb(newJobs)
    return hasFailed
'''def runSync(filename):
    mystr = '<tr class="strow1"> \
    <td class="stindex" valign="top" width="96"> \
    <p class="st"><b><span class="os"><a title="Test Suite name">SUITE:</a></span></b></p></td> \
    <td class="stcontent" valign="top" width="125"> \
    <p class="st"><span class="os"><a href="href" title="title">SPIACE_Regression_NextGen_LD</a></span></p></td> \
    </tr>'
    jobNameCont = BeautifulSoup(str(mystr)).find('td', 'stcontent')
    jobNameHref = jobNameCont.find('a')
    jobName = jobNameHref.renderContents()'''

def emailNotification(filename):
    parseIni(filename, False)

    fileList = []
    emailTitle = 'SPIACE Report ' + now.strftime('%Y.%m.%d %H:%M:%S') + ' UTC'
    emailBody = 'New Failures: http://honvm-regstore:8080/RegressionReport\nNeeds Attention: http://honvm-regstore:8080/RegressionReport/default/index?keywords=reviews.action+contains+"to+investigate"+or+reviews.action+=+""'

    send_mail('caden.morikuni@spirent.com',
        emailList,
        emailTitle,
        emailBody,
        fileList,
        'smtprelay.spirent.com')


if __name__ == '__main__':
    '''hnlOnly = False
    titleArea = ''
    if len(sys.argv) >= 2 and sys.argv[1] == '-hnl':
        hnlOnly = True
        titleArea = 'HNL'

    parseIni(hnlOnly)
    jobs = getJobs()
    hasFailed = False
    hasFailedSmt = getFmcFailures(jobs)
    hasFailedDev = getMbhFailures(jobs)
    if hasFailedSmt or hasFailedDev:
        hasFailed = True
    #writeIni(hnlOnly)
    fileList = list()
    '''

    '''
    emailTitle = titleArea + ' Final Report ' + now.strftime('%Y.%m.%d %H:%M:%S') + ' UTC'
    emailBody = 'There are no jobs to analyze.'
    if jobs:
        emailBody = 'There are no failures in: \n'
    if hasFailed:
        fileList.append(exportFailures(jobs, titleArea))
        emailTitle = titleArea + ' Initial Report ' + now.strftime('%Y.%m.%d %H:%M:%S') + ' UTC'
        emailBody = 'Inital Report from: \n'
    for job in jobs:
        emailBody = emailBody + '\t' + job.title + ' [' + job.build + ']\n'

    send_mail('caden.morikuni@spirent.com',
        emailList,
        emailTitle,
        emailBody,
        fileList,
        'smtprelay.spirent.com')'''
    # CM: store previous sheet and upon creating a new on delete old
