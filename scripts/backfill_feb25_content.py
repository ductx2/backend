"""
Backfill Feb 25 stub articles with full HTML content.

Re-extracts content for articles where LENGTH(content) < 500 on 2026-02-25.
Only updates `content` and `summary` fields -- does NOT touch knowledge card layers.

DB operations: via SSH -> docker exec psql (same pattern as npm run db:sql).
For large content updates: SCP SQL file to VPS, then docker cp + psql -f.
Content extraction: local Python (HTTP requests to source sites).

Usage:
    cd backend && python scripts/backfill_feb25_content.py
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Load env vars from parent directory (.env in project root)
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(env_path)

# Add backend to sys.path so we can import app modules
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

# Import content extractor
from app.services.content_extractor import UniversalContentExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# VPS connection details (from scripts/vps-db.sh)
VPS_HOST = "ubuntu@15.235.187.137"
DB_USER = "supabase_admin"
DB_NAME = "postgres"
SSH_OPTS = ["-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3"]


def ssh_cmd(remote_cmd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a command on VPS via SSH."""
    cmd = ["ssh"] + SSH_OPTS + [VPS_HOST, remote_cmd]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def scp_to_vps(local_path: str, remote_path: str, timeout: int = 30) -> None:
    """Copy a file to the VPS via SCP."""
    cmd = ["scp"] + SSH_OPTS + [local_path, f"{VPS_HOST}:{remote_path}"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"SCP failed: {result.stderr}")


def run_sql(query: str, timeout: int = 30) -> str:
    """Run a short SQL query on VPS via SSH + docker exec psql."""
    # For short queries, pass inline
    remote_cmd = (
        f'docker exec supabase-db psql -U {DB_USER} -d {DB_NAME} '
        f'-c "{query}"'
    )
    result = ssh_cmd(remote_cmd, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"SQL failed: {result.stderr}")
    return result.stdout


def run_sql_json(query: str, timeout: int = 30) -> list[dict]:
    """Run SQL query and return results as list of dicts (JSON output)."""
    json_query = f"SELECT json_agg(t) FROM ({query}) t"
    remote_cmd = (
        f'docker exec supabase-db psql -U {DB_USER} -d {DB_NAME} '
        f'-t -A -c "{json_query}"'
    )
    result = ssh_cmd(remote_cmd, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"SQL failed: {result.stderr}")
    output = result.stdout.strip()
    if not output or output == "null":
        return []
    return json.loads(output)


