"""CMP-A05 ReportAccess の契約：集計を書き出し先に書く（全体を置き換える。DD-11）。"""

from typing import Protocol

from fukugyononuko_social.domain.metrics import Report


class ReportAccess(Protocol):
    def publish_report(self, report: Report) -> None: ...
