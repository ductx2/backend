"""
Category Balance Configuration for Intelligent UPSC Curation
Based on actual UPSC exam pattern analysis (2024-2025)

This module defines the daily category targets and weights for ensuring
balanced content distribution matching real UPSC examination patterns.

Compatible with: Python 3.13+, FastAPI 0.116.1
Created: 2025-09-01
"""

from typing import Dict, Any
from enum import Enum

class UPSCCategory(str, Enum):
    """UPSC subject categories with exam pattern alignment"""
    CURRENT_AFFAIRS = "current_affairs"
    POLITY_GOVERNANCE = "polity_governance"
    ECONOMY_DEVELOPMENT = "economy_development"
    ENVIRONMENT_ECOLOGY = "environment_ecology"
    HISTORY_CULTURE = "history_culture"
    SCIENCE_TECHNOLOGY = "science_technology"

# Daily Category Targets Based on UPSC Exam Pattern Research
DAILY_CATEGORY_TARGETS: Dict[str, Dict[str, Any]] = {
    UPSCCategory.CURRENT_AFFAIRS: {
        "min": 5,
        "max": 7,
        "weight": 0.23,  # 22-24% of Prelims
        "description": "Current affairs, breaking news, government announcements"
    },
    UPSCCategory.POLITY_GOVERNANCE: {
        "min": 3,
        "max": 5,
        "weight": 0.18,  # 15-20% stable, constitutional focus
        "description": "Constitutional matters, governance, public administration"
    },
    UPSCCategory.ECONOMY_DEVELOPMENT: {
        "min": 3,
        "max": 4,
        "weight": 0.14,  # 13-15% application-based questions
        "description": "Economic policies, development programs, financial matters"
    },
    UPSCCategory.ENVIRONMENT_ECOLOGY: {
        "min": 3,
        "max": 5,
        "weight": 0.16,  # 15-18% declining but significant
        "description": "Environmental issues, climate change, biodiversity"
    },
    UPSCCategory.HISTORY_CULTURE: {
        "min": 3,
        "max": 4,
        "weight": 0.15,  # 14-16% bouncing back in 2025
        "description": "Historical events, cultural heritage, art and literature"
    },
    UPSCCategory.SCIENCE_TECHNOLOGY: {
        "min": 3,
        "max": 4,
        "weight": 0.14,  # 13-14% current affairs driven
        "description": "Science and technology developments, innovations"
    }
}

# Quality Thresholds for Each Category
CATEGORY_QUALITY_THRESHOLDS: Dict[str, Dict[str, int]] = {
    UPSCCategory.CURRENT_AFFAIRS: {
        "factual_min": 60,      # High factual content needed
        "analytical_min": 40,   # Moderate analytical depth
        "composite_min": 100
    },
    UPSCCategory.POLITY_GOVERNANCE: {
        "factual_min": 70,      # Constitutional facts crucial
        "analytical_min": 60,   # High analytical need for governance
        "composite_min": 130
    },
    UPSCCategory.ECONOMY_DEVELOPMENT: {
        "factual_min": 65,      # Economic data important
        "analytical_min": 70,   # High analytical requirement
        "composite_min": 135
    },
    UPSCCategory.ENVIRONMENT_ECOLOGY: {
        "factual_min": 55,      # Moderate factual need
        "analytical_min": 65,   # Environmental impact analysis
        "composite_min": 120
    },
    UPSCCategory.HISTORY_CULTURE: {
        "factual_min": 75,      # Historical facts essential
        "analytical_min": 50,   # Moderate analytical need
        "composite_min": 125
    },
    UPSCCategory.SCIENCE_TECHNOLOGY: {
        "factual_min": 70,      # Technical facts important
        "analytical_min": 55,   # Moderate analytical depth
        "composite_min": 125
    }
}

# Validation Functions
def validate_daily_targets() -> bool:
    """Validate that daily category targets are realistic and balanced"""
    total_min = sum(config["min"] for config in DAILY_CATEGORY_TARGETS.values())
    total_max = sum(config["max"] for config in DAILY_CATEGORY_TARGETS.values())
    total_weight = sum(config["weight"] for config in DAILY_CATEGORY_TARGETS.values())
    
    # Check if targets are reasonable (20-30 articles total)
    if not (20 <= total_min <= 25):
        return False
    if not (25 <= total_max <= 35):
        return False
    if not (0.95 <= total_weight <= 1.05):  # Allow small rounding errors
        return False
        
    return True

def get_category_target(category: UPSCCategory) -> Dict[str, Any]:
    """Get daily target configuration for a specific category"""
    return DAILY_CATEGORY_TARGETS.get(category, {
        "min": 2, "max": 3, "weight": 0.1, "description": "Unknown category"
    })

def get_quality_thresholds(category: UPSCCategory) -> Dict[str, int]:
    """Get quality thresholds for a specific category"""
    return CATEGORY_QUALITY_THRESHOLDS.get(category, {
        "factual_min": 50, "analytical_min": 50, "composite_min": 100
    })

# Export constants for easy importing
__all__ = [
    "UPSCCategory",
    "DAILY_CATEGORY_TARGETS", 
    "CATEGORY_QUALITY_THRESHOLDS",
    "validate_daily_targets",
    "get_category_target",
    "get_quality_thresholds"
]

# Validate configuration on import
if not validate_daily_targets():
    raise ValueError("Invalid daily category targets configuration")