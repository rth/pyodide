import pytest


def test_scipy_import(selenium_standalone):
    from selenium.common.exceptions import JavascriptException
    selenium = selenium_standalone
    selenium.load_package("scipy")
    selenium.run("""
        import scipy
        """)

    # supported modules
    for module in ['constants']:
        selenium.run(f"import scipy.{module}")

    # not yet built modules
    for module in ['cluster',  # needs sparse
                   'spatial',  # needs sparse
                   'sparse',
                   'integrate',  # needs special
                   'interpolate',  # needs linalg
                   'linalg',
                   'misc',   # needs special
                   'odrpack',
                   'signal',  # needs special
                   'image',  # needs special
                   'stats',  # need special
                   'optimize',  # needs minpack2
                   'fftpack',
                   'special']:
        with pytest.raises(JavascriptException) as err:
            selenium.run(f"import scipy.{module}")
        assert ('ModuleNotFoundError' in str(err.value)
                or 'ImportError' in str(err.value))

    print(selenium.logs)
