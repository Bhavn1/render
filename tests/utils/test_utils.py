import os
import typing
from pathlib import Path
from typing import Any, List, Union

import pytest
import typer
from packaging import version

from reflex import constants
from reflex.base import Base
from reflex.components.tags import Tag
from reflex.event import EVENT_ARG, EventChain, EventHandler, EventSpec
from reflex.state import State
from reflex.style import Style
from reflex.utils import (
    build,
    format,
    imports,
    prerequisites,
    types,
)
from reflex.utils import exec as utils_exec
from reflex.utils.serializers import serialize
from reflex.vars import BaseVar, Var


def mock_event(arg):
    pass


def get_above_max_version():
    """Get the 1 version above the max required bun version.

    Returns:
        max bun version plus one.

    """
    semantic_version_list = constants.BUN_VERSION.split(".")
    semantic_version_list[-1] = str(int(semantic_version_list[-1]) + 1)  # type: ignore
    return ".".join(semantic_version_list)


V055 = version.parse("0.5.5")
V059 = version.parse("0.5.9")
V056 = version.parse("0.5.6")
VMAXPLUS1 = version.parse(get_above_max_version())


class ExampleTestState(State):
    """Test state class."""

    def test_event_handler(self):
        """Test event handler."""
        pass


def test_func():
    pass


@pytest.mark.parametrize(
    "input,output",
    [
        ("", ""),
        ("hello", "hello"),
        ("Hello", "hello"),
        ("camelCase", "camel_case"),
        ("camelTwoHumps", "camel_two_humps"),
        ("_start_with_underscore", "_start_with_underscore"),
        ("__start_with_double_underscore", "__start_with_double_underscore"),
    ],
)
def test_to_snake_case(input: str, output: str):
    """Test converting strings to snake case.

    Args:
        input: The input string.
        output: The expected output string.
    """
    assert format.to_snake_case(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ("", ""),
        ("hello", "hello"),
        ("Hello", "Hello"),
        ("snake_case", "snakeCase"),
        ("snake_case_two", "snakeCaseTwo"),
    ],
)
def test_to_camel_case(input: str, output: str):
    """Test converting strings to camel case.

    Args:
        input: The input string.
        output: The expected output string.
    """
    assert format.to_camel_case(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ("", ""),
        ("hello", "Hello"),
        ("Hello", "Hello"),
        ("snake_case", "SnakeCase"),
        ("snake_case_two", "SnakeCaseTwo"),
    ],
)
def test_to_title_case(input: str, output: str):
    """Test converting strings to title case.

    Args:
        input: The input string.
        output: The expected output string.
    """
    assert format.to_title_case(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        ("{", "}"),
        ("(", ")"),
        ("[", "]"),
        ("<", ">"),
        ('"', '"'),
        ("'", "'"),
    ],
)
def test_get_close_char(input: str, output: str):
    """Test getting the close character for a given open character.

    Args:
        input: The open character.
        output: The expected close character.
    """
    assert format.get_close_char(input) == output


@pytest.mark.parametrize(
    "text,open,expected",
    [
        ("", "{", False),
        ("{wrap}", "{", True),
        ("{wrap", "{", False),
        ("{wrap}", "(", False),
        ("(wrap)", "(", True),
    ],
)
def test_is_wrapped(text: str, open: str, expected: bool):
    """Test checking if a string is wrapped in the given open and close characters.

    Args:
        text: The text to check.
        open: The open character.
        expected: Whether the text is wrapped.
    """
    assert format.is_wrapped(text, open) == expected


@pytest.mark.parametrize(
    "text,open,check_first,num,expected",
    [
        ("", "{", True, 1, "{}"),
        ("wrap", "{", True, 1, "{wrap}"),
        ("wrap", "(", True, 1, "(wrap)"),
        ("wrap", "(", True, 2, "((wrap))"),
        ("(wrap)", "(", True, 1, "(wrap)"),
        ("{wrap}", "{", True, 2, "{wrap}"),
        ("(wrap)", "{", True, 1, "{(wrap)}"),
        ("(wrap)", "(", False, 1, "((wrap))"),
    ],
)
def test_wrap(text: str, open: str, expected: str, check_first: bool, num: int):
    """Test wrapping a string.

    Args:
        text: The text to wrap.
        open: The open character.
        expected: The expected output string.
        check_first: Whether to check if the text is already wrapped.
        num: The number of times to wrap the text.
    """
    assert format.wrap(text, open, check_first=check_first, num=num) == expected


