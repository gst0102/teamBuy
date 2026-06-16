from __future__ import annotations

from app.models.domain import ImportBatch, ImportNotification
from app.services.helpers import new_id
from app.services.time_utils import now_iso


class ImportNotificationService:
    def build_notification(self, batch: ImportBatch, channel: str = "mock", media_warning_count: int = 0) -> ImportNotification:
        is_success = batch.status == "success"
        title = batch.titleCandidate or "未命名素材"
        if is_success:
            message = f"《{title}》已整理完成，请打开小程序认领、编辑和分类。"
            if media_warning_count:
                message += f" 其中 {media_warning_count} 个媒体暂未转存成功，已进入后台重试队列。"
        else:
            reason = f"原因：{batch.errorMessage}" if batch.errorMessage else "请检查内容后重试。"
            message = f"《{title}》导入失败，{reason}"
        return ImportNotification(
            id=new_id("notice"),
            importBatchId=batch.id,
            externalUserId=batch.externalUserId,
            conversationId=batch.conversationId,
            status="success" if is_success else "failed",
            title=title,
            message=message,
            channel=channel,
            sentAt=now_iso(),
            errorMessage=batch.errorMessage,
        )
