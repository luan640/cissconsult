from django.db import models


class MasterReportSettings(models.Model):
    evaluation_representative_name = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'master_report_settings'

    def __str__(self) -> str:
        return self.evaluation_representative_name or 'Master Report Settings'

