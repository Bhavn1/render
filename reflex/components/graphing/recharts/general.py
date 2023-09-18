"""General components for Recharts."""

from typing import Any, Dict

from reflex.vars import Var

from .recharts import Recharts


class ResponsiveContainer(Recharts):
    """A base class for responsive containers in Recharts."""

    tag = "ResponsiveContainer"

    # The aspect ratio of the container. The final aspect ratio of the SVG element will be (width / height) * aspect. Number
    aspect: Var[int]

    # The width of chart container. Number
    width: Var[int]

    # The height of chart container. Number
    height: Var[int]

    # The minimum width of chart container. Number
    min_width: Var[int]

    # The minimum height of chart container. Number
    min_height: Var[int]

    # If specified a positive number, debounced function will be used to handle the resize event.
    debounce: Var[int]


class Legend(Recharts):
    """A Legend component in Recharts."""

    tag = "Legend"

    # The width of legend container. Number
    width: Var[int]

    # The height of legend container. Number
    height: Var[int]

    # The layout of legend items. 'horizontal' | 'vertical'
    layout: Var[str]

    # The alignment of legend items in 'horizontal' direction, which can be 'left', 'center', 'right'.
    align: Var[str]

    # The alignment of legend items in 'vertical' direction, which can be 'top', 'middle', 'bottom'.
    vertical_align: Var[str]

    # The size of icon in each legend item.
    icon_size: Var[int]

    # The type of icon in each legend item. 'line' | 'plainline' | 'square' | 'rect' | 'circle' | 'cross' | 'diamond' | 'star' | 'triangle' | 'wye'
    icon_type: Var[str]

    # The width of chart container, usually calculated internally.
    chart_width: Var[int]

    # The height of chart container, usually calculated internally.
    chart_height: Var[int]

    # The margin of chart container, usually calculated internally.
    margin: Var[Dict[str, Any]]


class Tooltip(Recharts):
    """A Tooltip component in Recharts."""

    tag = "Tooltip"

    # The separator between name and value.
    separator: Var[str]

    # The offset size of tooltip. Number
    offset: Var[int]

    # When an item of the payload has value null or undefined, this item won't be displayed.
    filter_null: Var[bool]

    # The content style of tooltip. Object
    content_style: Var[Dict[str, Any]]

    # The wrapper style of tooltip. Object
    wrapper_style: Var[Dict[str, Any]]

    # The style of tooltip item container. Object
    item_style: Var[Dict[str, Any]]

    # The style of default tooltip label which is a p element.
    label_style: Var[Dict[str, Any]]

    # The box of viewing area, which has the shape of {x: someVal, y: someVal, width: someVal, height: someVal}, usually calculated internally.
    view_box: Var[Dict[str, Any]]

    # If set true, the tooltip is displayed. If set false, the tooltip is hidden, usually calculated internally.
    active: Var[bool]

    # If this field is set, the tooltip position will be fixed and will not move anymore.
    position: Var[Dict[str, Any]]

    # The coordinate of tooltip which is usually calculated internally.
    coordinate: Var[Dict[str, Any]]


class Label(Recharts):
    """A Label component in Recharts."""

    tag = "Label"

    # The box of viewing area, which has the shape of {x: someVal, y: someVal, width: someVal, height: someVal}, usually calculated internally.
    view_box: Var[Dict[str, Any]]

    # The value of label, which can be specified by this props or the children of <Label />
    value: Var[str]

    # The offset of label which can be specified by this props or the children of <Label />
    offset: Var[int]

    # The position of label which can be specified by this props or the children of <Label />
    position: Var[str]


class LabelList(Recharts):
    """A LabelList component in Recharts."""

    tag = "LabelList"

    # The key of a group of label values in data.
    data_key: Var[str]

    # The position of each label relative to it view box。op" | "left" | "right" | "bottom" | "inside" | "outside" | "insideLeft" | "insideRight" | "insideTop" | "insideBottom" | "insideTopLeft" | "insideBottomLeft" | "insideTopRight" | "insideBottomRight" | "insideStart" | "insideEnd" | "end" | "center"
    position: Var[str]

    # The offset to the specified "position"
    offset: Var[int]
