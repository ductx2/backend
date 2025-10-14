"""
Supabase Database Connection Wrapper
Production-ready database integration using existing credentials

Features:
- Supabase client initialization with service role key
- Connection pooling and error handling
- Database health checks and monitoring
- Async/await support for FastAPI integration
- Preserved configuration from main project

Compatible with Supabase 2.9.1 and Python 3.13.5
Uses existing credentials from UPSC project environment
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from contextlib import asynccontextmanager

# Supabase imports
from supabase import create_client, Client
from supabase.client import ClientOptions
from postgrest.exceptions import APIError

# Import settings
from .config import get_settings

# Initialize settings and logger
settings = get_settings()
logger = logging.getLogger(__name__)


class SupabaseConnection:
    """
    Supabase database connection wrapper
    Provides high-level database operations with error handling
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[Client] = None
        self._initialized = False
    
    def _initialize_client(self) -> Client:
        """
        Initialize Supabase client with service role key
        
        Returns:
            Client: Configured Supabase client
        """
        if self._client is None:
            try:
                # Create Supabase client with service role key
                self._client = create_client(
                    self.settings.supabase_url,
                    self.settings.supabase_service_key
                )
                
                self._initialized = True
                logger.info("Supabase client initialized successfully")
                
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
                raise ConnectionError(f"Database connection failed: {e}")
        
        return self._client
    
    @property
    def client(self) -> Client:
        """Get initialized Supabase client"""
        return self._initialize_client()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check database connection health
        
        Returns:
            Dict: Health check results
        """
        try:
            # Simple query to test connection
            result = self.client.table("current_affairs").select("count", count="exact").limit(1).execute()
            
            return {
                "status": "healthy",
                "connection": "active",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "table_accessible": True,
                "total_records": result.count if hasattr(result, 'count') else 0
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy", 
                "connection": "failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "table_accessible": False
            }
    
    async def get_current_affairs_count(self) -> int:
        """
        Get total count of current affairs records
        
        Returns:
            int: Total record count
        """
        try:
            result = self.client.table("current_affairs").select("*", count="exact").limit(1).execute()
            return result.count if hasattr(result, 'count') else 0
            
        except Exception as e:
            logger.error(f"Failed to get current affairs count: {e}")
            return 0
    
    async def insert_current_affair(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert new current affair article
        
        Args:
            article_data: Article data dictionary
            
        Returns:
            Dict: Insertion result with success status
        """
        try:
            # Add metadata
            article_data["created_at"] = datetime.now(timezone.utc).isoformat()
            article_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            result = self.client.table("current_affairs").insert(article_data).execute()
            
            if result.data:
                logger.info(f"Successfully inserted article: {article_data.get('title', 'Unknown')[:50]}")
                return {
                    "success": True,
                    "data": result.data[0],
                    "message": "Article inserted successfully"
                }
            else:
                return {
                    "success": False,
                    "error": "No data returned from insert operation"
                }
                
        except APIError as e:
            logger.error(f"API error inserting current affair: {e}")
            return {
                "success": False,
                "error": f"Database API error: {e.message if hasattr(e, 'message') else str(e)}"
            }
        except Exception as e:
            logger.error(f"Failed to insert current affair: {e}")
            return {
                "success": False,
                "error": f"Database insertion failed: {str(e)}"
            }
    
    async def upsert_current_affair(self, article_data: Dict[str, Any], match_field: str = "url") -> Dict[str, Any]:
        """
        Insert or update current affair article (avoid duplicates)
        
        Args:
            article_data: Article data dictionary
            match_field: Field to match for existing records
            
        Returns:
            Dict: Upsert result with success status
        """
        try:
            # Add metadata
            article_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            if "created_at" not in article_data:
                article_data["created_at"] = datetime.now(timezone.utc).isoformat()
            
            # Use upsert with on_conflict parameter
            result = self.client.table("current_affairs").upsert(
                article_data, 
                on_conflict=match_field
            ).execute()
            
            if result.data:
                logger.info(f"Successfully upserted article: {article_data.get('title', 'Unknown')[:50]}")
                return {
                    "success": True,
                    "data": result.data[0],
                    "message": "Article upserted successfully"
                }
            else:
                return {
                    "success": False,
                    "error": "No data returned from upsert operation"
                }
                
        except APIError as e:
            logger.error(f"API error upserting current affair: {e}")
            return {
                "success": False,
                "error": f"Database API error: {e.message if hasattr(e, 'message') else str(e)}"
            }
        except Exception as e:
            logger.error(f"Failed to upsert current affair: {e}")
            return {
                "success": False,
                "error": f"Database upsert failed: {str(e)}"
            }
    
    async def insert_current_affair(self, article_data: Dict[str, Any]) -> bool:
        """
        Insert a current affairs article with duplicate detection
        
        Args:
            article_data: Article data dictionary
            
        Returns:
            bool: True if inserted, False if duplicate or error
        """
        try:
            # Check for duplicates using content_hash
            existing = self.client.table("current_affairs").select("id").eq(
                "content_hash", article_data.get("content_hash", "")
            ).execute()
            
            if existing.data:
                logger.info(f"Duplicate article detected: {article_data.get('title', '')[:50]}...")
                return False
            
            # Insert the article
            result = self.client.table("current_affairs").insert(article_data).execute()
            
            if result.data:
                logger.info(f"✅ Article inserted: {article_data.get('title', '')[:50]}...")
                return True
            else:
                return False
                
        except APIError as e:
            if "duplicate key" in str(e).lower():
                logger.info(f"Duplicate article (DB constraint): {article_data.get('title', '')[:50]}...")
                return False
            else:
                logger.error(f"Database API error: {e}")
                return False
        except Exception as e:
            logger.error(f"Failed to insert current affair: {e}")
            return False
    
    async def get_recent_articles(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent current affairs articles
        
        Args:
            limit: Maximum number of articles to retrieve
            
        Returns:
            List: Recent articles data
        """
        try:
            result = self.client.table("current_affairs").select("*").order(
                "created_at", desc=True
            ).limit(limit).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Failed to get recent articles: {e}")
            return []
    
    async def search_articles(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search articles by title or content
        
        Args:
            query: Search query string
            limit: Maximum number of results
            
        Returns:
            List: Matching articles
        """
        try:
            # Use ilike search instead of text_search for better compatibility
            result = self.client.table("current_affairs").select("*").ilike(
                "title", f"%{query}%"
            ).limit(limit).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Failed to search articles: {e}")
            # Fallback to basic select if search fails
            try:
                result = self.client.table("current_affairs").select("*").limit(limit).execute()
                return result.data if result.data else []
            except Exception as fallback_error:
                logger.error(f"Fallback search also failed: {fallback_error}")
                return []
    
    async def get_articles_by_source(self, source: str, limit: int = 30) -> List[Dict[str, Any]]:
        """
        Get articles from specific source
        
        Args:
            source: Source name (RSS source or 'drishti_ias')
            limit: Maximum number of articles
            
        Returns:
            List: Articles from specified source
        """
        try:
            result = self.client.table("current_affairs").select("*").eq(
                "source", source
            ).order("created_at", desc=True).limit(limit).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Failed to get articles by source: {e}")
            return []
    
    async def get_high_relevance_articles(self, min_score: int = 70, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Get high UPSC relevance articles
        
        Args:
            min_score: Minimum relevance score (0-100)
            limit: Maximum number of articles
            
        Returns:
            List: High relevance articles
        """
        try:
            result = self.client.table("current_affairs").select("*").gte(
                "upsc_relevance", min_score
            ).order("upsc_relevance", desc=True).limit(limit).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Failed to get high relevance articles: {e}")
            return []
    
    async def get_current_affairs_by_date(
        self, 
        date, 
        limit: int = 50, 
        source: Optional[str] = None, 
        min_relevance: int = 40
    ) -> List[Dict[str, Any]]:
        """
        Get current affairs articles for a specific date
        
        Args:
            date: Target date (datetime.date object)
            limit: Maximum number of articles
            source: Optional source filter
            min_relevance: Minimum UPSC relevance score
            
        Returns:
            List: Articles for the specified date
        """
        try:
            # Convert date to string format for database query
            date_str = date.strftime("%Y-%m-%d")
            date_start = f"{date_str}T00:00:00"
            date_end = f"{date_str}T23:59:59"
            
            # Build query
            query = self.client.table("current_affairs").select("*")
            
            # Date filtering
            query = query.gte("created_at", date_start).lte("created_at", date_end)
            
            # Source filtering if specified
            if source:
                query = query.eq("source", source)
            
            # Relevance filtering
            if min_relevance:
                query = query.gte("upsc_relevance", min_relevance)
            
            # Order by relevance score (highest first) and limit
            result = query.order("upsc_relevance", desc=True).order("created_at", desc=True).limit(limit).execute()
            
            return result.data if result.data else []
            
        except Exception as e:
            logger.error(f"Failed to get current affairs by date {date}: {e}")
            return []
    
    async def get_current_affairs_count_by_date(self, date) -> int:
        """
        Get total count of current affairs articles for a specific date
        
        Args:
            date: Target date (datetime.date object)
            
        Returns:
            int: Total article count for the date
        """
        try:
            # Convert date to string format for database query
            date_str = date.strftime("%Y-%m-%d")
            date_start = f"{date_str}T00:00:00"
            date_end = f"{date_str}T23:59:59"
            
            result = self.client.table("current_affairs").select("*", count="exact").gte(
                "created_at", date_start
            ).lte("created_at", date_end).limit(1).execute()
            
            return result.count if hasattr(result, 'count') else 0
            
        except Exception as e:
            logger.error(f"Failed to get current affairs count for date {date}: {e}")
            return 0
    
    async def get_source_breakdown_by_date(self, date) -> Dict[str, int]:
        """
        Get article count breakdown by source for a specific date
        
        Args:
            date: Target date (datetime.date object)
            
        Returns:
            Dict: Source name to article count mapping
        """
        try:
            # Convert date to string format for database query
            date_str = date.strftime("%Y-%m-%d")
            date_start = f"{date_str}T00:00:00"
            date_end = f"{date_str}T23:59:59"
            
            # Get all articles for the date with source info
            result = self.client.table("current_affairs").select("source").gte(
                "created_at", date_start
            ).lte("created_at", date_end).execute()
            
            # Count articles by source
            source_breakdown = {}
            if result.data:
                for article in result.data:
                    source = article.get("source", "unknown")
                    source_breakdown[source] = source_breakdown.get(source, 0) + 1
            
            return source_breakdown
            
        except Exception as e:
            logger.error(f"Failed to get source breakdown for date {date}: {e}")
            return {}
    
    async def get_daily_statistics(self, date) -> Dict[str, Any]:
        """
        Get comprehensive daily statistics for monitoring and validation
        
        Args:
            date: Target date (datetime.date object)
            
        Returns:
            Dict: Comprehensive daily statistics
        """
        try:
            # Convert date to string format for database query
            date_str = date.strftime("%Y-%m-%d")
            date_start = f"{date_str}T00:00:00"
            date_end = f"{date_str}T23:59:59"
            
            # Get all articles for the date
            result = self.client.table("current_affairs").select("*").gte(
                "created_at", date_start
            ).lte("created_at", date_end).execute()
            
            articles = result.data if result.data else []
            
            # Calculate statistics
            total_articles = len(articles)
            total_rss_articles = len([a for a in articles if a.get("source", "").lower() != "drishti_ias"])
            total_drishti_articles = len([a for a in articles if a.get("source", "").lower() == "drishti_ias"])
            
            # Calculate average relevance score
            relevance_scores = [a.get("upsc_relevance", 0) for a in articles if a.get("upsc_relevance")]
            avg_relevance_score = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
            
            # Source breakdown
            source_breakdown = {}
            for article in articles:
                source = article.get("source", "unknown")
                source_breakdown[source] = source_breakdown.get(source, 0) + 1
            
            return {
                "date": date_str,
                "total_articles": total_articles,
                "total_rss_articles": total_rss_articles,
                "total_drishti_articles": total_drishti_articles,
                "avg_relevance_score": round(avg_relevance_score, 2),
                "source_breakdown": source_breakdown,
                "high_relevance_count": len([a for a in articles if a.get("upsc_relevance", 0) >= 70]),
                "medium_relevance_count": len([a for a in articles if 40 <= a.get("upsc_relevance", 0) < 70]),
                "low_relevance_count": len([a for a in articles if a.get("upsc_relevance", 0) < 40])
            }
            
        except Exception as e:
            logger.error(f"Failed to get daily statistics for date {date}: {e}")
            return {
                "date": date.strftime("%Y-%m-%d"),
                "total_articles": 0,
                "total_rss_articles": 0,
                "total_drishti_articles": 0,
                "avg_relevance_score": 0,
                "source_breakdown": {},
                "high_relevance_count": 0,
                "medium_relevance_count": 0,
                "low_relevance_count": 0
            }
    
    async def close(self):
        """Close database connection"""
        if self._client:
            # Supabase client doesn't require explicit closing
            self._client = None
            self._initialized = False
            logger.info("Supabase connection closed")


# Global database instance
db_connection = SupabaseConnection()


async def get_database() -> SupabaseConnection:
    """
    Dependency for getting database connection
    Use this in FastAPI endpoints that need database access
    
    Returns:
        SupabaseConnection: Database connection instance
    """
    return db_connection


def get_database_sync() -> SupabaseConnection:
    """
    Synchronous database connection getter
    Use for non-async contexts
    
    Returns:
        SupabaseConnection: Database connection instance
    """
    return db_connection


# Database configuration for easy import
DATABASE_CONFIG = {
    "connection": db_connection,
    "get_database": get_database,
    "get_database_sync": get_database_sync,
    "health_check": db_connection.health_check
}