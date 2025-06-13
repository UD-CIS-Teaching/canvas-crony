from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args
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
    make_ungraded_piles,
)
from reports.report_tools import make_table
from reports.report_types import Report, PdfReport
from reports.stats_helpers import f, iqr, get_normal_stats

RECENTLY_THRESHOLD = 3  # days
ANCIENT_THRESHOLD = 7  # days


def make_score_reports(course: CourseData, args: CronyConfiguration) -> list[Report]:
    reports = []

    # Get each TA mapped to their list of students
    staff_for_student = get_staff_for_student(course)

    # Process each submission, add it to our piles if ungraded
    all_graded, grader_piles = make_ungraded_piles(course)

    # Make a PDF for each TA
    staff_reports, staff_tables = make_score_reports_staff(
        course, grader_piles, len(all_graded), args
    )
    # Make a PDF for the instructor
    instructor_reports = make_score_reports_instructor(
        course, all_graded, staff_tables, args
    )

    reports.extend(staff_reports)
    reports.extend(instructor_reports)
    return reports


@dataclass
class StaffTables:
    extents: list[list[str]]
    iqr: list[list[str]]
    normal_stats: list[list[str]]


def make_score_reports_staff(
    course: CourseData,
    grader_piles: dict[int, list[Submission]],
    total_graded: int,
    args: CronyConfiguration,
):
    staff_reports = []
    staff_tables = {}
    for ta_id, graded in grader_piles.items():
        ta = course["users"][ta_id]
        # PDF
        staff_pdf = FPDF()
        staff_pdf.add_page()
        # Page Header
        staff_pdf.set_font("helvetica", "B", size=22)
        staff_pdf.write(txt=f"Staff Score Report\n")
        staff_pdf.set_font("helvetica", size=18)
        staff_pdf.write(txt=course["course"]["name"] + "\n")
        staff_pdf.write(txt=ta["name"] + "\n")
        staff_pdf.ln()
        # Summarize data
        staff_pdf.set_font("helvetica", size=14)

        # Group by graded
        graded_by_assignment = {
            None: list(graded),
        }
        for submission in graded:
            assignment_id = submission["assignment"]["id"]
            if assignment_id not in graded_by_assignment:
                graded_by_assignment[assignment_id] = []
            graded_by_assignment[assignment_id].append(submission)

        for assignment_id, graded in graded_by_assignment.items():
            if not graded:
                continue
            assignment = graded[0]["assignment"]
            # Header information
            staff_pdf.set_font(size=18)
            if assignment_id is None:
                staff_pdf.write(txt="All Assignments:\n")
                staff_pdf.set_font(size=12)
            else:
                staff_pdf.write(txt=assignment["name"] + ":\n")
                staff_pdf.set_font(size=12)
                staff_pdf.write(txt=f"Graded: {len(graded)}\n")
                staff_pdf.write(txt=f"Total Points: {assignment['points_possible']}\n")
            if assignment_id not in staff_tables:
                staff_tables[assignment_id] = {}

            # Extents (Zeros and Perfects)
            zeroes = [sub for sub in graded if sub["score"] == 0]
            perfects = [
                sub
                for sub in graded
                if sub["score"] == sub["assignment"]["points_possible"]
            ]
            extents_table = [
                ["", "Number", "Percent", "Out of Total"],
                [
                    "Graded Submissions",
                    str(len(graded)),
                    f"{f(100*len(graded)/total_graded)}%",
                    str(total_graded),
                ],
                [
                    "Zeroes",
                    str(len(zeroes)),
                    f"{f(100*len(zeroes)/len(graded))}%",
                    str(len(graded)),
                ],
                [
                    "Perfects",
                    str(len(perfects)),
                    f"{f(100*len(perfects)/len(graded))}%",
                    str(len(graded)),
                ],
            ]
            make_table(staff_pdf, extents_table)

            all_scores = [
                (
                    100 * sub["score"] / sub["assignment"].get("points_possible", 0)
                    if sub["assignment"]["points_possible"] and sub["score"]
                    else sub["score"] or 0
                )
                for sub in graded
            ]
            nonzero_scores = [
                (100 * sub["score"] / sub["assignment"]["points_possible"])
                for sub in graded
                if sub["score"] and sub["assignment"]["points_possible"]
            ]

            # IQR (with and without zeroes)
            staff_pdf.ln()
            iqr_table = [
                ["", "Min", "25%", "Median", "75%", "Max"],
                ["All Scores", *iqr(all_scores)],
                ["Non-Zero Scores", *iqr(nonzero_scores)],
            ]
            make_table(staff_pdf, iqr_table)

            # Mean, Variance, Std Dev
            staff_pdf.ln()
            normal_stats = [
                ["", "Mean", "Variance", "Std Dev"],
                ["All Scores", *get_normal_stats(all_scores)],
                ["Non-Zero Scores", *get_normal_stats(nonzero_scores)],
            ]
            make_table(staff_pdf, normal_stats)
            staff_pdf.ln()

            staff_tables[assignment_id][ta_id] = StaffTables(
                extents_table, iqr_table, normal_stats
            )

        # Grade distribution histogram
        # TODO: Make the histogram and embed it
        # Wrap it up
        staff_reports.append(
            PdfReport(
                "score",
                "{course_name} Score Report for {user_name}",
                ta,
                course,
                args,
                staff_pdf,
            )
        )
    return staff_reports, staff_tables


