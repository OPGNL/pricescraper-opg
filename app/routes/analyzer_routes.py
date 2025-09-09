"""
Configuration Analyzer API Routes
Provides endpoints for analyzing websites and generating configurations
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, HttpUrl
from typing import Dict, List, Optional, Any
import asyncio
import logging
from datetime import datetime

from app.services.config_analyzer import ConfigAnalyzer
from app.utils.selector_optimizer import SelectorOptimizer
from app.utils.pattern_matcher import PatternMatcher, ElementType
from app.database.database import SessionLocal
from app.models.models import DomainConfig

router = APIRouter(prefix="/api/analyzer", tags=["Configuration Analyzer"])
logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses
class AnalyzeRequest(BaseModel):
    url: HttpUrl
    deep_analysis: bool = True
    include_suggestions: bool = True

class AnalyzeResponse(BaseModel):
    success: bool
    domain: str
    analysis_id: str
    timestamp: str
    page_info: Dict[str, Any]
    form_fields: List[Dict[str, Any]]
    interactive_elements: List[Dict[str, Any]]
    price_elements: List[Dict[str, Any]]
    suggested_config: List[Dict[str, Any]]
    confidence_score: float
    warnings: List[str]
    industry_detected: List[str]

class ConfigGenerateRequest(BaseModel):
    analysis_id: str
    selected_elements: List[Dict[str, Any]]
    domain_name: Optional[str] = None
    category: str = "square_meter_price"

class ValidateSelectorRequest(BaseModel):
    selector: str
    purpose: Optional[str] = None

class OptimizeSelectorRequest(BaseModel):
    element_data: Dict[str, Any]
    purpose: str

# In-memory storage for analysis results (in production, use Redis or database)
analysis_cache = {}

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_website(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    """
    Analyze a website and suggest scraping configuration
    """
    try:
        logger.info(f"Starting analysis of website: {request.url}")

        # Initialize the analyzer
        analyzer = ConfigAnalyzer()

        # Perform the analysis
        results = await analyzer.analyze_website(str(request.url))

        # Generate analysis ID
        analysis_id = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(str(request.url)) % 10000}"

        # Cache the results
        analysis_cache[analysis_id] = results

        # Calculate overall confidence score
        confidence_score = calculate_overall_confidence(results)

        # Detect warnings
        warnings = generate_warnings(results)

        # Detect industry
        page_content = results.get('page_info', {}).get('title', '') + ' ' + str(results.get('form_fields', []))
        pattern_matcher = PatternMatcher()
        industry_detected = pattern_matcher.detect_industry(page_content)

        return AnalyzeResponse(
            success=True,
            domain=results['domain'],
            analysis_id=analysis_id,
            timestamp=results['timestamp'],
            page_info=results['page_info'],
            form_fields=[field.__dict__ for field in results['form_fields']],
            interactive_elements=[elem.__dict__ for elem in results['interactive_elements']],
            price_elements=[elem.__dict__ for elem in results['price_elements']],
            suggested_config=results['suggested_config'],
            confidence_score=confidence_score,
            warnings=warnings,
            industry_detected=industry_detected
        )

    except Exception as e:
        logger.error(f"Error analyzing website {request.url}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.get("/analysis/{analysis_id}")
async def get_analysis_results(analysis_id: str):
    """
    Get cached analysis results by ID
    """
    if analysis_id not in analysis_cache:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return JSONResponse(content=analysis_cache[analysis_id])

@router.post("/generate-config")
async def generate_configuration(request: ConfigGenerateRequest):
    """
    Generate a final configuration based on selected elements
    """
    try:
        if request.analysis_id not in analysis_cache:
            raise HTTPException(status_code=404, detail="Analysis not found")

        analysis_results = analysis_cache[request.analysis_id]
        domain = analysis_results['domain']

        # Generate final configuration steps
        config_steps = []

        # Sort elements by logical order (popups first, then form fields, then actions)
        sorted_elements = sort_elements_by_logic(request.selected_elements)

        for element in sorted_elements:
            step = convert_element_to_step(element, analysis_results)
            if step:
                config_steps.append(step)

        # Create the final configuration object
        final_config = {
            "domain": domain,
            "category": request.category,
            "steps": config_steps,
            "units": detect_units(analysis_results),
            "generated_at": datetime.now().isoformat(),
            "confidence": calculate_config_confidence(config_steps),
            "version": 1
        }

        # Optionally save to database
        if request.domain_name:
            await save_config_to_database(request.domain_name, final_config)

        return JSONResponse(content={
            "success": True,
            "config": final_config,
            "message": f"Configuration generated for {domain}"
        })

    except Exception as e:
        logger.error(f"Error generating configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Configuration generation failed: {str(e)}")

@router.post("/validate-selector")
async def validate_selector(request: ValidateSelectorRequest):
    """
    Validate a CSS selector for common issues
    """
    try:
        optimizer = SelectorOptimizer()
        validation_result = optimizer.validate_selector(request.selector)
        suggestions = optimizer.suggest_improvements(request.selector)

        return JSONResponse(content={
            "success": True,
            "selector": request.selector,
            "validation": validation_result,
            "suggestions": suggestions
        })

    except Exception as e:
        logger.error(f"Error validating selector: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

@router.post("/optimize-selector")
async def optimize_selector(request: OptimizeSelectorRequest):
    """
    Generate optimized selector strategies for an element
    """
    try:
        optimizer = SelectorOptimizer()
        strategies = optimizer.generate_selector_strategies(request.element_data)

        if request.purpose:
            best_strategy = optimizer.optimize_selector_for_purpose(strategies, request.purpose)
            return JSONResponse(content={
                "success": True,
                "best_strategy": best_strategy.__dict__,
                "all_strategies": [s.__dict__ for s in strategies]
            })

        return JSONResponse(content={
            "success": True,
            "strategies": [s.__dict__ for s in strategies]
        })

    except Exception as e:
        logger.error(f"Error optimizing selector: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")

@router.get("/patterns")
async def get_available_patterns():
    """
    Get available pattern types and their descriptions
    """
    pattern_matcher = PatternMatcher()

    patterns_info = {}
    for element_type in ElementType:
        if element_type != ElementType.UNKNOWN:
            patterns_info[element_type.value] = {
                "name": element_type.value,
                "description": f"Patterns for detecting {element_type.value} elements",
                "primary_patterns": pattern_matcher.patterns.get(element_type, {}).get('primary', []),
                "secondary_patterns": pattern_matcher.patterns.get(element_type, {}).get('secondary', [])
            }

    return JSONResponse(content={
        "success": True,
        "patterns": patterns_info
    })

@router.get("/analysis-history")
async def get_analysis_history():
    """
    Get list of recent analyses
    """
    history = []
    for analysis_id, results in analysis_cache.items():
        history.append({
            "analysis_id": analysis_id,
            "domain": results.get('domain', 'Unknown'),
            "timestamp": results.get('timestamp', ''),
            "url": results.get('url', ''),
            "step_count": len(results.get('suggested_config', []))
        })

    # Sort by timestamp (most recent first)
    history.sort(key=lambda x: x['timestamp'], reverse=True)

    return JSONResponse(content={
        "success": True,
        "history": history[:20]  # Return last 20 analyses
    })

@router.delete("/analysis/{analysis_id}")
async def delete_analysis(analysis_id: str):
    """
    Delete cached analysis results
    """
    if analysis_id not in analysis_cache:
        raise HTTPException(status_code=404, detail="Analysis not found")

    del analysis_cache[analysis_id]

    return JSONResponse(content={
        "success": True,
        "message": f"Analysis {analysis_id} deleted"
    })

@router.get("/config-preview/{analysis_id}")
async def preview_configuration(analysis_id: str):
    """
    Generate a preview of the configuration without saving
    """
    if analysis_id not in analysis_cache:
        raise HTTPException(status_code=404, detail="Analysis not found")

    analysis_results = analysis_cache[analysis_id]
    suggested_config = analysis_results.get('suggested_config', [])

    # Generate preview with explanations
    preview = {
        "domain": analysis_results['domain'],
        "total_steps": len(suggested_config),
        "steps_breakdown": {},
        "estimated_execution_time": estimate_execution_time(suggested_config),
        "complexity_score": calculate_complexity_score(suggested_config),
        "steps": []
    }

    # Count step types
    for step in suggested_config:
        step_type = step.get('type', 'unknown')
        preview['steps_breakdown'][step_type] = preview['steps_breakdown'].get(step_type, 0) + 1

    # Add detailed step information
    for i, step in enumerate(suggested_config, 1):
        preview['steps'].append({
            "step_number": i,
            "type": step.get('type', 'unknown'),
            "description": step.get('description', 'No description'),
            "selector": step.get('selector', ''),
            "confidence": step.get('confidence', 0.0),
            "estimated_time": estimate_step_time(step)
        })

    return JSONResponse(content={
        "success": True,
        "preview": preview
    })

# Helper functions

def calculate_overall_confidence(results: Dict) -> float:
    """Calculate overall confidence score for the analysis"""
    scores = []

    # Form fields confidence
    form_fields = results.get('form_fields', [])
    if form_fields:
        form_confidence = sum(field.confidence for field in form_fields) / len(form_fields)
        scores.append(form_confidence)

    # Interactive elements confidence
    interactive_elements = results.get('interactive_elements', [])
    if interactive_elements:
        interactive_confidence = sum(elem.confidence for elem in interactive_elements) / len(interactive_elements)
        scores.append(interactive_confidence)

    # Price elements confidence
    price_elements = results.get('price_elements', [])
    if price_elements:
        price_confidence = sum(elem.confidence for elem in price_elements) / len(price_elements)
        scores.append(price_confidence)

    return sum(scores) / len(scores) if scores else 0.5

def generate_warnings(results: Dict) -> List[str]:
    """Generate warnings based on analysis results"""
    warnings = []

    # Check for missing critical elements
    form_fields = results.get('form_fields', [])
    thickness_fields = [f for f in form_fields if f.purpose == 'thickness']
    price_elements = results.get('price_elements', [])

    if not thickness_fields:
        warnings.append("No thickness input fields detected")

    if not price_elements:
        warnings.append("No price display elements detected")

    # Check for low confidence elements
    low_confidence_count = 0
    all_elements = form_fields + results.get('interactive_elements', []) + price_elements

    for element in all_elements:
        if hasattr(element, 'confidence') and element.confidence < 0.6:
            low_confidence_count += 1

    if low_confidence_count > len(all_elements) * 0.3:  # More than 30% low confidence
        warnings.append("Many elements have low confidence scores")

    return warnings

def sort_elements_by_logic(elements: List[Dict]) -> List[Dict]:
    """Sort elements in logical execution order"""
    def get_priority(element):
        element_type = element.get('purpose', element.get('element_type', ''))
        priorities = {
            'cookies': 1,
            'popup': 2,
            'thickness': 3,
            'dimensions': 4,
            'length': 4,
            'width': 4,
            'quantity': 5,
            'add_to_cart': 6,
            'navigation': 7,
            'price': 8
        }
        return priorities.get(element_type, 5)

    return sorted(elements, key=get_priority)

def convert_element_to_step(element: Dict, analysis_results: Dict) -> Optional[Dict]:
    """Convert an analyzed element to a configuration step"""
    element_type = element.get('purpose', element.get('element_type', ''))
    selector = element.get('selector', '')

    if not selector:
        return None

    step_templates = {
        'cookies': {
            "type": "click",
            "description": "Accept cookies"
        },
        'thickness': {
            "type": "select",
            "value": "{thickness}",
            "unit": "mm",
            "description": "Set material thickness"
        },
        'length': {
            "type": "input",
            "value": "{length}",
            "unit": "mm",
            "description": "Set length dimension"
        },
        'width': {
            "type": "input",
            "value": "{width}",
            "unit": "mm",
            "description": "Set width dimension"
        },
        'quantity': {
            "type": "input",
            "value": "{quantity}",
            "description": "Set quantity"
        },
        'add_to_cart': {
            "type": "click",
            "description": "Add to cart or calculate price"
        },
        'price': {
            "type": "read_price",
            "description": "Extract calculated price"
        }
    }

    template = step_templates.get(element_type, {
        "type": "click",
        "description": f"Interact with {element_type} element"
    })

    step = {
        "selector": selector,
        **template,
        "confidence": element.get('confidence', 0.5)
    }

    return step

def detect_units(analysis_results: Dict) -> Dict[str, str]:
    """Detect preferred units based on website analysis"""
    # Default units
    units = {
        "thickness": "mm",
        "dimensions": "mm"
    }

    # Analyze form fields for unit hints
    form_fields = analysis_results.get('form_fields', [])
    for field in form_fields:
        field_text = f"{field.label} {field.placeholder}".lower()

        if 'cm' in field_text and field.purpose in ['thickness', 'dimensions']:
            units[field.purpose] = "cm"
        elif 'inch' in field_text or '"' in field_text:
            units[field.purpose] = "inch"

    return units

def calculate_config_confidence(steps: List[Dict]) -> float:
    """Calculate overall confidence for the generated configuration"""
    if not steps:
        return 0.0

    confidence_scores = [step.get('confidence', 0.5) for step in steps]
    return sum(confidence_scores) / len(confidence_scores)

def estimate_execution_time(steps: List[Dict]) -> int:
    """Estimate execution time in seconds"""
    time_per_step = {
        'click': 2,
        'input': 3,
        'select': 3,
        'wait': 1,
        'read_price': 2,
        'navigate': 3
    }

    total_time = 0
    for step in steps:
        step_type = step.get('type', 'click')
        total_time += time_per_step.get(step_type, 2)

    return total_time

def estimate_step_time(step: Dict) -> int:
    """Estimate execution time for a single step"""
    time_per_step = {
        'click': 2,
        'input': 3,
        'select': 3,
        'wait': 1,
        'read_price': 2,
        'navigate': 3
    }

    step_type = step.get('type', 'click')
    return time_per_step.get(step_type, 2)

def calculate_complexity_score(steps: List[Dict]) -> float:
    """Calculate complexity score (0-1, where 1 is most complex)"""
    if not steps:
        return 0.0

    complexity_weights = {
        'click': 0.1,
        'input': 0.3,
        'select': 0.4,
        'wait': 0.1,
        'read_price': 0.2,
        'navigate': 0.3
    }

    total_complexity = 0
    for step in steps:
        step_type = step.get('type', 'click')
        total_complexity += complexity_weights.get(step_type, 0.2)

    # Normalize by number of steps
    return min(total_complexity / len(steps), 1.0)

async def save_config_to_database(domain_name: str, config: Dict):
    """Save generated configuration to database"""
    db = SessionLocal()
    try:
        # Create new domain config
        db_config = DomainConfig(
            domain=domain_name,
            config=config,
            category=config.get('category', 'square_meter_price'),
            version=1,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        db.add(db_config)
        db.commit()

        logger.info(f"Saved configuration for domain: {domain_name}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving configuration to database: {str(e)}")
        raise
    finally:
        db.close()
