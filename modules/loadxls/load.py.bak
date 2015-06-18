#!/usr/bin/env python
# -*- coding: utf-8 -*-
from gluon import current
from gluon.dal import DAL, Field
from gluon.sqlhtml import SQLFORM
from gluon.validators import IS_NOT_EMPTY, IS_EMAIL, IS_LENGTH
from io import BytesIO
import sys

cols = ['Job', 'Branch', 'Build', 'Date', 'Module', 'Test Case', 'Link', 'Failure', 'Occurance', 'Reason', 'Action', 'Notes']

class TestJob():
    def __init__(self, jobInfo):
        self.jobInfo = jobInfo
        self.failList = list()

    def addFailure(self, module, tcName, tcLink, tcStatus, tcStatusLink, failure, occurrence, reason, action, notes):
        failDict = dict()
        failDict['module'] = module
        failDict['tcName'] = tcName
        failDict['tcLink'] = tcLink
        failDict['tcStatus'] = tcStatus
        failDict['tcStatusLink'] = tcStatusLink
        failDict['failure'] = failure
        failDict['occurrence'] = occurrence
        failDict['reason'] = reason
        failDict['action'] = action
        failDict['notes'] = notes
        self.failList.append(failDict)

class XlsLoader():
    def __init__(self):
        self.db = current.db
        self.session = current.session
        self.request = current.request
        self.response = current.response
        self.cache = current.cache
        self.jobDict = dict()
 
    def load(self, filename, data):
        #import openpyxl.reader.excel as excel
        import xlrd
        print '\n\n'
        
        wb = xlrd.open_workbook(file_contents=data, formatting_info=True)
        for sheet in wb.sheet_names():
            isBeingFixed = False
            if sheet == 'Being Fixed':
                isBeingFixed = True

            ws = wb.sheet_by_name(sheet)
            self.parseWorksheet(ws, isBeingFixed)
        self.loadToDb()
        return True

    def parseWorksheet(self, ws, isBeingFixed):
        jobSet = set()
        num_rows = ws.nrows - 1
        num_cells = ws.ncols - 1
        curr_row = 0
        while curr_row < num_rows:
            curr_row += 1
            row = ws.row(curr_row)
            jobName = ws.cell_value(curr_row, 0)
            print jobName
            jobLink = ws.hyperlink_map.get((curr_row, 0))
            jobLink = None if jobLink is None else jobLink.url_or_path
            branch = ws.cell_value(curr_row, 1)
            build = ws.cell_value(curr_row, 2)
            date = ws.cell_value(curr_row, 3)

            module = ws.cell_value(curr_row, 4)
            tcName = ws.cell_value(curr_row, 5)
            tcLink = ws.hyperlink_map.get((curr_row, 5))
            tcLink = None if tcLink is None else tcLink.url_or_path
            tcStatus = ws.cell_value(curr_row, 6)
            tcStatusLink = ws.hyperlink_map.get((curr_row, 6))
            tcStatusLink = None if tcStatusLink is None else tcStatusLink.url_or_path
            failure = ws.cell_value(curr_row, 7)
            occurrence = ws.cell_value(curr_row, 8)
            reason = ws.cell_value(curr_row, 9)
            action = ws.cell_value(curr_row, 10)
            notes = ws.cell_value(curr_row, 11)

            jobForSet = (jobName, jobLink, branch, build, date, isBeingFixed)
            tj = None
            if jobForSet in jobSet:
                tj = self.jobDict[jobForSet]
            else:
                tj = TestJob(jobForSet)
                self.jobDict[jobForSet] = tj

            tj.addFailure(module, tcName, tcLink, tcStatus, tcStatusLink, failure, occurrence, reason, action, notes)

    def loadToDb(self):
        db = self.db
        jobs = self.db.jobs
        runs = self.db.runs
        modules = self.db.modules
        testcases = self.db.testcases
        failures = self.db.failures
        reviews = self.db.reviews
        
        for key in self.jobDict.keys():
            # Add job
            jobName = key[0]
            print jobName
            branch = key[2]
            isBeingFixed = key[5]
            jobId = None
            select = db((jobs.jobName==jobName) & (jobs.beingFixed==isBeingFixed)).select(jobs.id)
            if len(select) > 0:
                jobId = select[0].id
            else:
                jobId = jobs.update_or_insert((jobs.jobName==jobName) & (jobs.beingFixed==isBeingFixed), jobName=jobName, beingFixed=isBeingFixed)
            print jobId

            # Add run
            jobLink = key[1]
            build = key[3]
            date = key[4]
            runId = None
            select = db((runs.build==build) & (runs.date == date)).select(runs.id)
            if len(select) > 0:
                runId = select[0].id
            else:
                runId = runs.update_or_insert((runs.build == build) & (runs.date == date), jobId=jobId, build=build, date=date, runLink=jobLink)

            for fail in self.jobDict[key].failList:
                # Add module
                module = fail['module']
                moduleId = None
                select = db(modules.moduleName==module).select(modules.id)
                if len(select) > 0:
                    moduleId = select[0].id
                else:
                    moduleId = modules.update_or_insert(modules.moduleName == module, moduleName=module)
                
                # Add testcase
                tcName = fail['tcName']
                tcLink = fail['tcLink']
                tcId = None
                select = db(testcases.testcaseName==tcName).select(testcases.id)
                if len(select) > 0:
                    tcId = select[0].id
                else:
                    tcId = testcases.update_or_insert(testcases.testcaseName == tcName, testcaseName=tcName, testcaseLink=tcLink)
                    
                # Add failure
                tcStatus = fail['tcStatus']
                tcStatusLink = fail['tcStatusLink']
                failId = None
                select = db((failures.testcaseId == tcId) & (failures.runId == runId)).select(failures.id)
                if len(select) > 0:
                    failId = select[0].id
                else:
                    failId = failures.update_or_insert((failures.testcaseId == tcId) & (failures.runId == runId), testcaseId=tcId, runId=runId, moduleId=moduleId, failStatus=tcStatus, failLink=tcStatusLink)

                # Add review
                failure = fail['failure']
                occurrence = fail['occurrence']
                reason = fail['reason']
                action = fail['action']
                notes = fail['notes']
                reviewId = None
                select = db(reviews.failureId == failId).select(reviews.id)
                if len(select) > 0:
                    reviewId = select[0].id
                else:
                    reviewId = reviews.update_or_insert(reviews.failureId == failId, reviewDate=date, failureId=failId, failure=failure, occurrence=occurrence, reason=reason, action=action, notes=notes)
        db.commit()

'''
num_rows = worksheet.nrows - 1
num_cells = worksheet.ncols - 1
curr_row = -1
while curr_row < num_rows:
	curr_row += 1
	row = worksheet.row(curr_row)
	print 'Row:', curr_row
	curr_cell = -1
	while curr_cell < num_cells:
		curr_cell += 1
		# Cell Types: 0=Empty, 1=Text, 2=Number, 3=Date, 4=Boolean, 5=Error, 6=Blank
		cell_type = worksheet.cell_type(curr_row, curr_cell)
		cell_value = worksheet.cell_value(curr_row, curr_cell)
		print '	', cell_type, ':', cell_value
        return True

mainData_book = xlrd.open_workbook("IEsummary.xls", formatting_info=True)
mainData_sheet = mainData_book.sheet_by_index(0)
for row in range(1, 101):
    rowValues = mainData_sheet.row_values(row, start_colx=0, end_colx=8)
    company_name = rowValues[0]

    link = mainData_sheet.hyperlink_map.get((row, 0))
    url = '(No URL)' if link is None else link.url_or_path
    print(company_name.ljust(20) + ': ' + url)
'''
