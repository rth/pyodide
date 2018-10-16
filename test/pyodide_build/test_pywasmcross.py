from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parents[2]))

from pyodide_build.pywasmcross import f2c  # noqa: E402


def _args_wrapper(func):
    """Convert function to take / return a string instead of a
    list of arguments

    Also sets pretend=True
    """
    def _inner(line):
        args = line.split()
        res = func(args, pretend=True)
        if hasattr(res, '__len__'):
            return ' '.join(res)
        else:
            return res
    return _inner


f2c_wrap = _args_wrapper(f2c)


def test_f2c():
    assert f2c_wrap('gfortran test.f') == 'gfortran test.c'
    assert f2c_wrap('gcc test.c') is None
    assert f2c_wrap('gfortran --version') is None
    assert f2c_wrap('gfortran --shared -c test.o -o test.so') == \
        'gfortran --shared -c test.o -o test.so'
