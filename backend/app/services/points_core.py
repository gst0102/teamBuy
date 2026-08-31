from __future__ import annotations

from fastapi import HTTPException

from app.models.domain import AppState, MutualPointAccount, MutualPointLedger
from app.services.helpers import new_id
from app.services.time_utils import now_iso


DEFAULT_POINTS_ACCOUNT_TYPE = "mutual_help"
MAX_ACCOUNT_TYPE_LENGTH = 64
MAX_LEDGER_TYPE_LENGTH = 64
MAX_SOURCE_TYPE_LENGTH = 64


class PointsCoreService:
    """The shared points accounting rules used by future tool domains.

    The existing mutual-help tables/models remain the storage compatibility
    layer for now.  ``accountType`` and the source fields make the records
    usable by other tools without creating another balance or ledger.  Every
    balance mutation goes through this class and is paired with an immutable
    ledger row.
    """

    @staticmethod
    def _clean(value: str | None, field: str, max_length: int) -> str:
        clean = str(value or "").strip()
        if not clean:
            raise HTTPException(status_code=400, detail=f"{field}不能为空")
        if len(clean) > max_length:
            raise HTTPException(status_code=400, detail=f"{field}过长")
        return clean

    @classmethod
    def normalize_account_type(cls, account_type: str = DEFAULT_POINTS_ACCOUNT_TYPE) -> str:
        return cls._clean(account_type, "积分账户类型", MAX_ACCOUNT_TYPE_LENGTH)

    @classmethod
    def _find_account(
        cls,
        state: AppState,
        user_id: str,
        account_type: str,
    ) -> MutualPointAccount | None:
        return next(
            (
                item
                for item in state.mutual_point_accounts
                if item.userId == user_id and item.accountType == account_type
            ),
            None,
        )

    @classmethod
    def _find_ledger_by_idempotency_key(
        cls,
        state: AppState,
        user_id: str,
        account_type: str,
        idempotency_key: str,
    ) -> MutualPointLedger | None:
        return next(
            (
                item
                for item in state.mutual_point_ledgers
                if item.userId == user_id
                and item.accountType == account_type
                and item.idempotencyKey == idempotency_key
            ),
            None,
        )

    @classmethod
    def ensure_account(
        cls,
        state: AppState,
        user_id: str,
        *,
        account_type: str = DEFAULT_POINTS_ACCOUNT_TYPE,
        initial_points: int = 0,
        initial_reason: str = "首次建立积分账户",
    ) -> MutualPointAccount:
        user_id = cls._clean(user_id, "用户 ID", 160)
        account_type = cls.normalize_account_type(account_type)
        if initial_points < 0:
            raise HTTPException(status_code=400, detail="初始积分不能为负数")

        account = cls._find_account(state, user_id, account_type)
        if account:
            return account

        now = now_iso()
        account = MutualPointAccount(
            id=f"{account_type}_points_{user_id}",
            userId=user_id,
            accountType=account_type,
            balance=initial_points,
            totalGranted=initial_points,
            totalConsumed=0,
            createdAt=now,
            updatedAt=now,
        )
        state.mutual_point_accounts.append(account)
        if initial_points:
            state.mutual_point_ledgers.append(
                MutualPointLedger(
                    id=new_id("points_ledger"),
                    userId=user_id,
                    accountType=account_type,
                    ledgerType="initial_grant",
                    pointsDelta=initial_points,
                    balanceAfter=initial_points,
                    reason=initial_reason,
                    idempotencyKey=f"initial:{account_type}:{user_id}",
                    sourceType="system",
                    sourceId=account.id,
                    createdAt=now,
                )
            )
        return account

    @classmethod
    def apply_delta(
        cls,
        state: AppState,
        user_id: str,
        points_delta: int,
        *,
        ledger_type: str,
        reason: str,
        idempotency_key: str | None = None,
        account_type: str = DEFAULT_POINTS_ACCOUNT_TYPE,
        source_type: str | None = None,
        source_id: str | None = None,
        related_order_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        user_id = cls._clean(user_id, "用户 ID", 160)
        account_type = cls.normalize_account_type(account_type)
        ledger_type = cls._clean(ledger_type, "积分流水类型", MAX_LEDGER_TYPE_LENGTH)
        reason = cls._clean(reason, "积分流水原因", 240)
        if points_delta == 0:
            raise HTTPException(status_code=400, detail="积分变动不能为 0")
        if idempotency_key is not None:
            idempotency_key = cls._clean(idempotency_key, "积分幂等键", 200)
        if source_type is not None:
            source_type = cls._clean(source_type, "积分来源类型", MAX_SOURCE_TYPE_LENGTH)
        if source_id is not None:
            source_id = cls._clean(source_id, "积分来源 ID", 200)

        account = cls.ensure_account(state, user_id, account_type=account_type)
        existing = (
            cls._find_ledger_by_idempotency_key(state, user_id, account_type, idempotency_key)
            if idempotency_key
            else None
        )
        if existing:
            return {"account": account, "ledger": existing, "duplicate": True}

        new_balance = account.balance + points_delta
        if new_balance < 0:
            raise HTTPException(status_code=402, detail="积分余额不足")

        now = now_iso()
        account.balance = new_balance
        if points_delta > 0:
            account.totalGranted += points_delta
        else:
            account.totalConsumed += abs(points_delta)
        account.updatedAt = now
        ledger = MutualPointLedger(
            id=new_id("points_ledger"),
            userId=user_id,
            accountType=account_type,
            ledgerType=ledger_type,
            pointsDelta=points_delta,
            balanceAfter=new_balance,
            reason=reason,
            relatedOrderId=related_order_id,
            idempotencyKey=idempotency_key,
            sourceType=source_type,
            sourceId=source_id,
            metadata=metadata or {},
            createdAt=now,
        )
        state.mutual_point_ledgers.append(ledger)
        return {"account": account, "ledger": ledger, "duplicate": False}

    @classmethod
    def grant(
        cls,
        state: AppState,
        user_id: str,
        points: int,
        *,
        ledger_type: str = "grant",
        reason: str,
        idempotency_key: str,
        account_type: str = DEFAULT_POINTS_ACCOUNT_TYPE,
        source_type: str | None = None,
        source_id: str | None = None,
        related_order_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        if points <= 0:
            raise HTTPException(status_code=400, detail="发放积分必须大于 0")
        return cls.apply_delta(
            state,
            user_id,
            points,
            ledger_type=ledger_type,
            reason=reason,
            idempotency_key=idempotency_key,
            account_type=account_type,
            source_type=source_type,
            source_id=source_id,
            related_order_id=related_order_id,
            metadata=metadata,
        )

    @classmethod
    def consume(
        cls,
        state: AppState,
        user_id: str,
        points: int,
        *,
        ledger_type: str = "consume",
        reason: str,
        idempotency_key: str,
        account_type: str = DEFAULT_POINTS_ACCOUNT_TYPE,
        source_type: str | None = None,
        source_id: str | None = None,
        related_order_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        if points <= 0:
            raise HTTPException(status_code=400, detail="消耗积分必须大于 0")
        return cls.apply_delta(
            state,
            user_id,
            -points,
            ledger_type=ledger_type,
            reason=reason,
            idempotency_key=idempotency_key,
            account_type=account_type,
            source_type=source_type,
            source_id=source_id,
            related_order_id=related_order_id,
            metadata=metadata,
        )

    @classmethod
    def transfer(
        cls,
        state: AppState,
        from_user_id: str,
        to_user_id: str,
        points: int,
        *,
        operation_key: str,
        debit_reason: str,
        credit_reason: str,
        account_type: str = DEFAULT_POINTS_ACCOUNT_TYPE,
        debit_ledger_type: str = "transfer_debit",
        credit_ledger_type: str = "transfer_credit",
        source_type: str | None = None,
        source_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        from_user_id = cls._clean(from_user_id, "扣款用户 ID", 160)
        to_user_id = cls._clean(to_user_id, "收款用户 ID", 160)
        if from_user_id == to_user_id:
            raise HTTPException(status_code=400, detail="扣款和收款用户不能相同")
        if points <= 0:
            raise HTTPException(status_code=400, detail="转账积分必须大于 0")
        # Leave room for the ``:debit``/``:credit`` suffixes used to make the
        # two immutable rows independently idempotent.
        operation_key = cls._clean(operation_key, "积分转账幂等键", 180)
        account_type = cls.normalize_account_type(account_type)
        debit_ledger_type = cls._clean(debit_ledger_type, "扣款流水类型", MAX_LEDGER_TYPE_LENGTH)
        credit_ledger_type = cls._clean(credit_ledger_type, "收款流水类型", MAX_LEDGER_TYPE_LENGTH)
        debit_reason = cls._clean(debit_reason, "扣款流水原因", 240)
        credit_reason = cls._clean(credit_reason, "收款流水原因", 240)
        if source_type is not None:
            source_type = cls._clean(source_type, "积分来源类型", MAX_SOURCE_TYPE_LENGTH)
        if source_id is not None:
            source_id = cls._clean(source_id, "积分来源 ID", 200)
        debit_key = f"{operation_key}:debit"
        credit_key = f"{operation_key}:credit"
        existing_debit = cls._find_ledger_by_idempotency_key(state, from_user_id, account_type, debit_key)
        existing_credit = cls._find_ledger_by_idempotency_key(state, to_user_id, account_type, credit_key)
        if existing_debit and existing_credit:
            return {
                "fromAccount": cls.ensure_account(state, from_user_id, account_type=account_type),
                "toAccount": cls.ensure_account(state, to_user_id, account_type=account_type),
                "debitLedger": existing_debit,
                "creditLedger": existing_credit,
                "duplicate": True,
            }
        if existing_debit or existing_credit:
            raise HTTPException(status_code=409, detail="积分转账流水不完整，请人工核对")

        from_account = cls.ensure_account(state, from_user_id, account_type=account_type)
        to_account = cls.ensure_account(state, to_user_id, account_type=account_type)
        if from_account.balance < points:
            raise HTTPException(status_code=402, detail="积分余额不足")

        debit = cls.consume(
            state,
            from_user_id,
            points,
            ledger_type=debit_ledger_type,
            reason=debit_reason,
            idempotency_key=debit_key,
            account_type=account_type,
            source_type=source_type,
            source_id=source_id,
            metadata=metadata,
        )
        credit = cls.grant(
            state,
            to_user_id,
            points,
            ledger_type=credit_ledger_type,
            reason=credit_reason,
            idempotency_key=credit_key,
            account_type=account_type,
            source_type=source_type,
            source_id=source_id,
            metadata=metadata,
        )
        return {
            "fromAccount": debit["account"],
            "toAccount": credit["account"],
            "debitLedger": debit["ledger"],
            "creditLedger": credit["ledger"],
            "duplicate": False,
        }

    @classmethod
    def list_ledgers(
        cls,
        state: AppState,
        user_id: str,
        *,
        account_type: str = DEFAULT_POINTS_ACCOUNT_TYPE,
        limit: int = 100,
    ) -> list[MutualPointLedger]:
        user_id = cls._clean(user_id, "用户 ID", 160)
        account_type = cls.normalize_account_type(account_type)
        safe_limit = min(max(int(limit or 100), 1), 200)
        return sorted(
            [
                item
                for item in state.mutual_point_ledgers
                if item.userId == user_id and item.accountType == account_type
            ],
            key=lambda item: (item.createdAt, item.id),
            reverse=True,
        )[:safe_limit]
