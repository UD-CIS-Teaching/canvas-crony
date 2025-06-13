from __future__ import annotations
import os

from fpdf import FPDF
import xlsxwriter

from canvas_data import CourseData, User
from cli_config import CronyConfiguration
from filesystem import clean_filename


class Report:
    maintype: str
    subtype: str
    extension: str

    def __init__(
        self,
        name: str,
        subject: str,
        target: User,
        course: CourseData,
        args: CronyConfiguration,
    ):
        self.course = course
        self.args = args
        self.name = name
        self.target = target
        self.subject = subject
        self.path = None
        self.filename = None

    def get_filename(self):
        course_id = clean_filename(self.course["course"]["course_code"])
        name = clean_filename(self.target["name"])
        return f"{self.name}_{course_id}_{name}.{self.extension}"

    def get_path(self):
        return os.path.join(self.args["output"], self.filename)

    def output(self):
        raise NotImplementedError(
            "Subclasses must implement the output method to generate the report."
        )

    def start(self):
        pass

    def __str__(self):
        return f"Report for {self.target['name']}"

    def __repr__(self):
        return f"Report({self.name!r}, {self.target['name']!r}, {self.course!r})"


class PdfReport(Report):
    maintype = "pdf"
    subtype = "pdf"
    extension = "pdf"

    def __init__(
        self,
        name: str,
        subject: str,
        target: User,
        course: CourseData,
        args: CronyConfiguration,
        pdf: FPDF = None,
    ):
        super().__init__(name, subject, target, course, args)
        self.pdf = pdf

    def output(self):
        self.filename = self.get_filename()
        self.path = self.get_path()
        self.pdf.output(self.path)


class XlsxReport(Report):
    maintype = "xlsx"
    subtype = "xlsx"
    extension = "xlsx"

    def __init__(
        self,
        name: str,
        subject: str,
        target: User,
        course: CourseData,
        args: CronyConfiguration,
    ):
        super().__init__(name, subject, target, course, args)
        self.xlsx = None

    def start(self):
        self.filename = self.get_filename()
        self.path = self.get_path()
        self.xlsx = xlsxwriter.Workbook(self.get_path())
        return self.xlsx

    def output(self):
        self.xlsx.close()


class ReportSet:
    def __init__(self, course: CourseData, args: CronyConfiguration):
        self.course = course
        self.args = args
        self.reports = []

    def extend(self, reports: list[Report]):
        self.reports.extend(reports)

    def output(self):
        # consolidate targets across reports?
        for report in self.reports:
            report.output()

    def __str__(self):
        return (
            f"ReportSet for {self.course['course']['id']} ({len(self.reports)} reports)"
        )

    def __repr__(self):
        return f"ReportSet({self.course['course']['id']}, {self.reports!r})"
