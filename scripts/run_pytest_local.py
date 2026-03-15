import sys

import pytest

rc = pytest.main(['-vv','-s'])
print('PYTEST_EXIT_CODE', rc)
sys.exit(rc)
