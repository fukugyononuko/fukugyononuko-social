"""CMP-C01 CLI（`nukosns`）。CLI が使うもの（Manager の契約と Utility）の組を定める（DD-15）。

組み立ては composition.py が行い、`run(argv, build)` の build として渡す。
"""

from dataclasses import dataclass

from fukugyononuko_social.managers.measurement import MeasurementManager
from fukugyononuko_social.managers.publishing import PublishingManager
from fukugyononuko_social.utilities.logging import Logging


@dataclass(frozen=True)
class App:
    measurement: MeasurementManager
    publishing: PublishingManager
    log: Logging