@pytest.mark.parametrize(
    "text,indent_level,expected",
    [
        ("", 2, ""),
        ("hello", 2, "hello"),
        ("hello\nworld", 2, "  hello\n  world\n"),
        ("hello\nworld", 4, "    hello\n    world\n"),
        ("  hello\n  world", 2, "    hello\n    world\n"),
    ],
)
def test_indent(text: str, indent_level: int, expected: str, windows_platform: bool):
    """Test indenting a string.

    Args:
        text: The text to indent.
        indent_level: The number of spaces to indent by.
        expected: The expected output string.
        windows_platform: Whether the system is windows.
    """
    assert format.indent(text, indent_level) == (
        expected.replace("\n", "\r\n") if windows_platform else expected
    )


@pytest.mark.parametrize(
    "condition,true_value,false_value,expected",
    [
        ("cond", "<C1>", '""', '{isTrue(cond) ? <C1> : ""}'),
        ("cond", "<C1>", "<C2>", "{isTrue(cond) ? <C1> : <C2>}"),
    ],
)
def test_format_cond(condition: str, true_value: str, false_value: str, expected: str):
    """Test formatting a cond.

    Args:
        condition: The condition to check.
        true_value: The value to return if the condition is true.
        false_value: The value to return if the condition is false.
        expected: The expected output string.
    """
    assert format.format_cond(condition, true_value, false_value) == expected


def test_merge_imports():
    """Test that imports are merged correctly."""
    d1 = {"react": {"Component"}}
    d2 = {"react": {"Component"}, "react-dom": {"render"}}
    d = imports.merge_imports(d1, d2)
    assert set(d.keys()) == {"react", "react-dom"}
    assert set(d["react"]) == {"Component"}
    assert set(d["react-dom"]) == {"render"}


@pytest.mark.parametrize(
    "cls,expected",
    [
        (str, False),
        (int, False),
        (float, False),
        (bool, False),
        (List, True),
        (List[int], True),
    ],
)
def test_is_generic_alias(cls: type, expected: bool):
    """Test checking if a class is a GenericAlias.

    Args:
        cls: The class to check.
        expected: Whether the class is a GenericAlias.
    """
    assert types.is_generic_alias(cls) == expected


@pytest.mark.parametrize(
    "route,format_case,expected",
    [
        ("", True, "index"),
        ("/", True, "index"),
        ("custom-route", True, "custom-route"),
        ("custom-route", False, "custom-route"),
        ("custom-route/", True, "custom-route"),
        ("custom-route/", False, "custom-route"),
        ("/custom-route", True, "custom-route"),
        ("/custom-route", False, "custom-route"),
        ("/custom_route", True, "custom-route"),
        ("/custom_route", False, "custom_route"),
        ("/CUSTOM_route", True, "custom-route"),
        ("/CUSTOM_route", False, "CUSTOM_route"),
    ],
)
def test_format_route(route: str, format_case: bool, expected: bool):
    """Test formatting a route.

    Args:
        route: The route to format.
        format_case: Whether to change casing to snake_case.
        expected: The expected formatted route.
    """
    assert format.format_route(route, format_case=format_case) == expected


@pytest.mark.parametrize(
    "prop,formatted",
    [
        ("string", '"string"'),
        ("{wrapped_string}", "{wrapped_string}"),
        (True, "{true}"),
        (False, "{false}"),
        (123, "{123}"),
        (3.14, "{3.14}"),
        ([1, 2, 3], "{[1, 2, 3]}"),
        (["a", "b", "c"], '{["a", "b", "c"]}'),
        ({"a": 1, "b": 2, "c": 3}, '{{"a": 1, "b": 2, "c": 3}}'),
        ({"a": 'foo "bar" baz'}, r'{{"a": "foo \"bar\" baz"}}'),
        (
            {
                "a": 'foo "{ "bar" }" baz',
                "b": BaseVar(name="val", type_="str"),
            },
            r'{{"a": "foo \"{ \"bar\" }\" baz", "b": val}}',
        ),
        (
            EventChain(events=[EventSpec(handler=EventHandler(fn=mock_event))]),
            '{_e => Event([E("mock_event", {})], _e)}',
        ),
        (
            EventChain(
                events=[
                    EventSpec(
                        handler=EventHandler(fn=mock_event),
                        args=((Var.create_safe("arg"), EVENT_ARG.target.value),),
                    )
                ]
            ),
            '{_e => Event([E("mock_event", {arg:_e.target.value})], _e)}',
        ),
        ({"a": "red", "b": "blue"}, '{{"a": "red", "b": "blue"}}'),
        (BaseVar(name="var", type_="int"), "{var}"),
        (
            BaseVar(
                name="_",
                type_=Any,
                state="",
                is_local=True,
                is_string=False,
            ),
            "{_}",
        ),
        (BaseVar(name='state.colors["a"]', type_="str"), '{state.colors["a"]}'),
        ({"a": BaseVar(name="val", type_="str")}, '{{"a": val}}'),
        ({"a": BaseVar(name='"val"', type_="str")}, '{{"a": "val"}}'),
        (
            {"a": BaseVar(name='state.colors["val"]', type_="str")},
            '{{"a": state.colors["val"]}}',
        ),
        # tricky real-world case from markdown component
        (
            {
                "h1": f"{{({{node, ...props}}) => <Heading {{...props}} {''.join(Tag(name='', props=Style({'as_': 'h1'})).format_props())} />}}"
            },
            '{{"h1": ({node, ...props}) => <Heading {...props} as={`h1`} />}}',
        ),
    ],
)
def test_format_prop(prop: Var, formatted: str):
    """Test that the formatted value of an prop is correct.

    Args:
        prop: The prop to test.
        formatted: The expected formatted value.
    """
    assert format.format_prop(prop) == formatted


