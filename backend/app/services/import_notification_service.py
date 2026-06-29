from __future__ import annotations

from app.models.domain import ImportBatch, ImportNotification
from app.services.helpers import new_id
from app.services.time_utils import now_iso


class ImportNotificationService:
    def build_notification(self, batch: ImportBatch, channel: str = "mock", media_warning_count: int = 0) -> ImportNotification:
        is_success = batch.status in {"success", "claimed"}
        title = batch.titleCandidate or "未命名素材"
        result_ref_id = batch.generatedNoteId or batch.generatedCardId
        result_type = "note" if batch.generatedNoteId else ("card" if batch.generatedCardId else None)
        result_path = f"/pages/note-edit/index?id={batch.generatedNoteId}" if batch.generatedNoteId else (
            f"/pages/card-view/index?id={batch.generatedCardId}" if batch.generatedCardId else None
        )
        actions = []
        if is_success:
            message = f"已生成《{title}》，打开小程序可查看和分享。"
            if result_path:
                actions.append({"key": "open-result", "label": "打开结果", "path": result_path})
            if batch.generatedNoteId:
                actions.append({"key": "add-showcase", "label": "加入合集", "path": f"/pages/showcase-edit/index?noteId={batch.generatedNoteId}&mode=property"})
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
            resultType=result_type,
            resultRefId=result_ref_id,
            resultPath=result_path,
            actions=actions,
            sendStatus="pending" if channel == "wecom" else "skipped",
        )
