from __future__ import annotations

from datetime import datetime, timedelta

from app.api.dependencies import get_app_service
from app.core.config import settings
from app.models.domain import ReferralRelation, ReferralReward, ReferralWithdrawal
from app.services.time_utils import SHANGHAI


def login(client, openid: str, nickname: str) -> dict:
    return client.post(
        "/api/auth/mock-login",
        json={"openid": openid, "nickname": nickname},
    ).json()["data"]


def test_referral_analytics_exposes_periods_relationships_earnings_and_transfers(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "ops-secret")
    inviter_a = login(client, "analytics_inviter_a", "推荐人甲")
    inviter_b = login(client, "analytics_inviter_b", "推荐人乙")
    invitee_a = login(client, "analytics_invitee_a", "被推荐甲")
    invitee_b = login(client, "analytics_invitee_b", "被推荐乙")
    invitee_c = login(client, "analytics_invitee_c", "被推荐丙")
    service = client.app.dependency_overrides[get_app_service]()

    now = datetime.now(tz=SHANGHAI)

    def stamp(days_ago: int) -> str:
        return (now - timedelta(days=days_ago, minutes=1)).isoformat()

    relation_today = ReferralRelation(
        id="analytics_relation_today",
        inviterUserId=inviter_a["id"],
        inviteeUserId=invitee_a["id"],
        source="share_link",
        createdAt=stamp(0),
        updatedAt=stamp(0),
    )
    relation_2d = ReferralRelation(
        id="analytics_relation_2d",
        inviterUserId=inviter_a["id"],
        inviteeUserId=invitee_b["id"],
        source="invite_code",
        createdAt=stamp(2),
        updatedAt=stamp(2),
    )
    relation_old = ReferralRelation(
        id="analytics_relation_old",
        inviterUserId=inviter_b["id"],
        inviteeUserId=invitee_c["id"],
        source="invite_code",
        createdAt=stamp(20),
        updatedAt=stamp(20),
    )
    reward_today = ReferralReward(
        id="analytics_reward_today",
        inviterUserId=inviter_a["id"],
        inviteeUserId=invitee_a["id"],
        sourceOrderId="analytics_order_today",
        amountFen=1000,
        withdrawnFen=1000,
        status="withdrawn",
        availableAt=stamp(0),
        withdrawnAt=stamp(0),
        createdAt=stamp(0),
        updatedAt=stamp(0),
    )
    reward_2d = ReferralReward(
        id="analytics_reward_2d",
        inviterUserId=inviter_a["id"],
        inviteeUserId=invitee_b["id"],
        sourceOrderId="analytics_order_2d",
        amountFen=800,
        status="available",
        availableAt=stamp(2),
        createdAt=stamp(2),
        updatedAt=stamp(2),
    )
    reward_old = ReferralReward(
        id="analytics_reward_old",
        inviterUserId=inviter_b["id"],
        inviteeUserId=invitee_c["id"],
        sourceOrderId="analytics_order_old",
        amountFen=500,
        status="revoked",
        revokedAt=stamp(20),
        createdAt=stamp(20),
        updatedAt=stamp(20),
    )
    paid_transfer = ReferralWithdrawal(
        id="analytics_transfer_paid",
        userId=inviter_a["id"],
        amountFen=1000,
        status="paid",
        rewardIds=[reward_today.id],
        paidAt=stamp(0),
        createdAt=stamp(1),
        updatedAt=stamp(0),
    )
    old_pending_transfer = ReferralWithdrawal(
        id="analytics_transfer_pending",
        userId=inviter_b["id"],
        amountFen=500,
        status="pending",
        rewardIds=[reward_old.id],
        createdAt=stamp(20),
        updatedAt=stamp(20),
    )
    state = service._load()
    state.referral_relations.extend([relation_today, relation_2d, relation_old])
    state.referral_rewards.extend([reward_today, reward_2d, reward_old])
    state.referral_withdrawals.extend([paid_transfer, old_pending_transfer])
    service._save(state)

    headers = {"X-Admin-Token": "ops-secret"}
    assert client.get("/api/ops-admin/referral-analytics").status_code == 403

    today = client.get("/api/ops-admin/referral-analytics", headers=headers, params={"period": "today"})
    assert today.status_code == 200
    today_data = today.json()["data"]
    assert today_data["summary"]["referralCount"] == 1
    assert today_data["summary"]["referrerCount"] == 1
    assert today_data["summary"]["rewardGeneratedFen"] == 1000
    assert today_data["summary"]["rewardNetFen"] == 1000
    assert today_data["summary"]["transferRequestedFen"] == 0
    assert today_data["summary"]["transferPaidFen"] == 1000
    assert today_data["relationRows"][0]["inviterNickname"] == "推荐人甲"
    assert today_data["relationRows"][0]["inviteeNickname"] == "被推荐甲"

    seven_days = client.get("/api/ops-admin/referral-analytics", headers=headers, params={"period": "7d"})
    seven_days_data = seven_days.json()["data"]
    assert seven_days_data["summary"]["referralCount"] == 2
    assert seven_days_data["summary"]["referredUserCount"] == 2
    assert seven_days_data["summary"]["rewardGeneratedFen"] == 1800
    assert seven_days_data["summary"]["transferPaidFen"] == 1000

    total = client.get("/api/ops-admin/referral-analytics", headers=headers, params={"period": "total"})
    total_data = total.json()["data"]
    assert total_data["summary"]["referralCount"] == 3
    assert total_data["summary"]["referrerCount"] == 2
    assert total_data["summary"]["rewardGeneratedFen"] == 2300
    assert total_data["summary"]["rewardRevokedFen"] == 500
    assert total_data["summary"]["rewardNetFen"] == 1800
    assert total_data["summary"]["transferRequestedFen"] == 1500
    assert total_data["summary"]["transferPaidFen"] == 1000
    assert len(total_data["relationRows"]) == 3
    assert len(total_data["withdrawalRows"]) == 2

    filtered = client.get(
        "/api/ops-admin/referral-analytics",
        headers=headers,
        params={"period": "total", "keyword": "被推荐甲"},
    )
    filtered_data = filtered.json()["data"]
    assert filtered_data["summary"]["referralCount"] == 3
    assert len(filtered_data["relationRows"]) == 1
    assert filtered_data["relationRows"][0]["inviteeUserId"] == invitee_a["id"]