def test_validate_invalid_bun_path(mocker):
    """Test that an error is thrown when a custom specified bun path is not valid
    or does not exist.

    Args:
        mocker: Pytest mocker object.
    """
    mock = mocker.Mock()
    mocker.patch.object(mock, "bun_path", return_value="/mock/path")
    mocker.patch("reflex.utils.prerequisites.get_config", mock)
    mocker.patch("reflex.utils.prerequisites.get_bun_version", return_value=None)

    with pytest.raises(typer.Exit):
        prerequisites.validate_bun()


def test_validate_bun_path_incompatible_version(mocker):
    """Test that an error is thrown when the bun version does not meet minimum requirements.

    Args:
        mocker: Pytest mocker object.
    """
    mock = mocker.Mock()
    mocker.patch.object(mock, "bun_path", return_value="/mock/path")
    mocker.patch("reflex.utils.prerequisites.get_config", mock)
    mocker.patch(
        "reflex.utils.prerequisites.get_bun_version",
        return_value=version.parse("0.6.5"),
    )

    with pytest.raises(typer.Exit):
        prerequisites.validate_bun()


def test_remove_existing_bun_installation(mocker):
    """Test that existing bun installation is removed.

    Args:
        mocker: Pytest mocker.
    """
    mocker.patch("reflex.utils.prerequisites.os.path.exists", return_value=True)
    rm = mocker.patch("reflex.utils.prerequisites.path_ops.rm", mocker.Mock())

    prerequisites.remove_existing_bun_installation()
    rm.assert_called_once()


def test_setup_frontend(tmp_path, mocker):
    """Test checking if assets content have been
    copied into the .web/public folder.

    Args:
        tmp_path: root path of test case data directory
        mocker: mocker object to allow mocking
    """
    web_public_folder = tmp_path / ".web" / "public"
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "favicon.ico").touch()

    mocker.patch("reflex.utils.prerequisites.install_frontend_packages")
    mocker.patch("reflex.utils.build.set_env_json")

    build.setup_frontend(tmp_path, disable_telemetry=False)
    assert web_public_folder.exists()
    assert (web_public_folder / "favicon.ico").exists()


@pytest.mark.parametrize(
    "input, output",
    [
        ("_hidden", True),
        ("not_hidden", False),
        ("__dundermethod__", False),
    ],
)
def test_is_backend_variable(input, output):
    assert types.is_backend_variable(input) == output


@pytest.mark.parametrize(
    "cls, cls_check, expected",
    [
        (int, int, True),
        (int, float, False),
        (int, Union[int, float], True),
        (float, Union[int, float], True),
        (str, Union[int, float], False),
        (List[int], List[int], True),
        (List[int], List[float], True),
        (Union[int, float], Union[int, float], False),
        (Union[int, Var[int]], Var[int], False),
        (int, Any, True),
        (Any, Any, True),
        (Union[int, float], Any, True),
    ],
)
def test_issubclass(cls: type, cls_check: type, expected: bool):
    assert types._issubclass(cls, cls_check) == expected


@pytest.mark.parametrize(
    "app_name,expected_config_name",
    [
        ("appname", "AppnameConfig"),
        ("app_name", "AppnameConfig"),
        ("app-name", "AppnameConfig"),
        ("appname2.io", "AppnameioConfig"),
    ],
)
def test_create_config(app_name, expected_config_name, mocker):
    """Test templates.RXCONFIG is formatted with correct app name and config class name.

    Args:
        app_name: App name.
        expected_config_name: Expected config name.
        mocker: Mocker object.
    """
    mocker.patch("builtins.open")
    tmpl_mock = mocker.patch("reflex.compiler.templates.RXCONFIG")
    prerequisites.create_config(app_name)
    tmpl_mock.render.assert_called_with(
        app_name=app_name, config_name=expected_config_name
    )


