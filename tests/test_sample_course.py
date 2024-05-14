"""
"""
import canvas_crony


def test_sample_course():
    reports = canvas_crony.canvas_crony({
        #"course": "../course_data/s23_cisc108.yaml",
        "course": "../course_data/test_ct_dev.yaml",
        "courses": "",
        "email": False,
        "only": "acbart@udel.edu",
        #"settings": "../secrets/settings.yaml",
        "settings": "../secrets/test_settings.yaml",
        "output": "../build/",
        "cache": True,
        "progress": True,
        "log": "../logs/run.log"
    })
    assert True
