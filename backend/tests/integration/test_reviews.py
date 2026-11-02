"""C12 review of a run and report publication (machine outputs never change)."""

import psycopg
import pytest
from legal_checker.api.auth import current_actor
from legal_checker.core.postgres import connect_postgres
from legal_checker.core.security import Actor
from test_assessment_runs import CASE, env, start  # noqa: F401  (fixture re-export)


@pytest.fixture
def run(env):  # noqa: F811
    env.source.real_steps_5_7 = True  # group C's steps 5–7 produce reviewable findings
    run_id = start(env.client)["context"]["run_id"]
    env.base = f"/api/v1/cases/{CASE}/runs/{run_id}"
    env.run_id = run_id
    return env


def state(ctx):
    return ctx.client.get(f"{ctx.base}/review-state").json()


def target(ctx, kind):
    return next(t for t in state(ctx)["targets"] if t["doi_tuong_loai"] == kind)


def review(ctx, item, action, reason="Đã đối chiếu", after=None, sha=None):
    return ctx.client.post(
        f"{ctx.base}/reviews",
        json={
            "target": {
                "doi_tuong_loai": item["doi_tuong_loai"],
                "doi_tuong_id": item["doi_tuong_id"],
            },
            "action": action,
            "after": after or {},
            "reason": reason,
            "expected_target_sha256": sha or item["target_sha256"],
        },
    )


def machine_report(ctx):
    return ctx.client.get(f"{ctx.base}/reports").json()["items"][-1]["report"]


def test_reviews_are_appended_with_optimistic_concurrency(run):
    criterion = target(run, "ket_qua_tieu_chi")
    confirmed = review(run, criterion, "CONFIRM")
    assert confirmed.status_code == 201, confirmed.text
    event = confirmed.json()["review"]
    assert event["actor_id"] == "USER_TEST" and event["before"]["target_sha256"]
    assert target(run, "ket_qua_tieu_chi")["latest_decision"] == "CONFIRM"

    current = target(run, "ket_qua_tieu_chi")
    new_finding = "VIOLATED" if current["overrides"].get("finding") != "VIOLATED" else "MISSING"
    overridden = review(run, current, "OVERRIDE", after={"finding": new_finding})
    assert overridden.status_code == 201, overridden.text
    after = target(run, "ket_qua_tieu_chi")
    assert after["overrides"] == {"finding": new_finding}
    assert after["target_sha256"] != current["target_sha256"]
    # A reviewer still holding the old hash cannot silently overwrite the override.
    stale = review(run, current, "OVERRIDE", after={"finding": "UNKNOWN"})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_REVIEW"

    history = run.client.get(f"{run.base}/reviews").json()
    assert history["total"] == 2
    assert [r["review"]["action"] for r in history["items"]] == ["CONFIRM", "OVERRIDE"]


@pytest.mark.parametrize(
    "action,after",
    [
        ("OVERRIDE", {"ket_qua_id": "X"}),  # not an editable field
        ("OVERRIDE", {"finding": "MAYBE"}),  # not schema-valid
        ("OVERRIDE", {}),
        ("COMMENT", {"finding": "SATISFIED"}),  # only OVERRIDE carries values
    ],
)
def test_invalid_reviews_are_rejected(run, action, after):
    response = review(run, target(run, "ket_qua_tieu_chi"), action, after=after)
    assert response.status_code == 422


def test_unknown_targets_and_missing_roles_are_rejected(run):
    fake = {
        "doi_tuong_loai": "ket_qua_tieu_chi",
        "doi_tuong_id": "KQ_OTHER_RUN",
        "target_sha256": "a" * 64,
    }
    assert review(run, fake, "CONFIRM").status_code == 422
    run.app.dependency_overrides[current_actor] = lambda: Actor(
        "VIEWER", "TENANT_TEST", frozenset({"viewer"})
    )
    try:
        assert review(run, target(run, "ket_qua_tieu_chi"), "CONFIRM").status_code == 403
    finally:
        run.app.dependency_overrides.clear()