@pytest.fixture
def tmp_working_dir(tmp_path):
    """Create a temporary directory and chdir to it.

    After the test executes, chdir back to the original working directory.

    Args:
        tmp_path: pytest tmp_path fixture creates per-test temp dir

    Yields:
        subdirectory of tmp_path which is now the current working directory.
    """
    old_pwd = Path(".").resolve()
    working_dir = tmp_path / "working_dir"
    working_dir.mkdir()
    os.chdir(working_dir)
    yield working_dir
    os.chdir(old_pwd)


def test_create_config_e2e(tmp_working_dir):
    """Create a new config file, exec it, and make assertions about the config.

    Args:
        tmp_working_dir: a new directory that is the current working directory
            for the duration of the test.
    """
    app_name = "e2e"
    prerequisites.create_config(app_name)
    eval_globals = {}
    exec((tmp_working_dir / constants.CONFIG_FILE).read_text(), eval_globals)
    config = eval_globals["config"]
    assert config.app_name == app_name


@pytest.mark.parametrize(
    "name,expected",
    [
        ("input1", "ref_input1"),
        ("input 1", "ref_input_1"),
        ("input-1", "ref_input_1"),
        ("input_1", "ref_input_1"),
        ("a long test?1! name", "ref_a_long_test_1_name"),
    ],
)
def test_format_ref(name, expected):
    """Test formatting a ref.

    Args:
        name: The name to format.
        expected: The expected formatted name.
    """
    assert format.format_ref(name) == expected


class DataFrame:
    """A Fake pandas DataFrame class."""

    pass


@pytest.mark.parametrize(
    "class_type,expected",
    [
        (list, False),
        (int, False),
        (dict, False),
        (DataFrame, True),
        (typing.Any, False),
        (typing.List, False),
    ],
)
def test_is_dataframe(class_type, expected):
    """Test that a type name is DataFrame.

    Args:
        class_type: the class type.
        expected: whether type name is DataFrame
    """
    assert types.is_dataframe(class_type) == expected


@pytest.mark.parametrize("gitignore_exists", [True, False])
def test_initialize_non_existent_gitignore(tmp_path, mocker, gitignore_exists):
    """Test that the generated .gitignore_file file on reflex init contains the correct file
    names with correct formatting.

    Args:
        tmp_path: The root test path.
        mocker: The mock object.
        gitignore_exists: Whether a gitignore file exists in the root dir.
    """
    expected = constants.DEFAULT_GITIGNORE.copy()
    mocker.patch("reflex.constants.GITIGNORE_FILE", tmp_path / ".gitignore")

    gitignore_file = tmp_path / ".gitignore"

    if gitignore_exists:
        gitignore_file.touch()
        gitignore_file.write_text(
            """*.db
        __pycache__/
        """
        )

    prerequisites.initialize_gitignore()

    assert gitignore_file.exists()
    file_content = [
        line.strip() for line in gitignore_file.open().read().splitlines() if line
    ]
    assert set(file_content) - expected == set()


def test_app_default_name(tmp_path, mocker):
    """Test that an error is raised if the app name is reflex.

    Args:
        tmp_path: Test working dir.
        mocker: Pytest mocker object.
    """
    reflex = tmp_path / "reflex"
    reflex.mkdir()

    mocker.patch("reflex.utils.prerequisites.os.getcwd", return_value=str(reflex))

    with pytest.raises(typer.Exit):
        prerequisites.get_default_app_name()


def test_node_install_windows(tmp_path, mocker):
    """Require user to install node manually for windows if node is not installed.

    Args:
        tmp_path: Test working dir.
        mocker: Pytest mocker object.
    """
    fnm_root_path = tmp_path / "reflex" / "fnm"
    fnm_exe = fnm_root_path / "fnm.exe"

    mocker.patch("reflex.utils.prerequisites.constants.FNM_DIR", fnm_root_path)
    mocker.patch("reflex.utils.prerequisites.constants.FNM_EXE", fnm_exe)
    mocker.patch("reflex.utils.prerequisites.constants.IS_WINDOWS", True)
    mocker.patch("reflex.utils.processes.new_process")
    mocker.patch("reflex.utils.processes.stream_logs")

    class Resp(Base):
        status_code = 200
        text = "test"

    mocker.patch("httpx.stream", return_value=Resp())
    download = mocker.patch("reflex.utils.prerequisites.download_and_extract_fnm_zip")
    mocker.patch("reflex.utils.prerequisites.zipfile.ZipFile")
    mocker.patch("reflex.utils.prerequisites.path_ops.rm")

    prerequisites.install_node()

    assert fnm_root_path.exists()
    download.assert_called_once()


