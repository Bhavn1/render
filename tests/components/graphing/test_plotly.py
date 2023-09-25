import pytest

try:
    import numpy as np
except ImportError:
    pytest.skip("numpy is not installed", allow_module_level=True)
import plotly.graph_objects as go

from reflex.components.graphing.plotly import serialize_plotly_figure  # type: ignore
from reflex.utils.serializers import serialize


@pytest.fixture
def plotly_fig() -> go.Figure:
    """Get a plotly figure.

    Returns:
        A random plotly figure.
    """
    # Generate random data.
    data = np.random.randint(0, 10, size=(10, 4))
    trace = go.Scatter(
        x=list(range(len(data))), y=data[:, 0], mode="lines", name="Trace 1"
    )

    # Create a graph.
    return go.Figure(data=[trace])


def test_serialize_plotly(plotly_fig: go.Figure):
    """Test that serializing a plotly figure works.

    Args:
        plotly_fig: The figure to serialize.
    """
    value = serialize(plotly_fig)
    assert isinstance(value, list)
    assert value == serialize_plotly_figure(plotly_fig)
