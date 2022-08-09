from typing import Literal, get_args
import math

from fpdf import FPDF

from canvas_data import CourseData, User, GradingStatus, Submission
from canvas_request import days_between
from cli_config import CronyConfiguration
from reports.report_types import Report


RECENTLY_THRESHOLD = 3 # days
ANCIENT_THRESHOLD = 7 # days


def make_ungraded_reports(course: CourseData, args: CronyConfiguration) -> list[Report]:
    reports = []
    staff_reports = {}

    # Get each TA mapped to their list of students
    staff_for_student: dict[int, list[User]] = {}
    for group_name, staff in course['cohorts'].items():
        for ta in staff:
            students = course['group_memberships'][group_name]
            for student in students:
                if student['id'] not in staff_for_student:
                    staff_for_student[student['id']] = []
                staff_for_student[student['id']].append(ta)

    # Process each submission, add it to our piles if ungraded
    ta_grading_piles: dict[int, dict[GradingStatus, list[Submission]]] = {}
    big_pile: dict[GradingStatus, set[int]] = {g: set() for g in get_args(GradingStatus)}
    for submission in course['submissions'].values():
        assignment = submission['assignment']
        student = submission['user']
        staff = staff_for_student.get(student['id'], [])
        grader = submission['grader']

        # Already machine graded
        if grader and isinstance(grader, int) and submission['workflow_state'] == 'graded':
            continue

        for ta in staff:
            status = classify_submission(submission)
            if ta['id'] not in ta_grading_piles:
                ta_grading_piles[ta['id']] = {g: [] for g in get_args(GradingStatus)}
            ta_grading_piles[ta['id']][status].append(submission)
            big_pile[status].add(submission['id'])

    # Make a PDF for each TA
    staff_reports = make_ungraded_reports_staff(course, big_pile, ta_grading_piles, args)
    # Make a PDF for the instructor
    instructor_reports = make_ungraded_reports_instructor(course, big_pile, ta_grading_piles, args)

    reports.extend(staff_reports)
    reports.extend(instructor_reports)
    return reports


def make_ungraded_reports_staff(course: CourseData, big_pile: dict[GradingStatus, set[int]],
                                ta_grading_piles: dict[int, dict[GradingStatus, list[Submission]]],
                                args: CronyConfiguration):
    staff_reports = []
    for ta_id, piles in ta_grading_piles.items():
        ta = course['users'][ta_id]
        # PDF
        staff_pdf = FPDF()
        staff_pdf.add_page()
        # Page Header
        staff_pdf.set_font('helvetica', "B", size=22)
        staff_pdf.write(txt=f"Staff Ungraded Report\n")
        staff_pdf.set_font('helvetica', size=18)
        staff_pdf.write(txt=course['course']['name']+"\n")
        staff_pdf.write(txt=ta['name']+"\n")
        staff_pdf.ln()
        # Summarize data
        for status, pile in piles.items():
            if pile:
                recent, ancient = check_recency(*pile)
                staff_pdf.write(txt=f"{status.title()}: {len(pile)} ({recent} recently, {ancient} more "
                                    f"than a week ago)\n")
        staff_pdf.ln()
        # List all the actual links
        staff_pdf.set_font('helvetica', size=14)
        flat_pile = sorted([(days_old(submission), status, submission)
                            for status, pile in piles.items()
                            for submission in pile
                            if status in ("missing", "graded")],
                           key= lambda item: (-item[0], item[1]))
        previous_age = None
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
        # Wrap it up
        staff_reports.append(Report("ungraded", ta, staff_pdf, course, args))
    return staff_reports

def make_ungraded_reports_instructor(course: CourseData, big_pile: dict[GradingStatus, set[int]],
                                     ta_grading_piles: dict[int, dict[GradingStatus, list[Submission]]],
                                     args: CronyConfiguration):
    instructor_reports = []
    for instructor in course['instructors']:
        instructor_pdf = FPDF()
        instructor_pdf.add_page()
        # Page Header
        instructor_pdf.set_font('helvetica', "B", size=22)
        instructor_pdf.write(txt=f"Instructor Ungraded Report\n")
        instructor_pdf.set_font('helvetica', size=18)
        instructor_pdf.write(txt=course['course']['name']+"\n")
        instructor_pdf.write(txt=instructor['name'] + "\n")
        instructor_pdf.ln()
        # Overall summary
        instructor_pdf.set_font('helvetica', size=12)
        for status, pile in big_pile.items():
            if pile:
                instructor_pdf.write(txt=f"{status.title()}: {len(pile)}\n")
        instructor_pdf.ln()

        # List out the TA's progress
        for ta_id, piles in ta_grading_piles.items():
            ta = course['users'][ta_id]
            instructor_pdf.write(txt=ta['name'] + ":\n")
            for status, pile in piles.items():
                if pile:
                    recent, ancient = check_recency(*pile)
                    instructor_pdf.write(txt=f"  {status.title()}: {len(pile)} ({recent} recently, {ancient} more "
                                             f"than a week ago)\n")
            instructor_pdf.ln()
        # Wrap it up
        instructor_reports.append(Report("ungraded", instructor, instructor_pdf, course, args))
    return instructor_reports

def classify_submission(submission) -> GradingStatus:
    # Skip graded assignments
    if submission['workflow_state'] == 'graded':
        return 'graded'
    # Check attempt status
    attempted = (submission['attempt'] and submission['attempt'] > 1) or submission['grade']
    # Submitted late
    if submission['late']:
        if attempted:
            return 'resubmitted'
        else:
            return 'ungraded'
    # Not yet submitted
    elif submission['missing']:
        return 'missing'
    # Submitted early, not yet graded
    elif submission['submitted_at']:
        if attempted:
            return 'resubmitted early'
        else:
            return 'ungraded early'
    return 'missing'


def check_recency(*submissions: list[Submission]) -> tuple[int, int]:
    recent, ancient = 0, 0
    for submission in submissions:
        if not submission['submitted_at']:
            continue
        grade_delay = days_old(submission)
        if grade_delay > ANCIENT_THRESHOLD:
            ancient += 1
        elif grade_delay < RECENTLY_THRESHOLD:
            recent += 1
    return recent, ancient


def days_old(submission: Submission) -> int:
    if not submission['submitted_at']:
        return 0
    return days_between(submission['submitted_at'], submission['graded_at'])