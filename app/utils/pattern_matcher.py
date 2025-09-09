"""
Pattern Matching Utilities
Advanced pattern matching for web scraping configuration
"""

import re
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from enum import Enum

class ElementType(Enum):
    THICKNESS = "thickness"
    LENGTH = "length"
    WIDTH = "width"
    QUANTITY = "quantity"
    PRICE = "price"
    ADD_TO_CART = "add_to_cart"
    COOKIES = "cookies"
    NAVIGATION = "navigation"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    UNKNOWN = "unknown"

@dataclass
class PatternMatch:
    element_type: ElementType
    confidence: float
    matched_patterns: List[str]
    context_clues: List[str]

class PatternMatcher:
    """Advanced pattern matching for identifying web elements"""

    def __init__(self):
        # Multi-language patterns for better international support
        self.patterns = {
            ElementType.THICKNESS: {
                'primary': [
                    r'\b(thick|thickness|dicke|épaisseur|spessore|grosor|tjocklek)\b',
                    r'\b(material\s*thickness|thickness\s*material)\b',
                    r'\b\d+\s*mm\s*(thick|dick|épais|spesso|grueso)\b',
                    r'\b(stärke|starke)\b'  # German
                ],
                'secondary': [
                    r'\b(depth|profundidad|profondeur|profondità|djup)\b',
                    r'\b(height|höhe|hauteur|altezza|altura|höjd)\b',
                    r'\bmm\b.*\b(panel|plate|sheet|platte|plaque|panneau)\b'
                ],
                'context': [
                    r'\b(plexiglas|acrylic|plastic|kunststoff|plastique|plástico)\b',
                    r'\b(sheet|panel|plate|platte|panneau|hoja)\b'
                ]
            },

            ElementType.LENGTH: {
                'primary': [
                    r'\b(length|länge|longueur|lunghezza|largo|längd)\b',
                    r'\b(long|lang|longo)\b.*\b(side|seite|côté|lato|lado)\b'
                ],
                'secondary': [
                    r'\b(x\s*axis|x-axis|horizontal)\b',
                    r'\b(width|breite|largeur|larghezza|ancho|bredd)\b.*\b(1|first|premier|primo|primero)\b'
                ],
                'context': [
                    r'\b(dimension|abmessung|dimension|dimensione|dimensión)\b',
                    r'\b(size|größe|taille|misura|tamaño|storlek)\b'
                ]
            },

            ElementType.WIDTH: {
                'primary': [
                    r'\b(width|breite|largeur|larghezza|ancho|bredd)\b',
                    r'\b(wide|breit|large|ancho|bred)\b'
                ],
                'secondary': [
                    r'\b(y\s*axis|y-axis|vertical)\b',
                    r'\b(short|kurz|court|corto)\b.*\b(side|seite|côté|lato|lado)\b'
                ],
                'context': [
                    r'\b(dimension|abmessung|dimension|dimensione|dimensión)\b',
                    r'\b(cross|quer|transverse|transversal)\b'
                ]
            },

            ElementType.QUANTITY: {
                'primary': [
                    r'\b(quantity|amount|aantal|anzahl|quantité|cantidad|antal)\b',
                    r'\b(pieces|stück|pièces|pezzi|piezas|stycken)\b',
                    r'\b(qty|menge|qté|cant)\b',
                    r'\b(units|einheiten|unités|unità|unidades|enheter)\b'
                ],
                'secondary': [
                    r'\b(count|zählen|compter|contare|contar|räkna)\b',
                    r'\b(number|nummer|numéro|numero|número)\b.*\b(of|von|de|di|av)\b'
                ],
                'context': [
                    r'\b(order|bestell|commander|ordinare|pedir|beställa)\b',
                    r'\b(buy|kauf|achat|comprare|comprar|köpa)\b'
                ]
            },

            ElementType.PRICE: {
                'primary': [
                    r'\b(price|preis|prix|prezzo|precio|pris)\b',
                    r'\b(cost|kosten|coût|costo|costo|kostnad)\b',
                    r'\b(total|gesamt|total|totale|total)\b',
                    r'(€|\$|£|CHF|SEK|NOK|DKK|PLN|CZK|HUF)',
                    r'\b\d+[.,]\d+\s*(€|\$|£|CHF|SEK|NOK|DKK|PLN|CZK|HUF)\b'
                ],
                'secondary': [
                    r'\b(amount|betrag|montant|importo|importe|belopp)\b',
                    r'\b(sum|summe|somme|somma|suma)\b',
                    r'\b(final|endlich|final|finale|final|slutlig)\b'
                ],
                'context': [
                    r'\b(calculate|berechnen|calculer|calcolare|calcular|beräkna)\b',
                    r'\b(estimate|schätzen|estimer|stimare|estimar|uppskatta)\b'
                ]
            },

            ElementType.ADD_TO_CART: {
                'primary': [
                    r'\b(add.*cart|in.*warenkorb|ajouter.*panier|aggiungi.*carrello|añadir.*carrito)\b',
                    r'\b(buy|kaufen|acheter|comprare|comprar|köpa)\b',
                    r'\b(order|bestellen|commander|ordinare|pedir|beställa)\b',
                    r'\b(purchase|erwerben|acheter|acquistare|adquirir|köpa)\b'
                ],
                'secondary': [
                    r'\b(cart|warenkorb|panier|carrello|carrito|kundvagn)\b',
                    r'\b(basket|korb|panier|cestino|cesta|korg)\b',
                    r'\b(checkout|kasse|caisse|cassa|caja|kassa)\b'
                ],
                'context': [
                    r'\b(shop|laden|magasin|negozio|tienda|butik)\b',
                    r'\b(store|geschäft|magasin|negozio|tienda|affär)\b'
                ]
            },

            ElementType.COOKIES: {
                'primary': [
                    r'\b(accept.*cookie|cookie.*accept|cookies.*akzeptieren)\b',
                    r'\b(allow.*cookie|cookie.*allow|cookies.*zulassen)\b',
                    r'\b(consent|einwilligung|consentement|consenso|consentimiento)\b',
                    r'\b(agree|zustimmen|accepter|accettare|aceptar|hålla med)\b'
                ],
                'secondary': [
                    r'\b(gdpr|dsgvo|rgpd)\b',
                    r'\b(privacy|datenschutz|confidentialité|privacy|privacidad|integritet)\b',
                    r'\b(tracking|verfolgung|suivi|tracciamento|seguimiento|spårning)\b'
                ],
                'context': [
                    r'\b(cookie|keks|biscuit|cookie|galleta|kaka)\b',
                    r'\b(banner|banner|bannière|banner|pancarta|banner)\b'
                ]
            },

            ElementType.EMAIL: {
                'primary': [
                    r'\b(email|e-mail|mail|courrier|correo|mejl)\b',
                    r'\b(address|adresse|dirección|indirizzo|adress)\b.*\b(email|mail)\b',
                    r'@.*\.(com|org|net|de|fr|es|it|se|no|dk)'
                ],
                'secondary': [
                    r'\b(contact|kontakt|contact|contatto|contacto)\b',
                    r'\b(newsletter|rundbrief|lettre|newsletter|boletín)\b'
                ],
                'context': []
            },

            ElementType.PHONE: {
                'primary': [
                    r'\b(phone|telefon|téléphone|telefono|teléfono)\b',
                    r'\b(mobile|handy|portable|cellulare|móvil|mobil)\b',
                    r'\b\+?\d{1,4}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b'
                ],
                'secondary': [
                    r'\b(call|anrufen|appeler|chiamare|llamar|ringa)\b',
                    r'\b(number|nummer|numéro|numero|número)\b'
                ],
                'context': []
            }
        }

        # Industry-specific patterns
        self.industry_patterns = {
            'plastic_manufacturing': [
                r'\b(plexiglas|acrylic|pmma|polycarbonate|pvc|abs)\b',
                r'\b(sheet|panel|plate|rod|tube|profile)\b',
                r'\b(transparent|opaque|colored|clear|matt)\b'
            ],
            'glass_manufacturing': [
                r'\b(glass|glas|verre|vetro|vidrio)\b',
                r'\b(tempered|gehärtet|trempé|temperato|templado)\b',
                r'\b(laminated|laminiert|feuilleté|laminato|laminado)\b'
            ],
            'metal_manufacturing': [
                r'\b(steel|stahl|acier|acciaio|acero)\b',
                r'\b(aluminum|aluminium|aluminio|alluminio)\b',
                r'\b(cutting|schneiden|découpe|taglio|corte)\b'
            ]
        }

    def analyze_element(self, text: str, attributes: Dict[str, str], context: str = "") -> PatternMatch:
        """Analyze an element to determine its likely purpose"""
        # Combine all text for analysis
        combined_text = f"{text} {' '.join(attributes.values())} {context}".lower()

        best_match = PatternMatch(
            element_type=ElementType.UNKNOWN,
            confidence=0.0,
            matched_patterns=[],
            context_clues=[]
        )

        for element_type, pattern_groups in self.patterns.items():
            confidence, matched_patterns, context_clues = self._calculate_match_confidence(
                combined_text, pattern_groups
            )

            if confidence > best_match.confidence:
                best_match = PatternMatch(
                    element_type=element_type,
                    confidence=confidence,
                    matched_patterns=matched_patterns,
                    context_clues=context_clues
                )

        return best_match

    def _calculate_match_confidence(self, text: str, pattern_groups: Dict[str, List[str]]) -> Tuple[float, List[str], List[str]]:
        """Calculate confidence score for pattern matching"""
        confidence = 0.0
        matched_patterns = []
        context_clues = []

        # Primary patterns (high weight)
        for pattern in pattern_groups.get('primary', []):
            if re.search(pattern, text, re.IGNORECASE):
                confidence += 0.4
                matched_patterns.append(pattern)

        # Secondary patterns (medium weight)
        for pattern in pattern_groups.get('secondary', []):
            if re.search(pattern, text, re.IGNORECASE):
                confidence += 0.2
                matched_patterns.append(pattern)

        # Context patterns (low weight but important for disambiguation)
        for pattern in pattern_groups.get('context', []):
            if re.search(pattern, text, re.IGNORECASE):
                confidence += 0.1
                context_clues.append(pattern)

        # Boost confidence if multiple patterns match
        if len(matched_patterns) > 1:
            confidence += 0.1

        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)

        return confidence, matched_patterns, context_clues

    def detect_industry(self, page_content: str) -> List[str]:
        """Detect the industry/domain of the website"""
        industries = []
        content_lower = page_content.lower()

        for industry, patterns in self.industry_patterns.items():
            matches = sum(1 for pattern in patterns if re.search(pattern, content_lower, re.IGNORECASE))
            if matches >= 2:  # Require at least 2 pattern matches
                industries.append(industry)

        return industries

    def find_related_elements(self, target_text: str, all_elements: List[Dict]) -> List[Dict]:
        """Find elements that are likely related to the target element"""
        related = []
        target_words = set(re.findall(r'\w+', target_text.lower()))

        for element in all_elements:
            element_text = f"{element.get('text', '')} {' '.join(element.get('attributes', {}).values())}"
            element_words = set(re.findall(r'\w+', element_text.lower()))

            # Calculate word overlap
            overlap = len(target_words.intersection(element_words))
            if overlap > 0:
                similarity = overlap / len(target_words.union(element_words))
                if similarity > 0.2:  # 20% similarity threshold
                    related.append({
                        'element': element,
                        'similarity': similarity,
                        'shared_words': target_words.intersection(element_words)
                    })

        return sorted(related, key=lambda x: x['similarity'], reverse=True)

    def suggest_element_groups(self, elements: List[Dict]) -> Dict[str, List[Dict]]:
        """Group related elements together"""
        groups = {
            'dimensions': [],
            'product_config': [],
            'pricing': [],
            'actions': [],
            'navigation': [],
            'forms': []
        }

        for element in elements:
            element_analysis = self.analyze_element(
                element.get('text', ''),
                element.get('attributes', {}),
                ''
            )

            element_type = element_analysis.element_type

            if element_type in [ElementType.LENGTH, ElementType.WIDTH, ElementType.THICKNESS]:
                groups['dimensions'].append(element)
            elif element_type == ElementType.QUANTITY:
                groups['product_config'].append(element)
            elif element_type == ElementType.PRICE:
                groups['pricing'].append(element)
            elif element_type == ElementType.ADD_TO_CART:
                groups['actions'].append(element)
            elif element_type == ElementType.NAVIGATION:
                groups['navigation'].append(element)
            elif element_type in [ElementType.EMAIL, ElementType.PHONE]:
                groups['forms'].append(element)

        # Remove empty groups
        return {k: v for k, v in groups.items() if v}

    def validate_element_sequence(self, elements: List[Dict]) -> Dict[str, any]:
        """Validate that elements form a logical sequence for scraping"""
        issues = []
        warnings = []
        score = 100

        element_types = []
        for element in elements:
            analysis = self.analyze_element(
                element.get('text', ''),
                element.get('attributes', {}),
                ''
            )
            element_types.append(analysis.element_type)

        # Check for required elements
        required_types = [ElementType.THICKNESS, ElementType.PRICE]
        missing_required = [t for t in required_types if t not in element_types]

        if missing_required:
            issues.append(f"Missing required elements: {[t.value for t in missing_required]}")
            score -= 30

        # Check for logical order
        dimension_types = [ElementType.THICKNESS, ElementType.LENGTH, ElementType.WIDTH]
        dimension_positions = [i for i, t in enumerate(element_types) if t in dimension_types]
        price_positions = [i for i, t in enumerate(element_types) if t == ElementType.PRICE]

        if price_positions and dimension_positions:
            if min(price_positions) < max(dimension_positions):
                warnings.append("Price element appears before all dimension inputs")
                score -= 10

        # Check for duplicate types
        type_counts = {}
        for t in element_types:
            type_counts[t] = type_counts.get(t, 0) + 1

        duplicates = [t.value for t, count in type_counts.items() if count > 1]
        if duplicates:
            warnings.append(f"Duplicate element types found: {duplicates}")
            score -= 5

        return {
            'valid': len(issues) == 0,
            'score': max(0, score),
            'issues': issues,
            'warnings': warnings,
            'element_types': [t.value for t in element_types]
        }

    def generate_step_description(self, element_type: ElementType, element_data: Dict) -> str:
        """Generate human-readable descriptions for configuration steps"""
        descriptions = {
            ElementType.THICKNESS: "Set material thickness",
            ElementType.LENGTH: "Set length dimension",
            ElementType.WIDTH: "Set width dimension",
            ElementType.QUANTITY: "Set quantity or number of pieces",
            ElementType.PRICE: "Extract calculated price",
            ElementType.ADD_TO_CART: "Add product to cart or calculate price",
            ElementType.COOKIES: "Accept cookie consent",
            ElementType.NAVIGATION: "Navigate to next step",
            ElementType.EMAIL: "Enter email address",
            ElementType.PHONE: "Enter phone number"
        }

        base_description = descriptions.get(element_type, "Interact with element")

        # Add specific details if available
        if element_data.get('text'):
            text = element_data['text'][:30]
            return f"{base_description} ('{text}...')"

        return base_description
