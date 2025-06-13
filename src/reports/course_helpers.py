from typing import Literal, get_args

from canvas_data import CourseData, User, GradingStatus, Submission, Group, NOT_CRITICAL
from canvas_request import days_between, past_date

RECENTLY_THRESHOLD = 3  # days
ANCIENT_THRESHOLD = 7  # days


def get_staff_for_student(course: CourseData) -> dict[int, list[User]]:
    """
    Get each TA mapped to their list of students
    """
    staff_for_student: dict[int, list[User]] = {}
    for group_name, staff in course["cohorts"].items():
        for ta in staff:
            students = course["group_memberships"][group_name]
            for student in students:
                if student["id"] not in staff_for_student:
                    staff_for_student[student["id"]] = []
                staff_for_student[student["id"]].append(ta)
    return staff_for_student


def make_graded_piles(course: CourseData):
    # Get each TA mapped to their list of students
    staff_for_student = get_staff_for_student(course)

    # Process each submission, add it to our piles if ungraded
    ta_students_pile: dict[int, dict[GradingStatus, list[Submission]]] = {}
    ta_graded_pile: dict[int, list[Submission]] = {}
    big_pile: dict[GradingStatus, set[int]] = {
        g: set() for g in get_args(GradingStatus)
    }
    for submission in course["submissions"].values():
        assignment = submission["assignment"]
        student = submission["user"]
        staff = staff_for_student.get(student["id"], [])
        grader = submission["grader"]

        # Already machine graded
        if (
            grader
            and isinstance(grader, int)
            and submission["workflow_state"] == "graded"
        ):
            continue

        for ta in staff:
            status = classify_submission(submission, course["group_membership_ids"])
            if ta["id"] not in ta_students_pile:
                ta_students_pile[ta["id"]] = {g: [] for g in get_args(GradingStatus)}
            ta_students_pile[ta["id"]][status].append(submission)
            grader_id = grader["id"] if grader else None
            if grader_id not in ta_graded_pile:
                ta_graded_pile[grader_id] = []
            ta_graded_pile[grader_id].append(submission)
            big_pile[status].add(submission["id"])

    return big_pile, ta_students_pile, ta_graded_pile


def make_ungraded_piles(course):
    """
    Ignores anything which is already graded.
    """
    grader_piles: dict[int, list[Submission]] = {}
    all_graded: list[Submission] = []
    for submission in course["submissions"].values():
        grader = submission["grader"]
        # Only deal with graded
        if submission["workflow_state"] != "graded":
            continue
        # Machine graded
        if grader and isinstance(grader, int):
            continue
        if grader is None:
            continue

        if grader["id"] not in grader_piles:
            grader_piles[grader["id"]] = []
        grader_piles[grader["id"]].append(submission)
        all_graded.append(submission)

    return all_graded, grader_piles


def make_grading_piles(course):
    """
    Makes grading piles for each TA, and a big pile of all ungraded submissions.
    """
    # Get each TA mapped to their list of students
    staff_for_student = get_staff_for_student(course)

    # Process each submission, add it to our piles if ungraded
    ta_grading_piles: dict[int, dict[GradingStatus, list[Submission]]] = {}
    big_pile: dict[GradingStatus, set[int]] = {
        g: set() for g in get_args(GradingStatus)
    }
    for submission in course["submissions"].values():
        assignment = submission["assignment"]
        student = submission["user"]
        staff = staff_for_student.get(student["id"], [])
        grader = submission["grader"]

        # Already machine graded
        if (
            grader
            and isinstance(grader, int)
            and submission["workflow_state"] == "graded"
        ):
            continue

        for ta in staff:
            status = classify_submission(submission, course["group_membership_ids"])
            if ta["id"] not in ta_grading_piles:
                ta_grading_piles[ta["id"]] = {g: [] for g in get_args(GradingStatus)}
            ta_grading_piles[ta["id"]][status].append(submission)
            big_pile[status].add(submission["id"])

    return big_pile, ta_grading_piles


def classify_submission(submission, groups: dict[int, set[int]]) -> GradingStatus:
    # Skip graded assignments
    if submission["workflow_state"] == "graded":
        return "graded"
    # Check attempt status
    attempted = (submission["attempt"] and submission["attempt"] > 1) or submission[
        "grade"
    ]
    # Submitted late
    if submission["late"]:
        if attempted:
            return "resubmitted (late)"
        else:
            return "not yet graded (late)"
    # Not yet submitted
    elif submission["missing"] or not submission["submitted_at"]:
        availability = classify_availability(submission, groups)
        if availability == "locked":
            return "missed lock date"
        elif availability == "past due":
            return "missed due date"
        elif availability == "open":
            return "in progress"
        return "future assignments"
    # Submitted on time, not yet graded
    elif submission["submitted_at"]:
        availability = classify_availability(submission, groups)
        if availability == "locked":
            if attempted:
                return "resubmitted (ready)"
            else:
                return "not yet graded (ready)"
        else:
            if attempted:
                return "resubmitted (early)"
            else:
                return "not yet graded (early)"
    return "unknown"


def check_recency(*submissions: Submission) -> tuple[int, int]:
    recent, ancient = 0, 0
    for submission in submissions:
        if not submission["submitted_at"]:
            continue
        grade_delay = days_old(submission)
        if grade_delay > ANCIENT_THRESHOLD:
            ancient += 1
        elif grade_delay < RECENTLY_THRESHOLD:
            recent += 1
    return recent, ancient


def days_old(submission: Submission) -> int:
    if not submission["submitted_at"]:
        return 0
    return days_between(submission["submitted_at"], submission["graded_at"])


def classify_availability(submission: Submission, groups: dict[int, set[int]]) -> str:
    assignment = submission["assignment"]
    if assignment["overrides"]:
        submitter_id = submission["user"]["id"]
        sections = {
            enrolled["course_section_id"]
            for enrolled in submission["user"]["enrollments"]
        }
        # First check for per-student overrides
        for override in assignment["overrides"]:
            if "student_ids" in override:
                if submitter_id in override["student_ids"]:
                    return check_availability(override)
        # Next separately check for any group overrides
        for override in assignment["overrides"]:
            if "group_id" in override:
                if override["group_id"] in groups:
                    if submitter_id in groups[override["group_id"]]:
                        return check_availability(override)
        # Then separately check for any course section overrides
        for override in assignment["overrides"]:
            if "course_section_id" in override:
                if override["course_section_id"] in sections:
                    return check_availability(override)
    # Finally fall back on assignment's settings
    return check_availability(assignment)


def check_availability(availability):
    if availability.get("lock_at") and past_date(availability["lock_at"]):
        return "locked"
    if availability.get("due_at") and past_date(availability["due_at"]):
        return "past due"
    if availability.get("unlock_at") and past_date(availability["unlock_at"]):
        return "open"
    return "future"
