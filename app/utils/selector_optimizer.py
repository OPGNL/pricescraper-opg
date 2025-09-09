"""
Selector Optimization Utilities
Helps generate robust and maintainable CSS selectors
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

@dataclass
class SelectorStrategy:
    selector: str
    confidence: float
    specificity: int
    maintainability: float
    description: str

class SelectorOptimizer:
    """Optimizes CSS selectors for reliability and maintainability"""

    # Generic class names to avoid in selectors
    GENERIC_CLASSES = {
        'btn', 'button', 'form-control', 'input', 'field', 'control',
        'container', 'wrapper', 'content', 'main', 'section', 'div',
        'row', 'col', 'column', 'grid', 'flex', 'block', 'inline',
        'text', 'label', 'title', 'heading', 'paragraph', 'span',
        'active', 'selected', 'focus', 'hover', 'disabled', 'hidden',
        'visible', 'show', 'hide', 'open', 'close', 'collapsed',
        'primary', 'secondary', 'success', 'warning', 'error', 'info',
        'large', 'medium', 'small', 'xs', 'sm', 'md', 'lg', 'xl'
    }

    # Framework-specific patterns that change frequently
    UNSTABLE_PATTERNS = [
        r'css-\w+',  # CSS-in-JS generated classes
        r'sc-\w+',   # Styled-components
        r'jsx-\d+',  # Next.js JSX classes
        r'[a-z]+-\d{6,}',  # Build-time generated hashes
        r'_\w{5,}',  # Webpack/bundler generated classes
        r'\w+__\w+--\w+',  # BEM with modifiers (too specific)
    ]

    def __init__(self):
        self.strategies = []

    def generate_selector_strategies(self, element_data: Dict) -> List[SelectorStrategy]:
        """Generate multiple selector strategies for an element"""
        strategies = []

        # Strategy 1: ID-based (highest confidence if present)
        if element_data.get('id'):
            strategies.append(self._create_id_strategy(element_data))

        # Strategy 2: Class-based strategies
        if element_data.get('className'):
            strategies.extend(self._create_class_strategies(element_data))

        # Strategy 3: Attribute-based strategies
        strategies.extend(self._create_attribute_strategies(element_data))

        # Strategy 4: Content-based strategies
        if element_data.get('text'):
            strategies.extend(self._create_content_strategies(element_data))

        # Strategy 5: Structural strategies
        strategies.extend(self._create_structural_strategies(element_data))

        # Sort by overall score (confidence + maintainability - specificity penalty)
        strategies.sort(key=lambda s: s.confidence + s.maintainability - (s.specificity * 0.1), reverse=True)

        return strategies[:5]  # Return top 5 strategies

    def _create_id_strategy(self, element_data: Dict) -> SelectorStrategy:
        """Create ID-based selector strategy"""
        element_id = element_data['id']

        # Check if ID looks stable
        confidence = 0.9
        if any(re.search(pattern, element_id) for pattern in self.UNSTABLE_PATTERNS):
            confidence = 0.6

        return SelectorStrategy(
            selector=f"#{element_id}",
            confidence=confidence,
            specificity=100,  # ID selectors have high specificity
            maintainability=0.8 if confidence > 0.8 else 0.5,
            description=f"ID selector for element with id '{element_id}'"
        )

    def _create_class_strategies(self, element_data: Dict) -> List[SelectorStrategy]:
        """Create class-based selector strategies"""
        strategies = []
        classes = element_data['className'].split()

        # Filter out generic and unstable classes
        stable_classes = []
        for cls in classes:
            if cls.lower() not in self.GENERIC_CLASSES:
                if not any(re.search(pattern, cls) for pattern in self.UNSTABLE_PATTERNS):
                    stable_classes.append(cls)

        if not stable_classes:
            return strategies

        # Single class strategy
        for cls in stable_classes[:3]:  # Top 3 classes
            confidence = self._calculate_class_confidence(cls, element_data)
            strategies.append(SelectorStrategy(
                selector=f".{cls}",
                confidence=confidence,
                specificity=10,
                maintainability=0.7,
                description=f"Single class selector for '{cls}'"
            ))

        # Multiple class strategy (more specific)
        if len(stable_classes) >= 2:
            combined_selector = f".{'.'.join(stable_classes[:2])}"
            strategies.append(SelectorStrategy(
                selector=combined_selector,
                confidence=0.8,
                specificity=20,
                maintainability=0.6,
                description=f"Combined class selector using {stable_classes[:2]}"
            ))

        return strategies

    def _create_attribute_strategies(self, element_data: Dict) -> List[SelectorStrategy]:
        """Create attribute-based selector strategies"""
        strategies = []

        # Name attribute
        if element_data.get('name'):
            name = element_data['name']
            strategies.append(SelectorStrategy(
                selector=f"[name='{name}']",
                confidence=0.8,
                specificity=10,
                maintainability=0.8,
                description=f"Name attribute selector for '{name}'"
            ))

        # Type attribute for inputs
        if element_data.get('input_type') and element_data.get('input_type') != 'text':
            input_type = element_data['input_type']
            strategies.append(SelectorStrategy(
                selector=f"input[type='{input_type}']",
                confidence=0.6,
                specificity=11,
                maintainability=0.7,
                description=f"Input type selector for '{input_type}'"
            ))

        # Role attribute
        if element_data.get('attributes', {}).get('role'):
            role = element_data['attributes']['role']
            strategies.append(SelectorStrategy(
                selector=f"[role='{role}']",
                confidence=0.7,
                specificity=10,
                maintainability=0.8,
                description=f"Role attribute selector for '{role}'"
            ))

        return strategies

    def _create_content_strategies(self, element_data: Dict) -> List[SelectorStrategy]:
        """Create content-based selector strategies"""
        strategies = []
        text = element_data['text'].strip()

        if len(text) > 0 and len(text) <= 50:  # Reasonable text length
            # Exact text match
            escaped_text = text.replace("'", "\\'")
            strategies.append(SelectorStrategy(
                selector=f":contains('{escaped_text}')",
                confidence=0.7,
                specificity=1,
                maintainability=0.4,  # Text can change
                description=f"Text content selector for '{text[:20]}...'"
            ))

            # Partial text match for longer texts
            if len(text) > 15:
                partial_text = text[:15].replace("'", "\\'")
                strategies.append(SelectorStrategy(
                    selector=f":contains('{partial_text}')",
                    confidence=0.5,
                    specificity=1,
                    maintainability=0.3,
                    description=f"Partial text content selector for '{partial_text}...'"
                ))

        return strategies

    def _create_structural_strategies(self, element_data: Dict) -> List[SelectorStrategy]:
        """Create structural selector strategies"""
        strategies = []
        element_type = element_data.get('element_type', 'div')

        # Tag name only (very generic)
        strategies.append(SelectorStrategy(
            selector=element_type,
            confidence=0.3,
            specificity=1,
            maintainability=0.9,
            description=f"Generic tag selector for '{element_type}'"
        ))

        # Tag + attribute combinations
        if element_data.get('name'):
            strategies.append(SelectorStrategy(
                selector=f"{element_type}[name='{element_data['name']}']",
                confidence=0.8,
                specificity=11,
                maintainability=0.8,
                description=f"Tag and name combination for '{element_type}'"
            ))

        return strategies

    def _calculate_class_confidence(self, class_name: str, element_data: Dict) -> float:
        """Calculate confidence score for a class name"""
        confidence = 0.7  # Base confidence

        # Boost for semantic class names
        semantic_keywords = [
            'price', 'cost', 'total', 'amount', 'thickness', 'width', 'length',
            'quantity', 'button', 'submit', 'calculate', 'add', 'cart',
            'product', 'form', 'field', 'input', 'select'
        ]

        if any(keyword in class_name.lower() for keyword in semantic_keywords):
            confidence += 0.2

        # Reduce for very short or very long class names
        if len(class_name) < 3:
            confidence -= 0.2
        elif len(class_name) > 20:
            confidence -= 0.1

        # Reduce for numbered classes (might be dynamic)
        if re.search(r'\d{3,}', class_name):
            confidence -= 0.3

        return max(0.1, min(1.0, confidence))

    def optimize_selector_for_purpose(self, strategies: List[SelectorStrategy], purpose: str) -> SelectorStrategy:
        """Select the best strategy for a specific purpose"""
        purpose_weights = {
            'thickness': {'specificity': 0.7, 'maintainability': 0.8},
            'dimensions': {'specificity': 0.6, 'maintainability': 0.9},
            'price': {'specificity': 0.5, 'maintainability': 0.7},
            'add_to_cart': {'specificity': 0.8, 'maintainability': 0.6},
            'cookies': {'specificity': 0.9, 'maintainability': 0.5}
        }

        weights = purpose_weights.get(purpose, {'specificity': 0.6, 'maintainability': 0.7})

        # Calculate weighted scores
        scored_strategies = []
        for strategy in strategies:
            score = (
                strategy.confidence * 0.4 +
                strategy.maintainability * weights['maintainability'] * 0.4 +
                (1 - strategy.specificity / 100) * weights['specificity'] * 0.2
            )
            scored_strategies.append((score, strategy))

        # Return the highest scoring strategy
        scored_strategies.sort(key=lambda x: x[0], reverse=True)
        return scored_strategies[0][1] if scored_strategies else strategies[0]

    def validate_selector(self, selector: str) -> Dict[str, any]:
        """Validate a CSS selector for common issues"""
        issues = []
        warnings = []
        score = 100

        # Check for overly specific selectors
        specificity = self._calculate_specificity(selector)
        if specificity > 200:
            issues.append("Selector is overly specific and may be brittle")
            score -= 20

        # Check for unstable patterns
        for pattern in self.UNSTABLE_PATTERNS:
            if re.search(pattern, selector):
                warnings.append(f"Selector contains potentially unstable pattern: {pattern}")
                score -= 10

        # Check for generic classes
        for generic in self.GENERIC_CLASSES:
            if f".{generic}" in selector or f" {generic}" in selector:
                warnings.append(f"Selector uses generic class: {generic}")
                score -= 5

        # Check for complex combinations
        if selector.count(' ') > 3:
            warnings.append("Selector is quite complex, consider simplifying")
            score -= 10

        return {
            'valid': len(issues) == 0,
            'score': max(0, score),
            'issues': issues,
            'warnings': warnings,
            'specificity': specificity
        }

    def _calculate_specificity(self, selector: str) -> int:
        """Calculate CSS specificity score"""
        # Simplified specificity calculation
        ids = len(re.findall(r'#\w+', selector))
        classes = len(re.findall(r'\.\w+', selector))
        attributes = len(re.findall(r'\[\w+', selector))
        elements = len(re.findall(r'\b[a-z]+\b', selector))

        return ids * 100 + (classes + attributes) * 10 + elements

    def suggest_improvements(self, selector: str) -> List[str]:
        """Suggest improvements for a selector"""
        suggestions = []
        validation = self.validate_selector(selector)

        if validation['specificity'] > 100:
            suggestions.append("Consider using a less specific selector")

        if ' ' in selector and '>' not in selector:
            suggestions.append("Consider using direct child selector (>) instead of descendant")

        if selector.count('.') > 2:
            suggestions.append("Consider reducing the number of class selectors")

        # Check for opportunities to use semantic attributes
        if '[name=' not in selector and '[id=' not in selector:
            suggestions.append("Consider using name or id attributes if available")

        return suggestions
