"""Standalone pipeline: crawl → extract text → chunk → embed → Qdrant."""

from app.services.crawl_ingestion.service import CrawlIngestionPipeline

__all__ = ["CrawlIngestionPipeline"]