def run_sql_file(sql_content: str, timeout: int = 60) -> str:
    """Write SQL to a temp file, SCP to VPS, docker cp into container, execute."""
    vps_tmp = "/tmp/backfill_update.sql"
    container_tmp = "/tmp/backfill_update.sql"

    # Write SQL to local temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sql", delete=False, encoding="utf-8") as f:
        f.write(sql_content)
        local_tmp = f.name

    try:
        # SCP to VPS
        scp_to_vps(local_tmp, vps_tmp, timeout=30)

        # docker cp into the container
        result = ssh_cmd(
            f"docker cp {vps_tmp} supabase-db:{container_tmp}",
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(f"docker cp failed: {result.stderr}")

        # Execute inside the container
        result = ssh_cmd(
            f'docker exec supabase-db psql -U {DB_USER} -d {DB_NAME} -f {container_tmp}',
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"psql -f failed: {result.stderr}")

        # Cleanup remote files
        ssh_cmd(f"rm -f {vps_tmp}", timeout=10)
        ssh_cmd(f"docker exec supabase-db rm -f {container_tmp}", timeout=10)

        return result.stdout
    finally:
        os.unlink(local_tmp)


def update_article(article_id: str, content: str, summary: str | None) -> bool:
    """Update article content via SQL file (handles large content safely)."""
    try:
        # Use dollar-quoting to avoid escaping issues with HTML content
        # Choose a unique dollar-tag unlikely to appear in content
        dollar_tag = "$BACKFILL$"
        if dollar_tag in content:
            dollar_tag = "$BF2$"
        if summary and len(summary) > 10:
            if dollar_tag in summary:
                dollar_tag = "$BF3$"
            sql = (
                f"UPDATE current_affairs\n"
                f"SET content = {dollar_tag}{content}{dollar_tag},\n"
                f"    summary = {dollar_tag}{summary}{dollar_tag}\n"
                f"WHERE id = '{article_id}';\n"
            )
        else:
            sql = (
                f"UPDATE current_affairs\n"
                f"SET content = {dollar_tag}{content}{dollar_tag}\n"
                f"WHERE id = '{article_id}';\n"
            )
        run_sql_file(sql, timeout=60)
        return True
    except Exception as e:
        logger.error(f"  FAIL: DB update error: {e}")
        return False


def fetch_stub_articles() -> list[dict]:
    """Fetch Feb 25 articles with content < 500 chars via SSH SQL."""
    query = (
        "SELECT id::text, title, source_url, LENGTH(content) as content_len "
        "FROM current_affairs "
        "WHERE date = '2026-02-25' AND LENGTH(content) < 500 "
        "ORDER BY LENGTH(content) ASC"
    )
    return run_sql_json(query, timeout=30)


async def backfill() -> None:
    """Main backfill logic."""
    extractor = UniversalContentExtractor()

    logger.info("=" * 60)
    logger.info("BACKFILL: Feb 25 stub articles")
    logger.info("=" * 60)

    stubs = fetch_stub_articles()
    logger.info(f"Found {len(stubs)} stub articles (content < 500 chars)")

    if not stubs:
        logger.info("No stub articles found. Nothing to do.")
        return

    updated = 0
    skipped = 0
    failed = 0

    for i, article in enumerate(stubs, 1):
        article_id = str(article["id"])
        title = (article.get("title") or "???")[:80]
        source_url = article.get("source_url") or ""
        old_len = article.get("content_len") or 0

        logger.info(f"\n[{i}/{len(stubs)}] {title}")
        logger.info(f"  URL: {source_url}")
        logger.info(f"  Current content length: {old_len}")

        if not source_url:
            logger.warning("  SKIP: No source_url")
            skipped += 1
            continue

        try:
            extracted = await extractor.extract_content(source_url)
        except Exception as e:
            logger.error(f"  FAIL: Extraction exception: {e}")
            failed += 1
            continue

        if not extracted:
            logger.warning("  SKIP: Extraction returned None (paywall/403/418)")
            skipped += 1
            continue

        new_content = extracted.content
        new_summary = extracted.summary

        # Validate: must have <p> tags AND length > 200 AND longer than original
        has_p_tags = "<p>" in new_content
        is_long_enough = len(new_content) > 200
        is_improvement = len(new_content) > old_len

        if not has_p_tags or not is_long_enough:
            logger.warning(
                f"  SKIP: Extracted content too short or no <p> tags "
                f"(len={len(new_content)}, has_p={has_p_tags})"
            )
            skipped += 1
            continue

        if not is_improvement:
            logger.warning(
                f"  SKIP: New content not longer than existing "
                f"(new={len(new_content)}, old={old_len})"
            )
            skipped += 1
            continue

        if update_article(article_id, new_content, new_summary):
            updated += 1
            logger.info(
                f"  UPDATED: {old_len} -> {len(new_content)} chars "
                f"(summary={'yes' if new_summary and len(new_summary) > 10 else 'no'})"
            )
        else:
            failed += 1

    logger.info("\n" + "=" * 60)
    logger.info("BACKFILL COMPLETE")
    logger.info(f"  Updated: {updated}")
    logger.info(f"  Skipped: {skipped}")
    logger.info(f"  Failed:  {failed}")
    logger.info(f"  Total:   {len(stubs)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(backfill())
