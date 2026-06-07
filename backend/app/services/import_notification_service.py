from __future__ import annotations

from app.models.domain import ImportBatch, ImportNotification
from app.services.helpers import new_id
from app.services.time_utils import now_iso


class ImportNotificationService:
    def build_notification(self, batch: ImportBatch) -> ImportNotification:
        is_success = batch.status == "success"
        title = batch.titleCandidate or "未命名素材"
        message = f"《{title}》导入成功，请打开小程序认领编辑。" if is_success else f"《{title}》导入失败，请检查内容后重试。"
        return ImportNotification(
            id=new_id("notice"),
            importBatchId=batch.id,
            externalUserId=batch.externalUserId,
            conversationId=batch.conversationId,
            status="success" if is_success else "failed",
            title=title,
            message=message,
            channel="mock",
            sentAt=now_iso(),
            errorMessage=batch.errorMessage,
        )
