"""Polar charts in Recharts."""

from typing import Any, Dict, List, Union

from reflex.vars import Var

from .recharts import Recharts


class Pie(Recharts):
    """A Pie chart component in Recharts."""

    tag = "Pie"

    # The key of each sector's value.
    data_key: Var[str]

    # The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container width.
    cx: Var[Union[int, str]]

    # The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container height.
    cy: Var[Union[int, str]]

    # The inner radius of pie, which can be set to a percent value.
    inner_radius: Var[Union[int, str]]

    # The outer radius of pie, which can be set to a percent value.
    outer_radius: Var[Union[int, str]]

    # The angle of first sector.
    start_angle: Var[int]

    # The direction of sectors. 1 means clockwise and -1 means anticlockwise.
    end_angle: Var[int]

    # The minimum angle of each unzero data.
    min_angle: Var[int]

    # The angle between two sectors.
    padding_angle: Var[int]

    # The key of each sector's name.
    name_key: Var[str]

    # The type of icon in legend. If set to 'none', no legend item will be rendered.
    legend_type: Var[str]

    # If false set, labels will not be drawn.
    label: Var[bool]

    # If false set, label lines will not be drawn.
    label_line: Var[bool]

    # Valid children components
    valid_children: List[str] = ["Cell", "LabelList"]


class Radar(Recharts):
    """A Radar chart component in Recharts."""

    tag = "Radar"

    # The key of a group of data which should be unique in a radar chart.
    data_key: Var[str]

    # The coordinates of all the vertexes of the radar shape, like [{ x, y }].
    points: Var[List[Dict[str, Any]]]

    # If false set, dots will not be drawn
    dot: Var[bool]

    # The type of icon in legend. If set to 'none', no legend item will be rendered.
    legend_type: Var[str]

    # If false set, labels will not be drawn
    label: Var[bool]

    # Specifies when the animation should begin, the unit of this option is ms.
    animation_begin: Var[int]

    # Specifies the duration of animation, the unit of this option is ms.
    animation_duration: Var[int]

    # The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'
    animation_easing: Var[str]

    # Valid children components
    valid_children: List[str] = ["LabelList"]


class RadialBar(Recharts):
    """A RadialBar chart component in Recharts."""

    tag = "RadialBar"

    # The source data which each element is an object.
    data: Var[List[Dict[str, Any]]]

    # Min angle of each bar. A positive value between 0 and 360.
    min_angle: Var[int]

    # Type of legend
    legend_type: Var[str]

    # If false set, labels will not be drawn.
    label: Var[bool]

    # If false set, background sector will not be drawn.
    background: Var[bool]

    # Valid children components
    valid_children: List[str] = ["LabelList"]


class PolarAngleAxis(Recharts):
    """A PolarAngleAxis component in Recharts."""

    tag = "PolarAngleAxis"

    # The key of a group of data which should be unique to show the meaning of angle axis.
    data_key: Var[str]

    # The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container width.
    cx: Var[Union[int, str]]

    # The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container height.
    cy: Var[Union[int, str]]

    # The outer radius of circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy.
    radius: Var[Union[int, str]]

    # If false set, axis line will not be drawn. If true set, axis line will be drawn which have the props calculated internally. If object set, axis line will be drawn which have the props mergered by the internal calculated props and the option.
    axis_line: Var[Union[bool, Dict[str, Any]]]

    # The type of axis line.
    axis_line_type: Var[str]

    # If false set, tick lines will not be drawn. If true set, tick lines will be drawn which have the props calculated internally. If object set, tick lines will be drawn which have the props mergered by the internal calculated props and the option.
    tick_line: Var[Union[bool, Dict[str, Any]]]

    # The width or height of tick.
    tick: Var[Union[int, str]]

    # The array of every tick's value and angle.
    ticks: Var[List[Dict[str, Any]]]

    # The orientation of axis text.
    orient: Var[str]

    # Allow the axis has duplicated categorys or not when the type of axis is "category".
    allow_duplicated_category: Var[bool]

    # Valid children components
    valid_children: List[str] = ["Label"]


class PolarGrid(Recharts):
    """A PolarGrid component in Recharts."""

    tag = "PolarGrid"

    # The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container width.
    cx: Var[Union[int, str]]

    # The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container height.
    cy: Var[Union[int, str]]

    # The radius of the inner polar grid.
    inner_radius: Var[Union[int, str]]

    # The radius of the outer polar grid.
    outer_radius: Var[Union[int, str]]

    # The array of every line grid's angle.
    polar_angles: Var[List[int]]

    # The array of every line grid's radius.
    polar_radius: Var[List[int]]

    # The type of polar grids. 'polygon' | 'circle'
    grid_type: Var[str]

    # Valid children components
    valid_children: List[str] = ["RadarChart", "RadiarBarChart"]


class PolarRadiusAxis(Recharts):
    """A PolarRadiusAxis component in Recharts."""

    tag = "PolarRadiusAxis"

    # The angle of radial direction line to display axis text.
    angle: Var[int]

    # The type of axis line. 'number' | 'category'
    type_: Var[str]

    # Allow the axis has duplicated categorys or not when the type of axis is "category".
    allow_duplicated_category: Var[bool]

    # The x-coordinate of center.
    cx: Var[Union[int, str]]

    # The y-coordinate of center.
    cy: Var[Union[int, str]]

    # If set to true, the ticks of this axis are reversed.
    reversed: Var[bool]

    # The orientation of axis text.
    orientation: Var[str]

    # If false set, axis line will not be drawn. If true set, axis line will be drawn which have the props calculated internally. If object set, axis line will be drawn which have the props mergered by the internal calculated props and the option.
    axis_line: Var[Union[bool, Dict[str, Any]]]

    # The width or height of tick.
    tick: Var[Union[int, str]]

    # The count of ticks.
    tick_count: Var[int]

    # If 'auto' set, the scale funtion is linear scale. 'auto' | 'linear' | 'pow' | 'sqrt' | 'log' | 'identity' | 'time' | 'band' | 'point' | 'ordinal' | 'quantile' | 'quantize' | 'utc' | 'sequential' | 'threshold'
    scale: Var[str]

    # Valid children components
    valid_children: List[str] = ["Label"]