def combine_tables(
    tables: list[list[list[str]]], names: list[str]
) -> dict[str, list[list[str]]]:
    first_row = tables[0][0]
    taken_tables = {}
    for row_id in range(1, len(tables[0])):
        new_table = [first_row]
        table_name = tables[0][row_id][0]
        for table_id, name in enumerate(names):
            taken_row = list(tables[table_id][row_id])
            taken_row[0] = name
            new_table.append(taken_row)
        taken_tables[table_name] = new_table
    return taken_tables


def make_score_reports_instructor(
    course: CourseData,
    all_graded: list[Submission],
    assignment_staff_tables: dict[int, dict[int, StaffTables]],
    args: CronyConfiguration,
):
    instructor_reports = []
    for instructor in course["instructors"]:
        instructor_pdf = FPDF()
        instructor_pdf.add_page()
        # Page Header
        instructor_pdf.set_font("helvetica", "B", size=22)
        instructor_pdf.write(txt=f"Instructor Score Report\n")
        instructor_pdf.set_font("helvetica", size=18)
        instructor_pdf.write(txt=course["course"]["name"] + "\n")
        instructor_pdf.write(txt=instructor["name"] + "\n")
        instructor_pdf.ln()
        # Overall summary
        instructor_pdf.set_font("helvetica", size=12)
        #   TA Sts
        instructor_pdf.write(txt=f"Staff: {len(assignment_staff_tables)}\n")
        instructor_pdf.write(txt=f"Groups: {len(course['groups'])}\n")
        instructor_pdf.write(txt=f"Students: {len(course['students'])}\n")
        instructor_pdf.write(txt=f"Assignments: {len(course['assignments'])}\n")
        expected_submissions = len(course["students"]) * len(course["assignments"])
        instructor_pdf.write(
            txt=f"Submissions: {len(course['submissions'])} ({expected_submissions} possible)\n"
        )
        instructor_pdf.write(
            txt=f"Graded: {len(all_graded)} ({len(all_graded)/expected_submissions:.2%})\n"
        )
        instructor_pdf.ln()

        # List out the TA's progress
        for assignment_id, staff_tables in assignment_staff_tables.items():
            if assignment_id is not None:
                assignment = course["assignments"][assignment_id]
                instructor_pdf.set_font(size=18)
                instructor_pdf.write(txt=assignment["name"] + ":\n")
                instructor_pdf.set_font(size=12)
                instructor_pdf.write(
                    txt=f"Total Points: {assignment['points_possible']}\n"
                )
            instructor_pdf.ln()
            for stat_name, stat_field in [
                ("Extents", "extents"),
                ("IQR of Percentage Scores", "iqr"),
                ("Normal Stats of Percentage Scores", "normal_stats"),
            ]:
                instructor_pdf.set_font(size=14)
                instructor_pdf.write(txt=stat_name + ":\n")
                names = [course["users"][ta_id]["name"] for ta_id in staff_tables]
                taken_tables = combine_tables(
                    [
                        getattr(staff_tables[ta_id], stat_field)
                        for ta_id in staff_tables
                    ],
                    names,
                )
                instructor_pdf.set_font(size=12)
                for table_name, table in taken_tables.items():
                    instructor_pdf.write(txt=table_name + ":\n")
                    make_table(instructor_pdf, table)
                    instructor_pdf.ln()
            instructor_pdf.add_page()

        # Wrap it up
        instructor_reports.append(
            PdfReport(
                "score",
                "{course_name} Instructor Score Report for {user_name}",
                instructor,
                course,
                args,
                instructor_pdf,
            )
        )
    return instructor_reports
