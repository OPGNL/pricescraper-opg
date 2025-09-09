"""
Website Configuration Analyzer
Automatically analyzes websites and suggests scraping configurations
"""

from playwright.async_api import async_playwright, Page
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse, urljoin
import re
import json
import asyncio
from datetime import datetime
import logging
from dataclasses import dataclass

@dataclass
class ElementInfo:
    selector: str
    element_type: str
    text: str
    attributes: Dict[str, str]
    confidence: float
    purpose: str
    position: Dict[str, int]

@dataclass
class FormFieldInfo:
    selector: str
    field_type: str
    name: str
    label: str
    placeholder: str
    required: bool
    options: List[str]
    confidence: float
    purpose: str

class ConfigAnalyzer:
    """Analyzes websites and generates scraping configurations"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Common patterns for different element types
        self.patterns = {
            'thickness': [
                r'\b(thick|thickness|dicke|épaisseur|spessore|grosor|tjocklek)\b',
                r'\b(material\s*thickness|thickness\s*material)\b',
                r'\b\d+\s*mm\s*(thick|dick|épais|spesso|grueso)\b',
                r'\b(stärke|starke)\b',  # German
                r'plattenstärke|materialstärke',
                r'dick|dickness',
                r'fl_thick|thick.*sel|thickness.*sel',  # Common German site patterns
                r'material.*auswahl|auswahl.*material',
                r'tiefe|depth',  # Add depth detection for German sites
                r'data-key="z"',  # Z-axis thickness
                r'mat.*thick|thick.*mat',  # Material thickness variations
                r'Tiefe\s*\(mm\)|Tiefe\s*mm'  # German with unit specification
            ],
            'length': [
                r'\b(length|länge|longueur|lunghezza|largo|längd)\b',
                r'\b(long|lang|longo)\b.*\b(side|seite|côté|lato|lado)\b',
                r'\b(x\s*axis|x-axis|horizontal)\b',
                r'data-key="x"',  # Specific to your site structure
                r'breite',  # German width (often used as length)
                r'Breite\s*\(mm\)|Breite\s*mm',  # German with unit specification
            ],
            'width': [
                r'\b(width|breite|largeur|larghezza|ancho|bredd)\b',
                r'\b(wide|breit|large|ancho|bred)\b',
                r'\b(y\s*axis|y-axis|vertical)\b',
                r'data-key="y"',  # Specific to your site structure
                r'höhe|height',  # German height
                r'Höhe\s*\(mm\)|Höhe\s*mm',  # German with unit specification
            ],
            'depth': [
                r'\b(depth|tiefe|profondeur|profondità|profundidad|djup)\b',
                r'\b(thickness|dicke|épaisseur)\b',  # Sometimes depth is thickness
                r'data-key="z"',  # Specific to your site structure
                r'\b(z\s*axis|z-axis)\b'
            ],
            'dimensions': [
                r'length|width|height|size|dimension',
                r'länge|breite|höhe|größe|abmessung',
                r'longueur|largeur|hauteur|taille',
                r'lunghezza|larghezza|altezza',
                r'largo|ancho|alto',
                r'mass|masse|dimension',
                r'zuschnitt|schnitt|format',  # German cutting terms
                r'maße|maß|masse.*cm|dimension.*cm',  # German measurements
                r'data-key="[xyz]"',  # Generic coordinate detection
                r'fl_inpLabel|fl_inpBox'  # Your site's specific classes
            ],
            'quantity': [
                r'quantity|amount|aantal|anzahl|quantité|cantidad|stück',
                r'pieces|stück|pièces|pezzi|piezas',
                r'qty|menge|anz',
                r'exemplar|stückzahl',
                r'einlegeböden|shelves|regal',  # Specific product quantities
                r'data-but="b_swoodVar"'  # Your site's quantity selector
            ],
            'price': [
                r'price|preis|prix|prezzo|precio|kosten',
                r'cost|kosten|coût|costo',
                r'total|gesamt|totale|summe',
                r'€|\$|£|CHF|SEK|NOK|DKK|EUR',
                r'\d+[.,]\d+\s*€|\d+[.,]\d+\s*EUR',
                r'betrag|rechnungsbetrag|gesamtbetrag',
                r'netto|brutto|incl|excl|inkl|exkl',
                r'price.*display|preis.*anzeige'
            ],
            'add_to_cart': [
                r'add.*cart|in.*warenkorb|ajouter.*panier',
                r'buy|kaufen|acheter|comprare|comprar|bestellen',
                r'order|bestellen|commander|ordinare|pedir',
                r'cart|warenkorb|panier|carrello|carrito',
                r'hinzufügen|add|calculate|berechnen|rechnen',
                r'konfigur|konfig|config|setup',
                r'weiter|continue|next|fortfahren'
            ],
            'cookies': [
                r'accept.*cookie|cookie.*accept|cookies.*akzeptieren',
                r'akzeptieren|accepter|accettare|aceptar',
                r'allow.*all|alle.*zulassen|allow.*cookie',
                r'consent|einwilligung|consentement|zustimm',
                r'privacy|datenschutz|gdpr|dsgvo'
            ]
        }

    async def analyze_website(self, url: str) -> Dict[str, Any]:
        """Main method to analyze a website and generate configuration"""
        self.logger.info(f"Starting analysis of {url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            try:
                # Navigate to the website
                await page.goto(url, wait_until='networkidle')
                await asyncio.sleep(3)

                # Try to dismiss any popups/cookies first to reveal content
                await self._handle_initial_popups(page)
                await asyncio.sleep(2)

                # Look for configuration buttons and click them to reveal form fields
                config_triggered = await self._handle_configuration_buttons(page)
                if config_triggered:
                    await asyncio.sleep(3)  # Wait for dynamic content to load

                # Collect all analysis data
                analysis_results = {
                    'url': url,
                    'domain': self._extract_domain(url),
                    'timestamp': datetime.now().isoformat(),
                    'page_info': await self._analyze_page_structure(page),
                    'form_fields': await self._analyze_form_fields(page),
                    'interactive_elements': await self._find_interactive_elements(page),
                    'price_elements': await self._find_price_elements(page),
                    'navigation_elements': await self._find_navigation_elements(page),
                    'popup_elements': await self._find_popup_elements(page),
                    'suggested_config': None
                }

                # Generate suggested configuration
                analysis_results['suggested_config'] = await self._generate_config_steps(analysis_results)

                return analysis_results

            except Exception as e:
                self.logger.error(f"Error analyzing website: {e}")
                raise
            finally:
                await browser.close()

    async def _analyze_page_structure(self, page: Page) -> Dict[str, Any]:
        """Analyze the overall page structure"""
        return await page.evaluate("""
            () => {
                const info = {
                    title: document.title,
                    url: window.location.href,
                    forms: document.forms.length,
                    inputs: document.querySelectorAll('input').length,
                    selects: document.querySelectorAll('select').length,
                    buttons: document.querySelectorAll('button').length,
                    links: document.querySelectorAll('a').length,
                    has_jquery: typeof jQuery !== 'undefined',
                    has_react: !!document.querySelector('[data-reactroot]') || !!window.React,
                    has_vue: !!window.Vue,
                    has_angular: !!window.angular || !!document.querySelector('[ng-app]'),
                    framework_indicators: []
                };

                // Check for common frameworks
                if (document.querySelector('.woocommerce')) info.framework_indicators.push('WooCommerce');
                if (document.querySelector('[data-shopify]')) info.framework_indicators.push('Shopify');
                if (document.querySelector('.magento')) info.framework_indicators.push('Magento');

                return info;
            }
        """)

    async def _analyze_form_fields(self, page: Page) -> List[FormFieldInfo]:
        """Analyze all form fields on the page"""
        form_data = await page.evaluate("""
            () => {
                const fields = [];
                const inputs = document.querySelectorAll('input, select, textarea');

                inputs.forEach((element, index) => {
                    const rect = element.getBoundingClientRect();
                    const label = element.closest('label') ||
                                 document.querySelector(`label[for="${element.id}"]`) ||
                                 element.previousElementSibling ||
                                 element.closest('.fl_inpBox')?.querySelector('.fl_inpLabel') ||
                                 element.parentElement?.querySelector('.fl_inpLabel');

                    // Get unit information
                    const unitElement = element.closest('.fl_inpCnt')?.querySelector('.fl_inpUnit') ||
                                      element.parentElement?.querySelector('.fl_inpUnit');
                    const unit = unitElement ? unitElement.textContent.trim() : '';

                    fields.push({
                        selector: element.tagName.toLowerCase() +
                                 (element.id ? `#${element.id}` : '') +
                                 (element.className ? `.${element.className.split(' ').join('.')}` : '') +
                                 `:nth-of-type(${index + 1})`,
                        element_type: element.tagName.toLowerCase(),
                        input_type: element.type || 'text',
                        name: element.name || '',
                        id: element.id || '',
                        className: element.className || '',
                        placeholder: element.placeholder || '',
                        required: element.required || false,
                        value: element.value || '',
                        label_text: label ? label.textContent.trim() : '',
                        unit: unit,
                        data_key: element.getAttribute('data-key') || '',
                        data_but: element.getAttribute('data-but') || '',
                        step: element.getAttribute('step') || '',
                        visible: rect.width > 0 && rect.height > 0,
                        position: {
                            x: Math.round(rect.x),
                            y: Math.round(rect.y),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        }
                    });
                });

                // Get select options
                document.querySelectorAll('select').forEach((select, index) => {
                    const options = Array.from(select.options).map(opt => ({
                        value: opt.value,
                        text: opt.textContent.trim()
                    }));

                    const fieldIndex = fields.findIndex(f => f.selector.includes(select.id) || f.selector.includes(select.className));
                    if (fieldIndex >= 0) {
                        fields[fieldIndex].options = options;
                    }
                });

                return fields;
            }
        """)

        # Convert to FormFieldInfo objects and analyze purpose
        form_fields = []
        for field_data in form_data:
            if not field_data['visible']:
                continue

            # Determine field purpose
            purpose = self._classify_field_purpose(field_data)
            confidence = self._calculate_field_confidence(field_data, purpose)

            # Generate optimized selector
            selector = self._optimize_selector(field_data)

            form_field = FormFieldInfo(
                selector=selector,
                field_type=field_data['input_type'],
                name=field_data['name'],
                label=field_data['label_text'],
                placeholder=field_data['placeholder'],
                required=field_data['required'],
                options=field_data.get('options', []),
                confidence=confidence,
                purpose=purpose
            )

            form_fields.append(form_field)

        return form_fields

    async def _find_interactive_elements(self, page: Page) -> List[ElementInfo]:
        """Find clickable elements like buttons, links, etc."""
        elements_data = await page.evaluate("""
            () => {
                const elements = [];
                const clickableSelectors = 'button, a, [onclick], [role="button"], .btn, .button, input[type="submit"], input[type="button"]';
                const clickables = document.querySelectorAll(clickableSelectors);

                clickables.forEach((element, index) => {
                    const rect = element.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) return;

                    const text = element.textContent?.trim() || element.value || element.title || '';
                    const href = element.href || '';

                    elements.push({
                        selector: element.tagName.toLowerCase() +
                                 (element.id ? `#${element.id}` : '') +
                                 (element.className ? `.${element.className.split(' ').join('.')}` : ''),
                        element_type: element.tagName.toLowerCase(),
                        text: text,
                        href: href,
                        attributes: {
                            id: element.id || '',
                            className: element.className || '',
                            type: element.type || '',
                            role: element.getAttribute('role') || '',
                            onclick: element.getAttribute('onclick') || ''
                        },
                        position: {
                            x: Math.round(rect.x),
                            y: Math.round(rect.y),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        }
                    });
                });

                return elements;
            }
        """)

        # Analyze each element and classify its purpose
        interactive_elements = []
        for element_data in elements_data:
            purpose = self._classify_element_purpose(element_data)
            confidence = self._calculate_element_confidence(element_data, purpose)
            selector = self._optimize_selector(element_data)

            element_info = ElementInfo(
                selector=selector,
                element_type=element_data['element_type'],
                text=element_data['text'],
                attributes=element_data['attributes'],
                confidence=confidence,
                purpose=purpose,
                position=element_data['position']
            )

            interactive_elements.append(element_info)

        return interactive_elements

    async def _find_price_elements(self, page: Page) -> List[ElementInfo]:
        """Find elements that likely contain prices"""
        price_data = await page.evaluate("""
            () => {
                const priceElements = [];
                const priceSelectors = [
                    '[class*="price"]', '[class*="preis"]', '[class*="prix"]', '[class*="prezzo"]',
                    '[class*="cost"]', '[class*="kosten"]', '[class*="total"]', '[class*="gesamt"]',
                    '[class*="amount"]', '[class*="betrag"]', '[class*="summe"]',
                    '[id*="price"]', '[id*="preis"]', '[id*="cost"]', '[id*="total"]',
                    '[id*="gesamt"]', '[id*="betrag"]', '[id*="summe"]',
                    '.woocommerce-Price-amount', '.product-price', '.price-wrapper',
                    '[data-price]', '[data-preis]', '[data-cost]',
                    '.price-display', '.price-value', '.final-price', '.calculated-price'
                ];

                // Enhanced price pattern for European formats and currencies
                const pricePattern = /(€|EUR|\$|USD|£|GBP|CHF|SEK|NOK|DKK|PLN|CZK)\s*\d{1,6}[.,]?\d{0,2}|\d{1,6}[.,]?\d{0,2}\s*(€|EUR|\$|USD|£|GBP|CHF|SEK|NOK|DKK|PLN|CZK)/i;

                // German price terms
                const germanPriceTerms = /(preis|kosten|betrag|summe|gesamt|total|netto|brutto|inkl|exkl)/i;

                // Search all elements
                const allElements = document.querySelectorAll('*');

                allElements.forEach((element) => {
                    const text = element.textContent?.trim() || '';
                    const rect = element.getBoundingClientRect();

                    // Skip if element is invisible, but allow various sizes for price displays
                    if (rect.width === 0 || rect.height === 0) return;

                    // Skip very large containers (likely page sections)
                    if (rect.width > 800 || rect.height > 200) return;

                    // Check if element matches price selectors
                    const matchesSelector = priceSelectors.some(sel => {
                        try {
                            return element.matches(sel);
                        } catch(e) {
                            return false;
                        }
                    });

                    // Check if contains price pattern
                    const matchesPattern = pricePattern.test(text);

                    // Check if contains German price terms with numbers
                    const hasGermanPriceTerms = germanPriceTerms.test(text) && /\d/.test(text);

                    // Look for elements that might be price containers even if hidden initially
                    const hasDataAttributes = element.hasAttribute('data-price') ||
                                            element.hasAttribute('data-preis') ||
                                            element.hasAttribute('data-cost') ||
                                            element.hasAttribute('data-total');

                    if (matchesSelector || matchesPattern || hasGermanPriceTerms || hasDataAttributes) {
                        // Generate a better selector
                        let selector = '';
                        if (element.id) {
                            selector = `#${element.id}`;
                        } else if (element.className) {
                            const classes = element.className.split(' ').filter(c => c.length > 0);
                            if (classes.length > 0) {
                                selector = `.${classes.slice(0, 2).join('.')}`;
                            }
                        } else {
                            selector = element.tagName.toLowerCase();
                        }

                        priceElements.push({
                            selector: selector,
                            element_type: element.tagName.toLowerCase(),
                            text: text.substring(0, 100), // Limit text length
                            attributes: {
                                id: element.id || '',
                                className: element.className || '',
                                'data-price': element.getAttribute('data-price') || '',
                                'data-preis': element.getAttribute('data-preis') || ''
                            },
                            position: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height)
                            },
                            matches_pattern: matchesPattern,
                            matches_selector: matchesSelector,
                            has_german_terms: hasGermanPriceTerms,
                            has_data_attributes: hasDataAttributes
                        });
                    }
                });

                return priceElements;
            }
        """)

        price_elements = []
        for element_data in price_data:
            confidence = 0.8 if element_data.get('matches_selector', False) else 0.6
            if element_data.get('matches_pattern', False):
                confidence += 0.2
            if element_data.get('has_german_terms', False):
                confidence += 0.1
            if element_data.get('has_data_attributes', False):
                confidence += 0.1

            selector = self._optimize_selector(element_data)

            element_info = ElementInfo(
                selector=selector,
                element_type=element_data['element_type'],
                text=element_data['text'],
                attributes=element_data['attributes'],
                confidence=min(confidence, 1.0),
                purpose='price',
                position=element_data['position']
            )

            price_elements.append(element_info)

        return price_elements

    async def _find_popup_elements(self, page: Page) -> List[ElementInfo]:
        """Find popup elements like cookie banners, modals, etc."""
        popup_data = await page.evaluate("""
            () => {
                const popups = [];
                const popupSelectors = [
                    '[class*="cookie"]', '[class*="consent"]', '[class*="modal"]',
                    '[class*="popup"]', '[class*="overlay"]', '[class*="dialog"]',
                    '[id*="cookie"]', '[id*="consent"]', '[id*="modal"]'
                ];

                popupSelectors.forEach(selector => {
                    const elements = document.querySelectorAll(selector);
                    elements.forEach(element => {
                        const rect = element.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) return;

                        popups.push({
                            selector: selector,
                            element_type: element.tagName.toLowerCase(),
                            text: element.textContent?.trim().substring(0, 100) || '',
                            attributes: {
                                id: element.id || '',
                                className: element.className || ''
                            },
                            position: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height)
                            }
                        });
                    });
                });

                return popups;
            }
        """)

        popup_elements = []
        for element_data in popup_data:
            purpose = self._classify_popup_purpose(element_data)
            confidence = self._calculate_popup_confidence(element_data, purpose)

            element_info = ElementInfo(
                selector=element_data['selector'],
                element_type=element_data['element_type'],
                text=element_data['text'],
                attributes=element_data['attributes'],
                confidence=confidence,
                purpose=purpose,
                position=element_data['position']
            )

            popup_elements.append(element_info)

        return popup_elements

    async def _find_navigation_elements(self, page: Page) -> List[ElementInfo]:
        """Find navigation elements that might be needed"""
        nav_data = await page.evaluate("""
            () => {
                const navElements = [];
                const navSelectors = [
                    'nav a', '.navigation a', '.menu a', '.nav a',
                    '[class*="next"]', '[class*="continue"]', '[class*="proceed"]',
                    '[class*="weiter"]', '[class*="suivant"]'
                ];

                navSelectors.forEach(selector => {
                    const elements = document.querySelectorAll(selector);
                    elements.forEach(element => {
                        const rect = element.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) return;

                        navElements.push({
                            selector: selector,
                            element_type: element.tagName.toLowerCase(),
                            text: element.textContent?.trim() || '',
                            href: element.href || '',
                            attributes: {
                                id: element.id || '',
                                className: element.className || ''
                            },
                            position: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height)
                            }
                        });
                    });
                });

                return navElements;
            }
        """)

        nav_elements = []
        for element_data in nav_data:
            purpose = self._classify_nav_purpose(element_data)
            confidence = self._calculate_nav_confidence(element_data, purpose)

            element_info = ElementInfo(
                selector=element_data['selector'],
                element_type=element_data['element_type'],
                text=element_data['text'],
                attributes=element_data['attributes'],
                confidence=confidence,
                purpose=purpose,
                position=element_data['position']
            )

            nav_elements.append(element_info)

        return nav_elements

    def _classify_field_purpose(self, field_data: Dict) -> str:
        """Classify the purpose of a form field"""
        text_to_check = (
            field_data['label_text'] + ' ' +
            field_data['placeholder'] + ' ' +
            field_data['name'] + ' ' +
            field_data['id']
        ).lower()

        # Check data-key attribute for dimension mapping
        data_key = field_data.get('data_key', '').lower()
        if data_key:
            # Common data-key patterns for dimensions
            if data_key in ['x', 'length', 'width', 'w', 'breite']:
                return 'width'
            elif data_key in ['y', 'height', 'h', 'höhe']:
                return 'height'
            elif data_key in ['z', 'depth', 'thickness', 't', 'd', 'tiefe', 'dicke']:
                return 'thickness'

        # Check unit information for dimension fields
        unit = field_data.get('unit', '').lower()
        if unit in ['mm', 'cm', 'm', 'inch', 'ft']:
            # Dimension field based on text analysis
            if any(dim in text_to_check for dim in ['breite', 'width', 'länge', 'length', 'x']):
                return 'width'
            elif any(dim in text_to_check for dim in ['höhe', 'height', 'y']):
                return 'height'
            elif any(dim in text_to_check for dim in ['tiefe', 'depth', 'dicke', 'thickness', 'stärke', 'z']):
                return 'thickness'
            else:
                return 'dimensions'

        for purpose, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_to_check, re.IGNORECASE):
                    return purpose

        # Check by field type
        if field_data['input_type'] in ['email']:
            return 'email'
        elif field_data['input_type'] in ['tel', 'phone']:
            return 'phone'
        elif field_data['input_type'] in ['number']:
            if any(dim in text_to_check for dim in ['length', 'width', 'height', 'size', 'breite', 'höhe', 'tiefe']):
                return 'dimensions'
            return 'quantity'

        return 'unknown'

    def _classify_element_purpose(self, element_data: Dict) -> str:
        """Classify the purpose of an interactive element"""
        text_to_check = (element_data['text'] + ' ' +
                        element_data['attributes'].get('className', '') + ' ' +
                        element_data['attributes'].get('id', '')).lower()

        for purpose, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_to_check, re.IGNORECASE):
                    return purpose

        return 'unknown'

    def _classify_popup_purpose(self, element_data: Dict) -> str:
        """Classify the purpose of a popup element"""
        text_to_check = (element_data['text'] + ' ' +
                        element_data['attributes'].get('className', '') + ' ' +
                        element_data['attributes'].get('id', '')).lower()

        if any(term in text_to_check for term in ['cookie', 'consent', 'gdpr']):
            return 'cookies'
        elif any(term in text_to_check for term in ['modal', 'dialog', 'popup']):
            return 'modal'

        return 'popup'

    def _classify_nav_purpose(self, element_data: Dict) -> str:
        """Classify the purpose of a navigation element"""
        text_to_check = element_data['text'].lower()

        if any(term in text_to_check for term in ['next', 'continue', 'weiter', 'suivant', 'proceed']):
            return 'next_step'
        elif any(term in text_to_check for term in ['back', 'previous', 'zurück', 'précédent']):
            return 'previous_step'
        elif any(term in text_to_check for term in ['cart', 'warenkorb', 'panier', 'checkout']):
            return 'cart'

        return 'navigation'

    def _calculate_field_confidence(self, field_data: Dict, purpose: str) -> float:
        """Calculate confidence score for field classification"""
        confidence = 0.5  # Base confidence

        # Boost confidence based on label quality
        if field_data['label_text']:
            confidence += 0.2

        # Boost confidence based on specific attributes
        if field_data['name'] and purpose in field_data['name'].lower():
            confidence += 0.2

        if field_data['id'] and purpose in field_data['id'].lower():
            confidence += 0.1

        # Boost for required fields that match expected purposes
        if field_data['required'] and purpose in ['thickness', 'dimensions', 'quantity']:
            confidence += 0.1

        return min(confidence, 1.0)

    def _calculate_element_confidence(self, element_data: Dict, purpose: str) -> float:
        """Calculate confidence score for element classification"""
        confidence = 0.5

        # Boost based on text content quality
        if element_data['text'] and len(element_data['text']) > 0:
            confidence += 0.2

        # Boost based on class names
        if purpose in element_data['attributes'].get('className', '').lower():
            confidence += 0.2

        # Boost based on element type
        if element_data['element_type'] == 'button' and purpose == 'add_to_cart':
            confidence += 0.1

        return min(confidence, 1.0)

    def _calculate_popup_confidence(self, element_data: Dict, purpose: str) -> float:
        """Calculate confidence score for popup classification"""
        confidence = 0.6  # Higher base for popups since they're more obvious

        if purpose in element_data['text'].lower():
            confidence += 0.3

        return min(confidence, 1.0)

    def _calculate_nav_confidence(self, element_data: Dict, purpose: str) -> float:
        """Calculate confidence score for navigation classification"""
        confidence = 0.5

        if purpose in element_data['text'].lower():
            confidence += 0.3

        if element_data['href']:
            confidence += 0.1

        return min(confidence, 1.0)

    def _optimize_selector(self, element_data: Dict) -> str:
        """Generate an optimized CSS selector for the element"""
        # Handle different data structures (form fields vs interactive elements)
        if 'attributes' in element_data:
            # Interactive elements structure
            attributes = element_data['attributes']
            element_id = attributes.get('id', '')
            class_name = attributes.get('className', '')
        else:
            # Form fields structure
            element_id = element_data.get('id', '')
            class_name = element_data.get('className', '')

        # Prefer ID selectors when available
        if element_id:
            return f"#{element_id}"

        # Use class-based selectors
        if class_name:
            classes = class_name.split()
            # Filter out generic classes
            specific_classes = [c for c in classes if len(c) > 2 and
                              c not in ['btn', 'button', 'form-control', 'input']]
            if specific_classes:
                return f".{'.'.join(specific_classes[:2])}"  # Use first 2 specific classes

        # Fallback to the original selector
        return element_data.get('selector', '')

    async def _generate_config_steps(self, analysis_results: Dict) -> List[Dict[str, Any]]:
        """Generate suggested configuration steps based on analysis"""
        steps = []

        # 1. Handle popups/cookies first
        cookie_elements = [el for el in analysis_results['interactive_elements']
                          if el.purpose == 'cookies' and el.confidence > 0.7]

        if cookie_elements:
            steps.append({
                "type": "click",
                "selector": cookie_elements[0].selector,
                "description": "Accept cookies",
                "confidence": cookie_elements[0].confidence
            })
            steps.append({
                "type": "wait",
                "duration": "short"
            })

        # 2. Handle form fields in logical order
        form_fields = analysis_results['form_fields']

        # Thickness field
        thickness_fields = [f for f in form_fields if f.purpose == 'thickness' and f.confidence > 0.6]
        if thickness_fields:
            field = thickness_fields[0]
            step = {
                "type": "select" if field.field_type == "select" else "input",
                "selector": field.selector,
                "value": "{thickness}",
                "unit": "mm",
                "description": f"Set thickness value",
                "confidence": field.confidence
            }
            if field.options:
                step["options"] = field.options
            steps.append(step)

        # Dimension fields
        dimension_fields = [f for f in form_fields if f.purpose == 'dimensions' and f.confidence > 0.6]
        for field in dimension_fields[:2]:  # Limit to first 2 dimension fields
            field_name = "length" if "length" in field.label.lower() else "width"
            steps.append({
                "type": "input",
                "selector": field.selector,
                "value": f"{{{field_name}}}",
                "unit": "mm",
                "description": f"Set {field_name} value",
                "confidence": field.confidence
            })

        # Quantity field
        quantity_fields = [f for f in form_fields if f.purpose == 'quantity' and f.confidence > 0.6]
        if quantity_fields:
            steps.append({
                "type": "input",
                "selector": quantity_fields[0].selector,
                "value": "{quantity}",
                "description": "Set quantity",
                "confidence": quantity_fields[0].confidence
            })

        # 3. Add to cart or calculate
        cart_elements = [el for el in analysis_results['interactive_elements']
                        if el.purpose == 'add_to_cart' and el.confidence > 0.7]
        if cart_elements:
            steps.append({
                "type": "click",
                "selector": cart_elements[0].selector,
                "description": "Add to cart or calculate price",
                "confidence": cart_elements[0].confidence
            })

        # 4. Wait for price calculation
        steps.append({
            "type": "wait",
            "duration": "default"
        })

        # 5. Read price
        price_elements = [el for el in analysis_results['price_elements']
                         if el.confidence > 0.7]
        if price_elements:
            # Sort by confidence and take the best one
            best_price_element = max(price_elements, key=lambda x: x.confidence)
            steps.append({
                "type": "read_price",
                "selector": best_price_element.selector,
                "description": "Extract calculated price",
                "confidence": best_price_element.confidence
            })

        return steps

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        parsed = urlparse(url)
        return parsed.netloc.replace('www.', '')

    def export_config(self, analysis_results: Dict, output_format: str = 'json') -> str:
        """Export the analysis results and suggested config"""
        if output_format == 'json':
            return json.dumps(analysis_results, indent=2, default=str)

        # Add other export formats as needed
        return str(analysis_results)

    def generate_summary_report(self, analysis_results: Dict) -> str:
        """Generate a human-readable summary report"""
        domain = analysis_results['domain']
        config_steps = analysis_results['suggested_config']

        report = f"""
