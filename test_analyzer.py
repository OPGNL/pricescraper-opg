#!/usr/bin/env python3
"""
Test script for the Configuration Analyzer
Run this to verify the analyzer is working correctly
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.config_analyzer import ConfigAnalyzer
from app.utils.selector_optimizer import SelectorOptimizer
from app.utils.pattern_matcher import PatternMatcher, ElementType

async def test_config_analyzer():
    """Test the configuration analyzer with a sample website"""
    print("🔍 Testing Configuration Analyzer...")
    print("=" * 50)

    # Test URL (using the German website from your error)
    test_url = "https://expresszuschnitt.de/waschkueche-schrank-tuer-regalboden"
    print(f"📊 Analyzing: {test_url}")
    print()

    try:
        # Initialize analyzer
        analyzer = ConfigAnalyzer()

        # Run analysis
        print("⏳ Running analysis (this may take 30-60 seconds)...")
        results = await analyzer.analyze_website(test_url)

        # Display results
        print("✅ Analysis completed!")
        print(f"🌐 Domain: {results['domain']}")
        print(f"📝 Form fields found: {len(results['form_fields'])}")
        print(f"🖱️  Interactive elements: {len(results['interactive_elements'])}")
        print(f"💰 Price elements: {len(results['price_elements'])}")
        print(f"⚙️  Suggested steps: {len(results['suggested_config'])}")
        print()

        # Show form fields
        if results['form_fields']:
            print("📋 Form Fields Detected:")
            for i, field in enumerate(results['form_fields'][:5], 1):  # Show first 5
                print(f"  {i}. {field.purpose} - {field.selector} (confidence: {field.confidence:.1%})")

        print()

        # Show suggested configuration
        if results['suggested_config']:
            print("🔧 Suggested Configuration Steps:")
            for i, step in enumerate(results['suggested_config'], 1):
                confidence = step.get('confidence', 0)
                print(f"  {i}. {step['type'].upper()}: {step.get('description', 'No description')}")
                print(f"     Selector: {step.get('selector', 'N/A')}")
                print(f"     Confidence: {confidence:.1%}")
                print()

        # Generate summary report
        print("📊 SUMMARY REPORT:")
        print("=" * 30)
        summary = analyzer.generate_summary_report(results)
        print(summary)

        return True

    except Exception as e:
        print(f"❌ Error during analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_pattern_matcher():
    """Test the pattern matcher with sample data"""
    print("\n🧠 Testing Pattern Matcher...")
    print("=" * 50)

    matcher = PatternMatcher()

    # Test cases
    test_cases = [
        {
            'text': 'Material thickness (mm)',
            'attributes': {'id': 'thickness_field', 'name': 'thickness'},
            'expected': ElementType.THICKNESS
        },
        {
            'text': 'Length in centimeters',
            'attributes': {'id': 'length_input', 'class': 'dimension-field'},
            'expected': ElementType.LENGTH
        },
        {
            'text': 'Price: €25.99',
            'attributes': {'class': 'price-display total-amount'},
            'expected': ElementType.PRICE
        },
        {
            'text': 'Add to cart',
            'attributes': {'class': 'btn btn-primary add-cart'},
            'expected': ElementType.ADD_TO_CART
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        result = matcher.analyze_element(
            test_case['text'],
            test_case['attributes']
        )

        status = "✅" if result.element_type == test_case['expected'] else "❌"
        print(f"  {i}. {status} '{test_case['text']}' -> {result.element_type.value} (confidence: {result.confidence:.1%})")

        if result.matched_patterns:
            print(f"     Matched patterns: {', '.join(result.matched_patterns[:2])}")

def test_selector_optimizer():
    """Test the selector optimizer"""
    print("\n🎯 Testing Selector Optimizer...")
    print("=" * 50)

    optimizer = SelectorOptimizer()

    # Test element data
    test_element = {
        'id': 'thickness_selector',
        'className': 'form-control thickness-field custom-select',
        'name': 'thickness',
        'attributes': {
            'id': 'thickness_selector',
            'className': 'form-control thickness-field custom-select',
            'name': 'thickness'
        }
    }

    # Generate strategies
    strategies = optimizer.generate_selector_strategies(test_element)

    print(f"📝 Generated {len(strategies)} selector strategies:")
    for i, strategy in enumerate(strategies, 1):
        print(f"  {i}. {strategy.selector}")
        print(f"     Confidence: {strategy.confidence:.1%}, Maintainability: {strategy.maintainability:.1%}")
        print(f"     Description: {strategy.description}")
        print()

    # Test selector validation
    test_selectors = [
        "#thickness_selector",
        ".form-control.thickness-field",
        "input[name='thickness']",
        "div > div > input.css-1234567.form-control"
    ]

    print("🔍 Selector Validation Results:")
    for selector in test_selectors:
        validation = optimizer.validate_selector(selector)
        status = "✅" if validation['valid'] else "⚠️"
        print(f"  {status} {selector} (Score: {validation['score']}/100)")
        if validation['warnings']:
            print(f"     Warnings: {', '.join(validation['warnings'][:2])}")

async def main():
    """Run all tests"""
    print("🧪 Configuration Analyzer Test Suite")
    print("=" * 60)
    print()

    # Test pattern matcher (fast)
    test_pattern_matcher()

    # Test selector optimizer (fast)
    test_selector_optimizer()

    # Ask if user wants to run the full website analysis (slow)
    print("\n" + "=" * 60)
    response = input("🌐 Run full website analysis test? This takes 30-60 seconds (y/N): ")

    if response.lower().startswith('y'):
        success = await test_config_analyzer()
        if success:
            print("\n🎉 All tests completed successfully!")
        else:
            print("\n❌ Some tests failed. Check the output above.")
    else:
        print("\n⏭️  Skipping website analysis test.")
        print("🎉 Basic tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
