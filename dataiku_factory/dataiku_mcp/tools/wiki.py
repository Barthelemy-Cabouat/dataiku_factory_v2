"""
Wiki management tools for Dataiku DSS.

Provides functions for listing, reading, creating, and updating wiki articles
in Dataiku DSS projects through the dataiku-api-client.
"""

from typing import Dict, List, Optional, Any
from dataiku_mcp.client import get_client, get_project


def list_articles(project_key: str) -> Dict[str, Any]:
    """
    List all wiki articles in a project.

    Args:
        project_key: The project key

    Returns:
        Dict with status, list of articles (id, name), and total count
    """
    try:
        project = get_project(project_key)
        wiki = project.get_wiki()
        articles = []
        for a in wiki.list_articles():
            data = a.get_data()
            articles.append({
                "id": a.article_id,
                "name": data.get_name(),
            })
        return {
            "status": "ok",
            "project_key": project_key,
            "articles": articles,
            "total_count": len(articles),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to list wiki articles in '{project_key}': {str(e)}",
        }


def get_article(project_key: str, article_id: int) -> Dict[str, Any]:
    """
    Get the content of a wiki article by id.

    Args:
        project_key: The project key
        article_id:  Integer article id (obtain via list_articles)

    Returns:
        Dict with status, article name, and body text
    """
    try:
        project = get_project(project_key)
        wiki = project.get_wiki()
        article = wiki.get_article(article_id)
        data = article.get_data()
        return {
            "status": "ok",
            "project_key": project_key,
            "article_id": article_id,
            "name": data.get_name(),
            "body": data.get_body(),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get wiki article {article_id} in '{project_key}': {str(e)}",
        }


def create_article(
    project_key: str,
    article_name: str,
    body: str,
    parent_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create a new wiki article.

    Args:
        project_key:  The project key
        article_name: Title of the new article
        body:         Markdown / HTML content
        parent_id:    Optional parent article id for nesting

    Returns:
        Dict with status and new article id
    """
    try:
        project = get_project(project_key)
        wiki = project.get_wiki()
        article = wiki.create_article(article_name, parent_id=parent_id, content=body)
        return {
            "status": "ok",
            "project_key": project_key,
            "article_id": article.article_id,
            "article_name": article_name,
            "message": f"Article '{article_name}' created successfully (id={article.article_id})",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to create wiki article '{article_name}' in '{project_key}': {str(e)}",
        }


def update_article(
    project_key: str,
    article_id: int,
    body: Optional[str] = None,
    article_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update an existing wiki article's body and/or title.

    Args:
        project_key:  The project key
        article_id:   Integer article id (obtain via list_articles)
        body:         New markdown / HTML content (omit to keep existing)
        article_name: New article title (omit to keep existing)

    Returns:
        Dict with status and updated fields
    """
    try:
        project = get_project(project_key)
        wiki = project.get_wiki()
        article = wiki.get_article(article_id)
        data = article.get_data()

        updated_fields = []
        if body is not None:
            data.set_body(body)
            updated_fields.append("body")
        if article_name is not None:
            data.set_name(article_name)
            updated_fields.append("name")

        if not updated_fields:
            return {
                "status": "ok",
                "project_key": project_key,
                "article_id": article_id,
                "updated_fields": [],
                "message": "Nothing to update — no body or name provided",
            }

        data.save()
        return {
            "status": "ok",
            "project_key": project_key,
            "article_id": article_id,
            "updated_fields": updated_fields,
            "message": f"Article {article_id} updated successfully",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to update wiki article {article_id} in '{project_key}': {str(e)}",
        }