Configuration Analysis Report for {domain}
========================================

Analysis completed at: {analysis_results['timestamp']}

Page Structure:
- Forms found: {analysis_results['page_info']['forms']}
- Input fields: {analysis_results['page_info']['inputs']}
- Select fields: {analysis_results['page_info']['selects']}
- Buttons: {analysis_results['page_info']['buttons']}

Key Elements Detected:
"""

        # Form fields summary
        form_fields = analysis_results['form_fields']
        thickness_fields = [f for f in form_fields if f.purpose == 'thickness']
        dimension_fields = [f for f in form_fields if f.purpose == 'dimensions']
        quantity_fields = [f for f in form_fields if f.purpose == 'quantity']

        report += f"""
Form Fields:
- Thickness fields: {len(thickness_fields)}
- Dimension fields: {len(dimension_fields)}
- Quantity fields: {len(quantity_fields)}

Interactive Elements:
- Cookie consent: {len([el for el in analysis_results['interactive_elements'] if el.purpose == 'cookies'])}
- Add to cart buttons: {len([el for el in analysis_results['interactive_elements'] if el.purpose == 'add_to_cart'])}

Price Elements:
- Price displays found: {len(analysis_results['price_elements'])}

Suggested Configuration Steps: {len(config_steps)}
"""

        for i, step in enumerate(config_steps, 1):
            confidence = step.get('confidence', 0)
            report += f"{i}. {step['type'].upper()}: {step.get('description', 'No description')} (Confidence: {confidence:.1%})\n"

        return report

    async def _handle_initial_popups(self, page: Page):
        """Try to handle common popups and overlays to reveal underlying content"""
        try:
            # Common cookie/consent button selectors
            popup_selectors = [
                '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',  # Cookiebot
                '[data-cy="accept-all"]',
                '.cookie-accept',
                '.accept-all',
                '.consent-accept',
                '[aria-label*="Accept"]',
                '[aria-label*="Akzeptieren"]',
                'button:has-text("Accept all")',
                'button:has-text("Alle akzeptieren")',
                'button:has-text("Accept")',
                'button:has-text("Akzeptieren")',
                '.btn:has-text("OK")',
                '[onclick*="accept"]',
                '[onclick*="consent"]'
            ]

            for selector in popup_selectors:
                try:
                    # Check if element exists and is visible
                    element = await page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            self.logger.info(f"Clicking popup element: {selector}")
                            await element.click()
                            await asyncio.sleep(1)
                            break  # Only click the first found popup
                except Exception as e:
                    continue  # Try next selector

            # Close any modal overlays
            modal_selectors = [
                '.modal .close',
                '.overlay .close',
                '[aria-label="Close"]',
                '[aria-label="Schließen"]',
                '.modal-close',
                '.close-button'
            ]

            for selector in modal_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        await asyncio.sleep(0.5)
                except Exception:
                    continue
        except Exception as e:
            self.logger.debug(f"Error handling popups: {e}")

    async def _handle_configuration_buttons(self, page: Page) -> bool:
        """Handle configuration buttons that reveal form fields"""
        self.logger.info("Looking for configuration buttons...")

        # Configuration button patterns (German and other languages)
        config_button_selectors = [
            # Specific selectors for German sites - the original error pattern!
            '.fl_thicks .fl_but',
            '.fl_but[data-but="b_showAll"]',
            '.btn-confi',
            '[name="fl_inWarenkorb"]',

            # Generic configuration button patterns
            '*[class*="config"]',
            '*[class*="konfig"]',
            '*[data-action*="config"]',
            '*[data-action*="configure"]',

            # Text-based selectors (more flexible)
            'button:has-text("konfigurieren")',
            'button:has-text("Jetzt konfigurieren")',
            'button:has-text("configure")',
            'button:has-text("Configure")',
            'button:has-text("Customize")',
            'button:has-text("anpassen")',

            # Common button classes that might trigger configuration
            '.customize-btn',
            '.configure-btn',
            '.product-config',
            '.open-configurator'
        ]

        # Try to find and click configuration buttons
        for selector in config_button_selectors:
            try:
                self.logger.info(f"Checking for configuration button: {selector}")

                # Wait a bit for the element to appear
                await page.wait_for_selector(selector, timeout=2000)

                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    # Check if the button text suggests it's a configuration button
                    text = await element.text_content()
                    if text:
                        text_lower = text.lower().strip()
                        config_keywords = [
                            'konfigurieren', 'configure', 'customize', 'anpassen',
                            'konfig', 'config', 'einstellungen', 'settings',
                            'optionen', 'options', 'auswählen', 'wählen'
                        ]

                        if any(keyword in text_lower for keyword in config_keywords):
                            self.logger.info(f"Found configuration button: '{text}' with selector: {selector}")

                            # Scroll the element into view
                            await element.scroll_into_view_if_needed()
                            await asyncio.sleep(0.5)

                            # Click the button
                            await element.click()
                            self.logger.info(f"Clicked configuration button: '{text}'")

                            # Wait for potential page changes/dynamic content
                            await asyncio.sleep(2)

                            # Check if new content appeared (like form fields)
                            new_inputs = await page.query_selector_all('input, select, textarea')
                            if len(new_inputs) > 0:
                                self.logger.info(f"Configuration revealed {len(new_inputs)} input elements")
                                return True

                            return True  # Button was clicked successfully

            except Exception as e:
                self.logger.debug(f"Could not interact with selector {selector}: {e}")
                continue

        # Try to find buttons by their visible text (fallback method)
        try:
            all_buttons = await page.query_selector_all('button, input[type="button"], input[type="submit"], .btn, [role="button"]')

            for button in all_buttons:
                if await button.is_visible():
                    text = await button.text_content()
                    if text:
                        text_lower = text.lower().strip()
                        if any(keyword in text_lower for keyword in ['konfigurieren', 'configure', 'jetzt', 'customize']):
                            self.logger.info(f"Found configuration button by text: '{text}'")

                            await button.scroll_into_view_if_needed()
                            await asyncio.sleep(0.5)
                            await button.click()

                            self.logger.info(f"Clicked configuration button: '{text}'")
                            await asyncio.sleep(2)
                            return True

        except Exception as e:
            self.logger.debug(f"Error in text-based button detection: {e}")

        self.logger.info("No configuration buttons found or clicked")
        return False
