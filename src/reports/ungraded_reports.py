from __future__ import annotations
import math

from fpdf import FPDF

from canvas_data import CourseData, User, GradingStatus, Submission, Group, NOT_CRITICAL
from canvas_request import days_between, past_date
from cli_config import CronyConfiguration
from reports.course_helpers import (
    get_staff_for_student,
    classify_submission,
    check_recency,
    days_old,
    make_grading_piles,
)
from reports.report_tools import make_table
from reports.report_types import Report


def make_ungraded_reports(course: CourseData, args: CronyConfiguration) -> list[Report]:
    reports = []
    staff_reports = {}

    staff_for_student = get_staff_for_student(course)

    big_pile, ta_grading_piles = make_grading_piles(course)

    # Make a PDF for each TA
    staff_reports = make_ungraded_reports_staff(
        course, big_pile, ta_grading_piles, args
    )
    # Make a PDF for the instructor
    instructor_reports = make_ungraded_reports_instructor(
        course, big_pile, ta_grading_piles, args
    )

    reports.extend(staff_reports)
    reports.extend(instructor_reports)
    return reports


def make_ungraded_reports_staff(
    course: CourseData,
    big_pile: dict[GradingStatus, set[int]],
    ta_grading_piles: dict[int, dict[GradingStatus, list[Submission]]],
    args: CronyConfiguration,
):
    staff_reports = []
    for ta_id, piles in ta_grading_piles.items():
        ta = course["users"][ta_id]
        # PDF
        staff_pdf = FPDF()
        staff_pdf.add_page()
        # Page Header
        staff_pdf.set_font("helvetica", "B", size=22)
        staff_pdf.write(txt=f"Staff Ungraded Report\n")
        staff_pdf.set_font("helvetica", size=18)
        staff_pdf.write(txt=course["course"]["name"] + "\n")
        staff_pdf.write(txt=ta["name"] + "\n")
        staff_pdf.ln()
        # Summarize data
        staff_pdf.set_font("helvetica", size=14)
        table_data = [["", "Total", "Past 3 Days", "Past Week", "Older"]]
        for status, pile in piles.items():
            if pile:
                recent, ancient = check_recency(*pile)
                normal = len(pile) - recent - ancient
                table_data.append(
                    [
                        status.title(),
                        str(len(pile)),
                        str(recent),
                        str(normal),
                        str(ancient),
                    ]
                )
                # staff_pdf.write(txt=f"{}: {len(pile)} total"
                #                    f" ({recent} within past 3 days, {normal} within last week, {ancient} older)\n")
        make_table(staff_pdf, table_data)
        staff_pdf.ln()
        # List all the actual links
        staff_pdf.set_font("helvetica", size=14)
        list_actual_links(staff_pdf, piles, course)
        """
        flat_pile = sorted([(days_old(submission), status, submission)
                            for status, pile in piles.items()
                            for submission in pile
                            if status not in NOT_CRITICAL],
                           key=lambda item: (-item[0], item[1]))
        previous_age = None
        if not flat_pile:
            staff_pdf.write(txt="You are all caught up on grading! Great work!")
        for age, status, submission in flat_pile:
            log_age = round(math.log2(age)) if age > 0 else 0
            if previous_age is None or log_age < previous_age:
                previous_age = log_age
                staff_pdf.set_font(size=18)
                staff_pdf.write(txt=f"{age} day{'s' if age > 1 else ''} ago:\n")
                staff_pdf.set_font(size=14)
            assignment = submission['assignment']
            url = course['speed_grader_url'].format(course_id=course['id'], assignment_id=assignment['id'],
                                                    user_id=submission['user']['id'])
            staff_pdf.write(txt="   ")
            staff_pdf.set_font(style="U")
            staff_pdf.write(txt=f"{assignment['name']}: {submission['user']['name']}", link=url)
            staff_pdf.set_font()
            staff_pdf.ln()
        """
        # Wrap it up
        staff_reports.append(
            Report(
                "ungraded",
                "{course_name} Grading Report for {user_name}",
                ta,
                staff_pdf,
                course,
                args,
            )
        )
    return staff_reports


