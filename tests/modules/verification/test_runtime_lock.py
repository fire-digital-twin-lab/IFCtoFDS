from scripts.check_verification_environment import check_requirements


def test_runtime_lock_checks_only_the_current_python_marker_branch():
    checks = check_requirements(
        'numpy==2.2.6; python_full_version < "3.11"\nnumpy==2.5.4; python_full_version >= "3.12"',
        {"numpy": "2.5.4"}, {"python_full_version": "3.12.10"})
    assert len(checks) == 1
    assert checks[0]["status"] == "PASS"


def test_missing_or_changed_locked_dependencies_fail():
    checks = check_requirements("numpy==2.5.4\nscipy==1.18.1", {"numpy": "2.4.6"})
    assert [c["status"] for c in checks] == ["FAIL", "FAIL"]
