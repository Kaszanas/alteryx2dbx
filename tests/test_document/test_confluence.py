from unittest.mock import MagicMock, patch
from alteryx2dbx.document.confluence import (
    publish_draft,
    confluence_available,
    pat_setup_guide,
)


def test_confluence_available_when_installed():
    result = confluence_available()
    assert isinstance(result, bool)


def test_publish_draft_creates_page():
    mock_confluence = MagicMock()
    mock_confluence.get_page_by_title.return_value = None
    mock_confluence.create_page.return_value = {
        "id": "12345",
        "_links": {
            "base": "https://test.atlassian.net/wiki",
            "webui": "/spaces/TEST/pages/12345",
        },
    }

    config = {
        "confluence": {
            "url": "https://test.atlassian.net",
            "space": "TEST",
            "parent_page": "Migration Reports",
            "pat": "fake-token",
        }
    }
    markdown = "# Test Report\n\nSome content."

    with patch(
        "alteryx2dbx.document.confluence._get_confluence_client",
        return_value=mock_confluence,
    ):
        result = publish_draft(config, "Test Workflow", markdown)

    mock_confluence.create_page.assert_called_once()
    assert result is not None


def test_publish_draft_updates_existing_page():
    mock_confluence = MagicMock()
    mock_confluence.get_page_by_title.return_value = {"id": "99999"}
    mock_confluence.update_page.return_value = {
        "id": "99999",
        "_links": {
            "base": "https://test.atlassian.net/wiki",
            "webui": "/spaces/TEST/pages/99999",
        },
    }

    config = {
        "confluence": {
            "url": "https://test.atlassian.net",
            "space": "TEST",
            "parent_page": "Migration Reports",
            "pat": "fake-token",
        }
    }
    markdown = "# Updated Report\n\nNew content."

    with patch(
        "alteryx2dbx.document.confluence._get_confluence_client",
        return_value=mock_confluence,
    ):
        result = publish_draft(config, "Test Workflow", markdown)

    mock_confluence.update_page.assert_called_once()
    assert result is not None


def test_pat_setup_guide_returns_string():
    guide = pat_setup_guide()
    assert isinstance(guide, str)
    assert "Personal Access Token" in guide
