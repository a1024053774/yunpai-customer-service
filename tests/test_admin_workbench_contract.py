"""The admin page must expose the API's rollback state without stale actions."""
from pathlib import Path


def test_admin_workbench_renders_rolled_back_state_without_rollback_action() -> None:
    html = Path("src/yunpai_customer_service/demo/static/admin.html").read_text(
        encoding="utf-8"
    )
    assert 'esc(x.status)' in html
    assert 'x.status === "approved"' in html
    assert 'data-action="rollback"' in html
    assert 'x.status === "rolled_back"' not in html
    # The action is guarded by approved status; rolled_back therefore has no button.
    assert 'x.status === "approved" ?' in html
