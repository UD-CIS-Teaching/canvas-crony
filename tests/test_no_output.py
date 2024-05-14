"""
"""

import canvas_crony


def test_check_stats():
    reports = canvas_crony.canvas_crony(
        {
            # "course": "../course_data/s23_cisc108.yaml",
            "course": "../course_data/test_ct_dev.yaml",
            "courses": "",
            "email": False,
            "output": False,
            "only": "acbart@vt.edu",
            # "settings": "../secrets/settings.yaml",
            "settings": "../secrets/test_settings.yaml",
            "cache": True,
            "progress": True,
            "log": "",
            "safe": False,
        }
    )
    print([repr(r) for r in reports[0].reports])
    assert True
