from dataclasses import dataclass
from typing import Literal, get_args
import math

from fpdf import FPDF
import xlsxwriter

from canvas_data import CourseData, User, GradingStatus, Submission, Group, NOT_CRITICAL
from canvas_request import days_between, past_date
from cli_config import CronyConfiguration
from reports.course_helpers import (
    get_staff_for_student,
    classify_submission,
    check_recency,
    days_old,
    make_grading_piles,
    make_graded_piles,
)
from reports.report_tools import make_table
from reports.report_types import Report, PdfReport, XlsxReport
from reports.stats_helpers import f

"""
Long term things to add:
- How many did they grade of their own students?
- How many did they grade of other students?
- How many did they grade in total?
- How many did they grade in [time frame]?
- What was the average time to grade?
- What was the average score given?
"""


def make_grading_reports(course: CourseData, args: CronyConfiguration) -> list[Report]:
    """
    Create grading reports for the course.
    :param course: The course data.
    :param args: The CLI arguments.
    :return: A list of reports.
    """
    reports = []

    # Get each TA mapped to their list of students
    all_graded, ta_students_pile, ta_graded_pile = make_graded_piles(course)

    instructor_reports = make_grading_reports_instructor(
        course, all_graded, ta_students_pile, ta_graded_pile, args
    )

    reports.extend(instructor_reports)

    return reports


MAIN_PAGE_HEADERS = [
    "TA",
    "Total Graded",
    "Total Assigned",
    "Work Difference",
    "Graded within 1 week",
    "Graded after 2 weeks",
]


def make_grading_reports_instructor(
    course: CourseData,
    all_graded: list[Submission],
    ta_students_pile: dict[User, list[Submission]],
    ta_graded_pile: dict[User, list[Submission]],
    args: CronyConfiguration,
) -> list[Report]:
    """
    Create grading reports for the instructor.
    :param course: The course data.
    :param all_graded: All graded submissions.
    :param ta_students_pile: TA to students mapping.
    :param ta_graded_pile: TA to graded submissions mapping.
    :param args: The CLI arguments.
    :return: A list of reports.
    """
    reports = []

    for instructor in course["instructors"]:
        new_report = XlsxReport(
            "grading",
            "{course_name} Grading Report for {user_name}",
            instructor,
            course,
            args,
        )
        workbook = new_report.start()

        worksheet = workbook.add_worksheet("Grading Report")

        for col_num, header in enumerate(MAIN_PAGE_HEADERS):
            worksheet.write(0, col_num, header)

        for row_num, ta in enumerate(course["staff"].values(), start=1):
            worksheet.write(row_num, 0, ta["name"])

            graded_submissions = ta_graded_pile.get(ta["id"], [])
            worksheet.write(row_num, 1, len(graded_submissions))

            assigned_submissions_by_status = ta_students_pile.get(ta["id"], {})
            all_assigned_submissions = [
                submissions
                for status, submissions in assigned_submissions_by_status.items()
            ]
            assigned_submissions = sum(
                len(submissions) for submissions in all_assigned_submissions
            )
            worksheet.write(row_num, 2, assigned_submissions)

            ungraded_submissions = assigned_submissions - len(graded_submissions)
            worksheet.write(row_num, 3, ungraded_submissions)

            graded_within_week = (
                100
                * sum(
                    1
                    for submission in graded_submissions
                    if days_between(submission["graded_at"], submission["submitted_at"])
                    <= 7
                )
                // len(graded_submissions)
                if graded_submissions
                else 0
            )
            worksheet.write(row_num, 4, f"{f(graded_within_week)}%")

            graded_after_two_weeks = (
                100
                * sum(
                    1
                    for submission in graded_submissions
                    if days_between(submission["graded_at"], submission["submitted_at"])
                    > 14
                )
                // len(graded_submissions)
                if graded_submissions
                else 0
            )
            worksheet.write(row_num, 5, f"{f(graded_after_two_weeks)}%")

        # for row_num, (ta_id, graded_pile) in enumerate(ta_graded_pile.items(), start=1):
        #     ta = course["users"].get(ta_id)
        #     if ta_id is None:
        #         worksheet.write(row_num, 0, f"Not yet graded")
        #         worksheet.write(row_num, 1, len(graded_pile))
        #         continue
        #     if not ta:
        #         worksheet.write(row_num, 0, f"TA {ta_id} not found: {ta_id}")
        #         worksheet.write(row_num, 1, len(graded_pile))
        #         continue
        #
        #     worksheet.write(row_num, 0, ta["name"])
        #     worksheet.write(row_num, 1, len(graded_pile))

        reports.append(new_report)

    return reports