def list_actual_links(staff_pdf, piles, course: CourseData):
    flat_pile = sorted(
        [
            (days_old(submission), status, submission)
            for status, pile in piles.items()
            for submission in pile
            if status not in NOT_CRITICAL
        ],
        key=lambda item: (-item[0], item[1]),
    )
    previous_age = None
    if not flat_pile:
        staff_pdf.write(txt="You are all caught up on grading! Great work!")
    for age, status, submission in flat_pile:
        log_age = round(math.log2(age)) if age > 0 else 0
        if previous_age is None or log_age < previous_age:
            previous_age = log_age
            staff_pdf.set_font(size=18)
            staff_pdf.write(txt=f"{age} day{'s' if age > 1 else ''} ago:\n")
            staff_pdf.set_font(size=14)
        assignment = submission["assignment"]
        url = course["speed_grader_url"].format(
            course_id=course["id"],
            assignment_id=assignment["id"],
            user_id=submission["user"]["id"],
        )
        staff_pdf.write(txt="   ")
        staff_pdf.set_font(style="U")
        staff_pdf.write(
            txt=f"{assignment['name']}: {submission['user']['name']}", link=url
        )
        staff_pdf.set_font()
        staff_pdf.ln()


def make_ungraded_reports_instructor(
    course: CourseData,
    big_pile: dict[GradingStatus, set[int]],
    ta_grading_piles: dict[int, dict[GradingStatus, list[Submission]]],
    args: CronyConfiguration,
):
    instructor_reports = []
    for instructor in course["instructors"]:
        instructor_pdf = FPDF()
        instructor_pdf.add_page()
        # Page Header
        instructor_pdf.set_font("helvetica", "B", size=22)
        instructor_pdf.write(txt=f"Instructor Ungraded Report\n")
        instructor_pdf.set_font("helvetica", size=18)
        instructor_pdf.write(txt=course["course"]["name"] + "\n")
        instructor_pdf.write(txt=instructor["name"] + "\n")
        instructor_pdf.ln()
        # Overall summary
        instructor_pdf.set_font("helvetica", size=12)
        #   TA Sts
        instructor_pdf.write(txt=f"Staff: {len(ta_grading_piles)}\n")
        instructor_pdf.write(txt=f"Groups: {len(course['groups'])}\n")
        instructor_pdf.write(txt=f"Students: {len(course['students'])}\n")
        instructor_pdf.write(txt=f"Assignments: {len(course['assignments'])}\n")
        expected_submissions = len(course["students"]) * len(course["assignments"])
        instructor_pdf.write(
            txt=f"Submissions: {len(course['submissions'])} ({expected_submissions} possible)\n"
        )
        for status, pile in big_pile.items():
            if pile:
                instructor_pdf.write(txt=f"{status.title()}: {len(pile)}\n")
        instructor_pdf.ln()

        # List out the TA's progress
        for ta_id, piles in ta_grading_piles.items():
            ta = course["users"][ta_id]
            instructor_pdf.write(txt=ta["name"] + ":\n")
            table_data = [["", "Total", "Past 3 Days", "Past Week", "Older"]]
            for status, pile in piles.items():
                if pile:
                    recent, ancient = check_recency(*pile)
                    normal = len(pile) - recent - ancient
                    table_data.append(
                        [
                            status.title(),
                            str(len(pile)),
                            str(recent),
                            str(normal),
                            str(ancient),
                        ]
                    )
                    # instructor_pdf.write(txt=f"  {status.title()}: {len(pile)} ({recent} recently, {ancient} more "
                    #                         f"than a week ago)\n")
            make_table(instructor_pdf, table_data)
            instructor_pdf.ln()

        instructor_pdf.set_font("helvetica", "B", size=22)
        instructor_pdf.write(txt="Individual Links:\n")
        for ta_id, piles in ta_grading_piles.items():
            ta = course["users"][ta_id]
            instructor_pdf.set_font("helvetica", "B", size=14)
            instructor_pdf.write(txt=ta["name"] + ":\n")
            instructor_pdf.set_font("helvetica", size=12)
            list_actual_links(instructor_pdf, piles, course)
            instructor_pdf.ln()
        # Wrap it up
        instructor_reports.append(
            Report(
                "ungraded",
                "{course_name} Instructor Grading Report for {user_name}",
                instructor,
                instructor_pdf,
                course,
                args,
            )
        )
    return instructor_reports
