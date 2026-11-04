"""E5 交付可行性：清单与判定的回归测试。

这一项跟 E1/E4 不同——它不是从数据算出来的，是把「该问主办方什么」
问对之后拼成 go/no-go。所以测试重点不是数值精度，而是**判定逻辑不许被稀释**：

    7 项 ok + 1 项做不到  ≠  "基本可行"
    7 项 ok + 1 项没问到  ≠  "通过"

历史上最容易出的错是「加权」：一旦把约束做成可补偿的分数，就会出现
「其他项都不错所以消防不过也能去」。这条在 self_check 和这里都要钉住。
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.persona.e5 import (
    CHECKLIST_BY_ID,
    E5_CHECKLIST,
    evaluate,
    self_check,
)

ALL_IDS = [it.id for it in E5_CHECKLIST]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ============================================================
# 清单
# ============================================================

def test_checklist_has_eight_items(client):
    r = client.get("/api/persona/e5/checklist")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] == 8
    assert len(data["items"]) == 8
    assert {i["id"] for i in data["items"]} == set(ALL_IDS)


def test_every_item_has_a_question_to_ask(client):
    """清单的价值全在 ask —— 没有具体问题的条目等于没写。"""
    data = client.get("/api/persona/e5/checklist").json()["data"]
    for it in data["items"]:
        assert it["ask"], f"{it['id']} 缺 ask"
        assert "问" in it["ask"], f"{it['id']} 的 ask 不像一句能照着念的问话"
        assert it["why"], f"{it['id']} 缺 why"
        assert it["short_consequence"] in ("block", "cost")


def test_cost_items_must_offer_a_fallback(client):
    """判为「能做到但要加钱」的项，必须给出替代方案，否则用户只知道要花钱不知道为什么。"""
    data = client.get("/api/persona/e5/checklist").json()["data"]
    for it in data["items"]:
        if it["short_consequence"] == "cost":
            assert it["fallback"], f"{it['id']} 是 cost 类却没给 fallback"


def test_checklist_with_unknown_slug_404(client):
    assert client.get("/api/persona/e5/checklist?slug=__not_exist__").status_code == 404


# ============================================================
# 判定
# ============================================================

def _post(client, states, slug=None):
    return client.post(
        "/api/persona/e5/evaluate",
        json={"expo_slug": slug, "states": states},
    )


def test_all_ok_is_pass(client):
    r = _post(client, {i: "ok" for i in ALL_IDS})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["verdict"] == "pass"
    assert d["blocked"] == [] and d["extra_cost"] == [] and d["unresolved"] == []


def test_one_block_beats_everything(client):
    """核心用例：其余七项全 ok，只有层高不够 → 必须直接不可行。"""
    states = {i: "ok" for i in ALL_IDS}
    states["height"] = "short"
    d = _post(client, states).json()["data"]
    assert d["verdict"] == "blocked"
    assert [b["id"] for b in d["blocked"]] == ["height"]


def test_block_wins_over_unknown(client):
    """已知做不到就不必等未知项——先去问也不会改变结论。"""
    d = _post(client, {"height": "short"}).json()["data"]
    assert d["verdict"] == "blocked"


def test_empty_input_is_incomplete_not_pass(client):
    """漏填不等于满足：默认必须是最保守的状态。"""
    d = _post(client, {}).json()["data"]
    assert d["verdict"] == "incomplete"
    assert len(d["unresolved"]) == 8


def test_partial_input_is_incomplete(client):
    d = _post(client, {"height": "ok", "power": "ok"}).json()["data"]
    assert d["verdict"] == "incomplete"
    assert len(d["unresolved"]) == 6


def test_cost_only_is_pass_with_cost(client):
    states = {i: "ok" for i in ALL_IDS}
    states["fire"] = "short"
    d = _post(client, states).json()["data"]
    assert d["verdict"] == "pass_with_cost"
    assert [c["id"] for c in d["extra_cost"]] == ["fire"]
    assert d["note"], "有额外成本时必须提示把它算进 E3"


def test_unknown_still_blocks_a_pass_even_with_cost(client):
    """7 ok + 1 cost + 1 未知 ≠ 通过。不知道的事没问完，就不能给结论。"""
    states = {i: "ok" for i in ALL_IDS}
    states["fire"] = "short"
    states["rigging"] = "unknown"
    d = _post(client, states).json()["data"]
    assert d["verdict"] == "incomplete"


def test_illegal_state_value_treated_as_unknown(client):
    """「大概吧」这种答案不能当 ok 用。"""
    d = _post(client, {"height": "大概吧"}).json()["data"]
    assert d["states"]["height"] == "unknown"
    assert d["verdict"] == "incomplete"


def test_unresolved_items_carry_their_question(client):
    """未解决项要连问题一起返回，用户才能直接照着问。"""
    d = _post(client, {}).json()["data"]
    for item in d["unresolved"]:
        assert item["ask"]
        assert item["id"] in CHECKLIST_BY_ID


# ============================================================
# na（不适用）—— 标摊展商不该被问层高
# ============================================================

NA_ITEMS = {i for i in ALL_IDS if CHECKLIST_BY_ID[i].na_allowed}


def test_na_set_is_exactly_the_custom_booth_items():
    """只能放行特装专属项。进场时间/供电/消防任何参展方都躲不开。"""
    assert NA_ITEMS == {"height", "floor_load", "freight", "contractor", "rigging"}
    for i in ("setup_window", "power", "fire"):
        assert not CHECKLIST_BY_ID[i].na_allowed, f"{i} 不应允许标不适用"


def test_standard_booth_exhibitor_can_finish(client):
    """标摊展商：特装项标 na，其余如实答 → 应当能拿到结论，而不是卡在 incomplete。"""
    states = {i: ("na" if i in NA_ITEMS else "ok") for i in ALL_IDS}
    d = _post(client, states).json()["data"]
    assert d["verdict"] == "pass"
    assert set(d["not_applicable"]) == NA_ITEMS
    assert d["unresolved"] == []


def test_all_na_cannot_fake_a_pass(client):
    """核心护栏：全部标「不适用」不能拿到通过，否则清单形同虚设。"""
    d = _post(client, {i: "na" for i in ALL_IDS}).json()["data"]
    assert d["verdict"] == "incomplete"
    assert {u["id"] for u in d["unresolved"]} == {"setup_window", "power", "fire"}


def test_na_on_disallowed_item_degrades_to_unknown(client):
    d = _post(client, {**{i: "ok" for i in ALL_IDS}, "power": "na"}).json()["data"]
    assert d["states"]["power"] == "unknown"
    assert "power" in [u["id"] for u in d["unresolved"]]


def test_na_does_not_mask_a_block(client):
    """把四项特装项标 na，第五项（层高）判不满足 → 仍然 blocked，不能靠 na 绕开。"""
    states = {i: ("na" if i in NA_ITEMS else "ok") for i in ALL_IDS}
    states["height"] = "short"
    d = _post(client, states).json()["data"]
    assert d["verdict"] == "blocked"
    assert [b["id"] for b in d["blocked"]] == ["height"]
    assert d["extra_cost"] == []


def test_checklist_exposes_na_allowed(client):
    data = client.get("/api/persona/e5/checklist").json()["data"]
    flags = {i["id"]: i["na_allowed"] for i in data["items"]}
    assert {k for k, v in flags.items() if v} == NA_ITEMS


# ============================================================
# 纯逻辑自检
# ============================================================

def test_self_check_passes():
    assert self_check() == []


def test_no_scoring_anywhere():
    """结构层面的护栏：结果里不许出现分数/权重这类可供加权的字段。"""
    r = evaluate({i: "ok" for i in ALL_IDS})
    forbidden = {"score", "total_score", "weight", "weighted", "points", "grade"}
    assert not (forbidden & set(r.keys())), "E5 是约束不是偏好，不应出现可加权的分数"
