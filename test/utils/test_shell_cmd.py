import sys

from src.utils.shell_cmd import shell_cmd_live


def test_shell_cmd_live_closes_stdin_after_input():
    command = (
        f'{sys.executable} -c "import sys; data = sys.stdin.read(); '
        'print(data.decode() if isinstance(data, bytes) else data)"'
    )

    ret, out, err = shell_cmd_live(command, cap_in=b"hello", cap_out=True, cap_err=True)

    assert ret == 0
    assert out == ["hello"]
    assert err is None