def test_review_events_are_append_only_and_mirrored_to_c12(run):
    review(run, target(run, "ket_qua_tuan_thu"), "COMMENT", reason="Cần xem phụ lục")
    with connect_postgres(run.database_url) as connection:
        mirrored = connection.execute(
            "SELECT hanh_dong, ly_do, gia_tri_truoc_json FROM runtime.nhat_ky_review "
            "WHERE ca_id=%s",
            (CASE,),
        ).fetchone()
        assert mirrored["hanh_dong"] == "COMMENT" and mirrored["ly_do"] == "Cần xem phụ lục"
        assert mirrored["gia_tri_truoc_json"]["run_id"] == run.run_id
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            connection.execute("UPDATE runtime.review_events SET reason='edited'")


def test_rebuilt_report_carries_the_review_layer_without_editing_machine_output(run):
    machine = machine_report(run)
    criterion = target(run, "ket_qua_tieu_chi")
    original = next(
        c["finding"]
        for c in machine["report_json"]["compliance"]["criterion_results"]
        if c["ket_qua_id"] == criterion["doi_tuong_id"]
    )
    new_finding = "VIOLATED" if original != "VIOLATED" else "MISSING"
    review(run, criterion, "OVERRIDE", after={"finding": new_finding})
    rebuilt = run.client.post(f"{run.base}/reports").json()
    report = rebuilt["report"]
    assert rebuilt["review_revision"] == state(run)["review_revision"] != "none"
    assert report["bao_cao_id"] != machine["bao_cao_id"]
    assert report["review_status"] == "IN_REVIEW" and report["report_status"] == "DRAFT"
    layer = report["report_json"]["audit"]["review"]
    assert layer["effective"]["ket_qua_tieu_chi"][criterion["doi_tuong_id"]] == {
        "finding": new_finding
    }
    still_machine = next(
        c["finding"]
        for c in report["report_json"]["compliance"]["criterion_results"]
        if c["ket_qua_id"] == criterion["doi_tuong_id"]
    )
    assert still_machine == original  # the AI result stays as produced
    versions = run.client.get(f"{run.base}/reports").json()
    assert versions["total"] == 2


def publish(ctx, bao_cao_id, revision):
    return ctx.client.post(
        f"/api/v1/reports/{bao_cao_id}/publish", json={"expected_review_revision": revision}
    )


def test_publication_requires_complete_current_review(run):
    machine = machine_report(run)
    nothing = publish(run, machine["bao_cao_id"], "none")
    assert nothing.status_code == 409 and nothing.json()["error"]["code"] == "REVIEW_REQUIRED"

    recommendation = target(run, "khuyen_nghi_danh_gia")
    review(run, recommendation, "REQUEST_MORE_EVIDENCE", reason="Thiếu phụ lục thanh toán")
    draft = run.client.post(f"{run.base}/reports").json()
    blocked = publish(run, draft["report"]["bao_cao_id"], draft["review_revision"])
    assert blocked.status_code == 409
    assert {d["reason"] for d in blocked.json()["error"]["details"]} >= {"REQUEST_MORE_EVIDENCE"}

    review(run, target(run, "khuyen_nghi_danh_gia"), "CONFIRM", reason="Đã nhận phụ lục")
    # The previous draft no longer reflects every review of the run.
    stale = publish(run, draft["report"]["bao_cao_id"], draft["review_revision"])
    assert stale.status_code == 409
    current = run.client.post(f"{run.base}/reports").json()
    blockers = state(run)["blockers"]
    for item in blockers:  # serious findings still unconfirmed in this fixture, if any
        review(run, target(run, item["doi_tuong_loai"]), "CONFIRM")
    if blockers:
        current = run.client.post(f"{run.base}/reports").json()
    published = publish(run, current["report"]["bao_cao_id"], current["review_revision"])
    assert published.status_code == 200, published.text
    report = published.json()["report"]
    assert report["report_status"] == "PUBLISHED" and report["review_status"] == "APPROVED"
    publication = report["report_json"]["audit"]["publication"]
    assert publication["published_by"] == "USER_TEST"
    assert publication["source_bao_cao_id"] == current["report"]["bao_cao_id"]
    again = publish(run, current["report"]["bao_cao_id"], current["review_revision"])
    assert again.json()["report"]["bao_cao_id"] == report["bao_cao_id"]  # idempotent
    assert publish(run, report["bao_cao_id"], current["review_revision"]).status_code == 409
