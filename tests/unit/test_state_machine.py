import pytest
from app.core.context import Actor, Ctx
from app.core.errors import InvalidTransition
from app.workflows import state_machine as sm


class FakeDB:
    def __init__(self):
        self.added = []

    def add(self, o):
        self.added.append(o)


class P:
    def __init__(self, status):
        import uuid

        self.id = uuid.uuid4()
        self.status = status
        self.resume_status = None
        self.retry_count = 0
        self.progress = 0


def ctx():
    return Ctx(db=FakeDB(), actor=Actor(type="SYSTEM", id=None, label="test"), mode="DEMO")


def test_main_flow_is_reachable_in_order():
    for a, b in zip(sm.MAIN_FLOW, sm.MAIN_FLOW[1:], strict=False):
        if a == "FEEDBACK_REVIEW":
            continue
        assert sm.can_transition(a, b), f"{a} → {b}"


def test_has_exactly_16_main_and_4_exception_states():
    assert len(sm.MAIN_FLOW) == 16
    assert set(sm.EXCEPTION_STATES) == {"FAILED", "CANCELLED", "RETRY_PENDING", "NEEDS_MANUAL_ACTION"}


@pytest.mark.parametrize("a,b", [("CREATED", "APPROVED"), ("SCRIPT_REVIEW", "PUBLISHED"), ("FINAL_QC", "APPROVED"),
                                 ("CANCELLED", "CREATED"), ("PUBLISHED", "CANCELLED"), ("APPROVAL_PENDING", "PUBLISHED")])
def test_invalid_transitions_rejected(a, b):
    p = P(a)
    with pytest.raises(InvalidTransition):
        sm.transition(ctx(), p, b)
    assert p.status == a


def test_transition_records_event_and_progress():
    c = ctx()
    p = P("CREATED")
    sm.transition(c, p, "SCRIPT_GENERATING", note="x")
    assert p.status == "SCRIPT_GENERATING" and p.progress > 0
    assert any(type(o).__name__ == "WorkflowEvent" for o in c.db.added)
    assert any(type(o).__name__ == "AuditLog" for o in c.db.added)


def test_retry_resumes_only_failed_step():
    c = ctx()
    p = P("RENDERING")
    sm.transition(c, p, "RETRY_PENDING")
    assert p.resume_status == "RENDERING"
    with pytest.raises(InvalidTransition):
        sm.transition(c, p, "GENERATING")
    sm.transition(c, p, "RENDERING")
    assert p.retry_count == 1


def test_cancel_allowed_until_published():
    for s in sm.ALL_STATES:
        if s in sm.NON_CANCELLABLE:
            assert "CANCELLED" not in sm.TRANSITIONS[s]
        else:
            assert "CANCELLED" in sm.TRANSITIONS[s]


def test_every_state_has_step_spec_with_owner():
    for s in sm.ALL_STATES:
        assert sm.STEPS[s].owner and sm.STEPS[s].label


def test_failed_remembers_step_for_retry():
    c = ctx()
    p = P("RENDERING")
    sm.transition(c, p, "FAILED")
    sm.transition(c, p, "RETRY_PENDING")
    assert p.resume_status == "RENDERING"
    sm.transition(c, p, "RENDERING")
