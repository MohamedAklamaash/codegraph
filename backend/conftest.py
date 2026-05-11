"""Empty conftest — test bootstrap stubs live at the top of `core/test_settings.py`
because pytest-django's `pytest_load_initial_conftests` runs `django.setup()`
*before* the rootdir conftest is loaded.
"""
