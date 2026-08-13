"""Tests for the offline Hanzi Writer single-line provider."""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from src.glyph import build_trajectory
from src.glyph.hanzi_writer import (
    HanziWriterData,
    HanziWriterDataError,
    SingleLineLayoutEngine,
)
from src.glyph.layout_engine import LayoutConfig
from src.glyph.trajectory import PenState, Point2D
from src.trajectory.config import MotionConfig
from src.trajectory.coordinate import CoordinateTransformer
from src.trajectory.motion import trajectory_to_commands
from src.trajectory.processor import TrajectoryProcessor


class StubData:
    def __init__(self, characters):
        self.characters = characters

    def get_medians(self, char):
        return self.characters.get(char)


def test_offline_data_contains_ni_hao_in_stroke_order():
    data = HanziWriterData()
    assert data.character_count == 9574
    assert len(data.get_medians("你")) == 7
    assert len(data.get_medians("好")) == 6


def test_official_coordinate_box_maps_to_page_millimeters():
    data = StubData({"X": [[[0, 900], [1024, -124]]]})
    config = LayoutConfig(
        char_size=20,
        margin_left=3,
        margin_top=4,
        margin_right=0,
        margin_bottom=0,
    )
    engine = SingleLineLayoutEngine(data, config, smooth_strokes=False)
    glyph = engine.layout("X")[0]
    assert glyph.contours[0] == [Point2D(3, 4), Point2D(23, 24)]


def test_smoothing_preserves_stroke_endpoints_and_adds_samples():
    source = [[0, 900], [512, 500], [1024, -124]]
    data = StubData({"X": [source]})
    config = LayoutConfig(char_size=20, margin_left=0, margin_top=0)
    raw = SingleLineLayoutEngine(data, config, smooth_strokes=False).layout("X")[0]
    smooth = SingleLineLayoutEngine(data, config, smooth_strokes=True).layout("X")[0]
    assert smooth.contours[0][0] == raw.contours[0][0]
    assert smooth.contours[0][-1] == raw.contours[0][-1]
    assert len(smooth.contours[0]) > len(raw.contours[0])


def test_missing_character_is_reported_without_outline_fallback():
    engine = SingleLineLayoutEngine(StubData({}), LayoutConfig())
    unsupported = chr(0x1F600)
    assert engine.layout(unsupported) == []
    assert engine.missing_characters == [unsupported]


def test_invalid_data_file_has_clear_error(tmp_path: Path):
    path = tmp_path / "bad.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as file_obj:
        file_obj.write("{}")
    with pytest.raises(HanziWriterDataError, match="Cannot load Hanzi Writer data"):
        HanziWriterData(path).get_medians("你")


def test_ni_hao_runs_through_motion_pipeline_as_separate_strokes():
    layout = LayoutConfig(char_size=14, page_width=148, page_height=210)
    engine = SingleLineLayoutEngine(HanziWriterData(), layout)
    trajectory = build_trajectory(engine, "你好")
    assert len(trajectory.glyphs) == 2
    assert [len(glyph.contours) for glyph in trajectory.glyphs] == [7, 6]
    assert sum(point.state == PenState.UP for point in trajectory.points) == 24

    config = MotionConfig(work_width_mm=200, work_height_mm=280)
    cleaned = TrajectoryProcessor(config).process(trajectory.points)
    transformer = CoordinateTransformer(config)
    transformer.fit_bounds(trajectory.page_width_mm, trajectory.page_height_mm)
    commands = trajectory_to_commands(transformer.transform(cleaned), config)
    assert commands
    assert commands[-1].type.name == "PEN_UP"
