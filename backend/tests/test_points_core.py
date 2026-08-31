from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.domain import AppState
from app.services.points_core import PointsCoreService


def test_points_core_is_idempotent_and_supports_multiple_tool_account_types():
    state = AppState()
    core = PointsCoreService()

    account = core.ensure_account(
        state,
        "user-a",
        initial_points=100,
        initial_reason="首次进入互帮互助赠送积分",
    )
    assert account.balance == 100
    assert len(state.mutual_point_ledgers) == 1

    granted = core.grant(
        state,
        "user-a",
        20,
        reason="完成互帮互助任务",
        idempotency_key="task:task-1:executor:user-a",
        source_type="mutual_task",
        source_id="task-1",
    )
    repeated = core.grant(
        state,
        "user-a",
        20,
        reason="完成互帮互助任务",
        idempotency_key="task:task-1:executor:user-a",
        source_type="mutual_task",
        source_id="task-1",
    )
    assert granted["account"].balance == 120
    assert repeated["duplicate"] is True
    assert repeated["account"].balance == 120
    assert len(state.mutual_point_ledgers) == 2

    consumed = core.consume(
        state,
        "user-a",
        30,
        reason="解锁羊毛任务",
        idempotency_key="wool:wool-1:unlock:user-a",
        source_type="wool_unlock",
        source_id="wool-1",
    )
    assert consumed["account"].balance == 90
    with pytest.raises(HTTPException) as exc_info:
        core.consume(
            state,
            "user-a",
            91,
            reason="余额不足测试",
            idempotency_key="insufficient:user-a",
        )
    assert exc_info.value.status_code == 402
    assert state.mutual_point_accounts[0].balance == 90

    future_tool_account = core.ensure_account(
        state,
        "user-a",
        account_type="future_tool",
        initial_points=0,
    )
    assert future_tool_account.balance == 0
    assert core.list_ledgers(state, "user-a", account_type="future_tool") == []


def test_points_core_transfer_is_atomic_and_idempotent():
    state = AppState()
    core = PointsCoreService()
    core.ensure_account(state, "publisher", initial_points=100)
    core.ensure_account(state, "executor", initial_points=0)

    result = core.transfer(
        state,
        "publisher",
        "executor",
        5,
        operation_key="task:task-2:settlement:submission-1",
        debit_reason="任务结算扣除发布者积分",
        credit_reason="任务完成奖励执行者积分",
        source_type="mutual_task_settlement",
        source_id="submission-1",
    )
    repeated = core.transfer(
        state,
        "publisher",
        "executor",
        5,
        operation_key="task:task-2:settlement:submission-1",
        debit_reason="任务结算扣除发布者积分",
        credit_reason="任务完成奖励执行者积分",
        source_type="mutual_task_settlement",
        source_id="submission-1",
    )
    assert result["fromAccount"].balance == 95
    assert result["toAccount"].balance == 5
    assert repeated["duplicate"] is True
    assert repeated["fromAccount"].balance == 95
    assert repeated["toAccount"].balance == 5
    # The zero-point executor account has no seed ledger; the transfer adds
    # exactly one debit and one credit row.
    assert len(state.mutual_point_ledgers) == 3

    with pytest.raises(HTTPException) as exc_info:
        core.transfer(
            state,
            "publisher",
            "executor",
            96,
            operation_key="task:task-2:settlement:submission-2",
            debit_reason="余额不足测试",
            credit_reason="不应入账",
        )
    assert exc_info.value.status_code == 402
    assert state.mutual_point_accounts[0].balance == 95
    assert state.mutual_point_accounts[1].balance == 5
    assert len(state.mutual_point_ledgers) == 3