@pytest.mark.parametrize(
    "machine, system",
    [
        ("x64", "Darwin"),
        ("arm64", "Darwin"),
        ("x64", "Windows"),
        ("arm64", "Windows"),
        ("armv7", "Linux"),
        ("armv8-a", "Linux"),
        ("armv8.1-a", "Linux"),
        ("armv8.2-a", "Linux"),
        ("armv8.3-a", "Linux"),
        ("armv8.4-a", "Linux"),
        ("aarch64", "Linux"),
        ("aarch32", "Linux"),
    ],
)
def test_node_install_unix(tmp_path, mocker, machine, system):
    fnm_root_path = tmp_path / "reflex" / "fnm"
    fnm_exe = fnm_root_path / "fnm"

    mocker.patch("reflex.utils.prerequisites.constants.FNM_DIR", fnm_root_path)
    mocker.patch("reflex.utils.prerequisites.constants.FNM_EXE", fnm_exe)
    mocker.patch("reflex.utils.prerequisites.constants.IS_WINDOWS", False)
    mocker.patch("reflex.utils.prerequisites.platform.machine", return_value=machine)
    mocker.patch("reflex.utils.prerequisites.platform.system", return_value=system)

    class Resp(Base):
        status_code = 200
        text = "test"

    mocker.patch("httpx.stream", return_value=Resp())
    download = mocker.patch("reflex.utils.prerequisites.download_and_extract_fnm_zip")
    process = mocker.patch("reflex.utils.processes.new_process")
    chmod = mocker.patch("reflex.utils.prerequisites.os.chmod")
    mocker.patch("reflex.utils.processes.stream_logs")

    prerequisites.install_node()

    assert fnm_root_path.exists()
    download.assert_called_once()
    if system == "Darwin" and machine == "arm64":
        process.assert_called_with(
            [
                fnm_exe,
                "install",
                "--arch=arm64",
                constants.NODE_VERSION,
                "--fnm-dir",
                fnm_root_path,
            ]
        )
    else:
        process.assert_called_with(
            [fnm_exe, "install", constants.NODE_VERSION, "--fnm-dir", fnm_root_path]
        )
    chmod.assert_called_once()


def test_bun_install_without_unzip(mocker):
    """Test that an error is thrown when installing bun with unzip not installed.

    Args:
        mocker: Pytest mocker object.
    """
    mocker.patch("reflex.utils.path_ops.which", return_value=None)
    mocker.patch("os.path.exists", return_value=False)
    mocker.patch("reflex.utils.prerequisites.constants.IS_WINDOWS", False)

    with pytest.raises(FileNotFoundError):
        prerequisites.install_bun()


@pytest.mark.parametrize("is_windows", [True, False])
def test_create_reflex_dir(mocker, is_windows):
    """Test that a reflex directory is created on initializing frontend
    dependencies.

    Args:
        mocker: Pytest mocker object.
        is_windows: Whether platform is windows.
    """
    mocker.patch("reflex.utils.prerequisites.constants.IS_WINDOWS", is_windows)
    mocker.patch("reflex.utils.prerequisites.processes.run_concurrently", mocker.Mock())
    mocker.patch("reflex.utils.prerequisites.initialize_web_directory", mocker.Mock())
    mocker.patch("reflex.utils.processes.run_concurrently")
    mocker.patch("reflex.utils.prerequisites.validate_bun")
    create_cmd = mocker.patch(
        "reflex.utils.prerequisites.path_ops.mkdir", mocker.Mock()
    )

    prerequisites.initialize_frontend_dependencies()

    assert create_cmd.called


def test_output_system_info(mocker):
    """Make sure reflex does not crash dumping system info.

    Args:
        mocker: Pytest mocker object.

    This test makes no assertions about the output, other than it executes
    without crashing.
    """
    mocker.patch("reflex.utils.console.LOG_LEVEL", constants.LogLevel.DEBUG)
    utils_exec.output_system_info()


@pytest.mark.parametrize(
    "callable", [ExampleTestState.test_event_handler, test_func, lambda x: x]
)
def test_style_prop_with_event_handler_value(callable):
    """Test that a type error is thrown when a style prop has a
    callable as value.

    Args:
        callable: The callable function or event handler.

    """
    style = {
        "color": EventHandler(fn=callable)
        if type(callable) != EventHandler
        else callable
    }

    with pytest.raises(TypeError):
        serialize(style)  # type: ignore
