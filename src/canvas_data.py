from __future__ import annotations
from typing import TypedDict, Optional, Literal, Union
import os

from settings import yaml_load


class Course(TypedDict):
    """
    The actual canvas course, without other data like students and stuff
    """

    id: int
    name: str
    course_code: str
    workflow_state: Literal["unpublished", "available", "completed", "deleted"]
    created_at: str
    start_at: str
    end_at: str


class EnrollmentGrade(TypedDict):
    html_url: str
    current_grade: str
    current_score: float
    final_grade: str
    final_score: float
    override_grade: str
    override_score: float
    unposted_current_grade: str
    unposted_current_score: float
    unposted_final_grade: str
    unposted_final_score: float


class Enrollment(TypedDict):
    id: int
    user_id: int
    course_section_id: int
    type: Literal[
        "StudentEnrollment",
        "TeacherEnrollment",
        "TaEnrollment",
        "DesignerEnrollment",
        "ObserverEnrollment",
    ]
    created_at: str
    updated_at: str
    end_at: str
    last_activity_at: str
    total_activity_time: int
    grades: EnrollmentGrade


class User(TypedDict):
    id: int
    name: str
    email: str
    enrollments: list[Enrollment]


def clean_user(user: User):
    if "email" not in user:
        return None
    user["email"] = user["email"].lower()
    return user


class Group(TypedDict):
    id: int
    name: str


class AssignmentGroup(TypedDict):
    id: int
    name: str


class AssignmentOverride(TypedDict):
    id: int
    title: str
    # Will have only one of these
    student_ids: list[int]
    course_section_id: int
    group_id: int
    # Should have all of these, though they may be None
    due_at: str
    lock_at: str
    unlock_at: str


class Assignment(TypedDict):
    id: int
    name: str
    due_at: str
    lock_at: str
    unlock_at: str
    html_url: str
    points_possible: float
    published: bool
    assignment_group: AssignmentGroup
    overrides: list[AssignmentOverride]


class Submission(TypedDict):
    id: int
    user: User
    assignment: Assignment
    attempt: int
    grade: str
    score: float
    submission_type: Literal[
        "online_text_entry",
        "online_url",
        "online_upload",
        "media_recording",
        "student_annotation",
    ]
    submitted_at: str
    grader: Union[int, User]
    graded_at: str
    late: bool
    excused: bool
    missing: bool
    late_policy_status: Literal["late", "missing", "extended", "none", None]
    seconds_late: int
    workflow_state: Literal["submitted"]
    redo_request: bool
    html_url: str


class RawCourseData(TypedDict):
    id: int
    # Whether the course should be forced to be active or not; if None then use course time period
    active: Optional[bool]
    cohorts: dict[str, dict[str, list[str]]]
    instructors: list[str]


class CourseData(TypedDict):
    id: int
    active: Optional[bool]
    # Course file Data
    cohorts: dict[str, list[User]]
    instructors: list[User]
    # Pulled data
    course: Course
    users: dict[int, User]
    assignments: dict[int, Assignment]
    submissions: dict[int, Submission]
    assignment_groups: dict[int, AssignmentGroup]
    groups: list[Group]
    group_memberships: dict[str, list[User]]
    group_membership_ids: dict[int, set[int]]
    # Mixed pulled/course file data
    staff: dict[int, User]
    students: dict[int, User]
    speed_grader_url: str


class Report(TypedDict):
    course: CourseData
    path: str


def load_course_data(filename: str) -> RawCourseData:
    return yaml_load(filename)


def load_course_folder(folder: str) -> list[RawCourseData]:
    for filename in os.listdir(folder):
        yield yaml_load(os.path.join(folder, filename))


GradingStatus = Literal[
    "graded",
    "not yet graded (late)",
    "resubmitted (late)",
    "not yet graded (ready)",
    "resubmitted (ready)",
    "not yet graded (early)",
    "resubmitted (early)",
    # 'early resubmission', 'early submission',
    # 'not submitted',
    # 'missing',
    "in progress",
    "missed due date",
    "missed lock date",
    "future assignments",
]

NOT_CRITICAL: set[GradingStatus] = {
    "future assignments",
    "not yet due",
    "graded",
    "missed due date",
    "missed lock date",
    "in progress",
}
