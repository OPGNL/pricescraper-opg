"""
Enhanced Website Configuration Analyzer
Automatically analyzes websites and generates production-ready scraping configurations
"""

from playwright.async_api import async_playwright, Page, Browser
from typing import Dict, List, Any, Optional, Tuple, Set
from urllib.parse import urlparse, urljoin
import re
import json
import asyncio
from datetime import datetime
import logging
from dataclasses import dataclass, asdict
from enum import Enum

class StepType(Enum):
    """Enumeration of all possible step types"""
    CLICK = "click"
    INPUT = "input"
    SELECT = "select"
    WAIT = "wait"
    READ_PRICE = "read_price"
    NAVIGATE = "navigate"
    BLUR = "blur"
    MODIFY_ELEMENT = "modify_element"

class FieldType(Enum):
    """Enumeration of field purposes"""
    THICKNESS = "thickness"
    LENGTH = "length"
    WIDTH = "width"
    HEIGHT = "height"
    DEPTH = "depth"
    QUANTITY = "quantity"
    DIMENSIONS = "dimensions"
    PRICE = "price"
    UNKNOWN = "unknown"

class ElementPurpose(Enum):
    """Enumeration of element purposes"""
    COOKIE_CONSENT = "cookies"
    CONFIGURATION = "configuration"
    ADD_TO_CART = "add_to_cart"
    NAVIGATION = "navigation"
    PRICE_DISPLAY = "price"
    MODAL = "modal"
    POPUP = "popup"
    SHIPPING = "shipping"
    QUANTITY_INPUT = "quantity"
    DIMENSION_INPUT = "dimension"

@dataclass
class AnalysisContext:
    """Context information for analysis"""
    domain: str
    language: str = "en"
    framework: Optional[str] = None
    has_configurator: bool = False
    requires_navigation: bool = False
    multi_step_checkout: bool = False

@dataclass
class ConfigStep:
    """Represents a single configuration step"""
    type: str
    selector: Optional[str] = None
    value: Optional[str] = None
    unit: Optional[str] = None
    duration: Optional[str] = None
    includes_vat: Optional[bool] = None
    calculation: Optional[str] = None
    continue_on_error: Optional[bool] = None
    clear_first: Optional[bool] = None
    description: Optional[str] = None
    randomize: Optional[bool] = None
    random_type: Optional[str] = None
    default_value: Optional[float] = None
    option_selector: Optional[str] = None
    add_class: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values"""
        result = {}
        for key, value in asdict(self).items():
            if value is not None:
                result[key] = value
        return result

@dataclass
class WorkflowPattern:
    """Represents a detected workflow pattern"""
    name: str
    confidence: float
    steps: List[ConfigStep]
    required_elements: List[str]
    optional_elements: List[str] = None

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

class EnhancedConfigAnalyzer:
    """Enhanced analyzer that generates production-ready configurations"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.context: Optional[AnalysisContext] = None

        # Enhanced pattern recognition
        self.dimension_patterns = self._build_dimension_patterns()
        self.interaction_patterns = self._build_interaction_patterns()
        self.workflow_patterns = self._build_workflow_patterns()

        # Common selectors for different frameworks/sites
        self.framework_selectors = {
            'cookiebot': {
                'accept': '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
                'decline': '#CybotCookiebotDialogBodyButtonDecline'
            },
            'woocommerce': {
                'add_to_cart': '.single_add_to_cart_button',
                'cart': '.woocommerce-cart',
                'quantity': '.qty'
            },
            'shopify': {
                'add_to_cart': '[data-shopify]',
                'cart': '.cart'
            }
        }

    def _build_dimension_patterns(self) -> Dict[str, List[str]]:
        """Build comprehensive dimension detection patterns"""
        return {
            'thickness': [
                # English
                r'\b(thick|thickness|depth|height)\b',
                r'\bmaterial\s*(thick|depth)\b',
                r'\b\d+\s*mm\s*(thick|deep)\b',

                # German
                r'\b(dick|dicke|stärke|starke|tiefe)\b',
                r'plattenstärke|materialstärke',
                r'Tiefe\s*\(mm\)|Dicke\s*\(mm\)',

                # French
                r'\b(épaisseur|profondeur)\b',

                # Dutch
                r'\b(dikte|diepte)\b',

                # Data attributes
                r'data-key="[zt]"',
                r'data-dimension="thickness"',

                # Form field names/ids
                r'thickness|dikte|dicke|epaisseur',
            ],
            'length': [
                # English
                r'\b(length|long|horizontal)\b',
                r'\b(x\s*axis|x-axis)\b',

                # German
                r'\b(länge|lang|breite)\b',
                r'Länge\s*\(mm\)|Breite\s*\(mm\)',

                # French
                r'\b(longueur|long)\b',

                # Dutch
                r'\b(lengte|lang)\b',

                # Data attributes
                r'data-key="[x0]"',
                r'data-dimension="length"',

                # Form field names/ids
                r'length|lengte|länge|longueur',
            ],
            'width': [
                # English
                r'\b(width|wide|vertical)\b',
                r'\b(y\s*axis|y-axis)\b',

                # German
                r'\b(breite|breit|höhe)\b',
                r'Breite\s*\(mm\)|Höhe\s*\(mm\)',

                # French
                r'\b(largeur|large|hauteur)\b',

                # Dutch
                r'\b(breedte|breed|hoogte)\b',

                # Data attributes
                r'data-key="[y12]"',
                r'data-dimension="width"',

                # Form field names/ids
                r'width|breedte|breite|largeur',
            ],
            'quantity': [
                # English
                r'\b(quantity|amount|qty|pieces|pcs)\b',

                # German
                r'\b(anzahl|menge|stück|stk|exemplar)\b',

                # French
                r'\b(quantité|nombre|pièces)\b',

                # Dutch
                r'\b(aantal|hoeveelheid|stuks)\b',

                # Data attributes
                r'data-but=".*quantity.*"',
                r'data-dimension="quantity"',

                # Form field names/ids
                r'quantity|aantal|anzahl|quantite',
            ]
        }

    def _build_interaction_patterns(self) -> Dict[str, List[str]]:
        """Build interaction element detection patterns"""
        return {
            'configuration': [
                # Button text patterns
                r'konfigur|konfig|config|setup|customize|anpassen',
                r'jetzt\s*konfigurieren|configure\s*now',
                r'product\s*config|produkt\s*konfig',

                # Class/ID patterns
                r'\.config|\.konfig|\.customize',
                r'#config|#konfig|#customize',
                r'data-action="config"',

                # Common German site patterns
                r'\.btn-confi|\.fl_but',
                r'button\[name="configure"\]',
            ],
            'add_to_cart': [
                # Multi-language button text
                r'add.*cart|in.*warenkorb|ajouter.*panier',
                r'buy|kaufen|acheter|comprare|comprar|bestellen',
                r'order|bestellen|commander|ordinare|pedir',
                r'hinzufügen|toevoegen|agregar',

                # Class patterns
                r'\.add.*cart|\.single_add_to_cart',
                r'\.btn.*buy|\.buy.*btn',
                r'\.addtobasket|\.add-to-basket',

                # Name/ID patterns
                r'name=".*cart.*"|name=".*bestell.*"',
                r'id=".*cart.*"|id=".*buy.*"',
            ],
            'cookies': [
                # Accept patterns
                r'accept.*cookie|cookie.*accept|akzeptieren',
                r'allow.*all|alle.*zulassen|tout.*accepter',
                r'consent|einwilligung|toestemming',

                # Class/ID patterns
                r'\.accept.*cookie|\.cookie.*accept',
                r'#accept.*cookie|#cookie.*accept',
                r'\.btn.*accept|\.accept.*btn',
            ]
        }

    def _build_workflow_patterns(self) -> List[WorkflowPattern]:
        """Build common workflow patterns"""
        return [
            WorkflowPattern(
                name="simple_configurator",
                confidence=0.8,
                steps=[],
                required_elements=["dimension_inputs", "add_to_cart", "price_display"],
                optional_elements=["thickness_selector", "quantity_input"]
            ),
            WorkflowPattern(
                name="complex_configurator",
                confidence=0.9,
                steps=[],
                required_elements=["config_button", "dimension_inputs", "add_to_cart", "cart_navigation", "price_display"],
                optional_elements=["thickness_selector", "quantity_input"]
            ),
            WorkflowPattern(
                name="cart_checkout",
                confidence=0.7,
                steps=[],
                required_elements=["dimension_inputs", "add_to_cart", "cart_page", "checkout_process"],
                optional_elements=["user_registration", "shipping_selection"]
            )
        ]

    async def analyze_website_comprehensive(self, url: str, max_depth: int = 3) -> Dict[str, Any]:
        """Comprehensive website analysis with multi-page exploration"""
        self.logger.info(f"Starting comprehensive analysis of {url}")

        self.context = AnalysisContext(domain=self._extract_domain(url))

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)

            try:
                analysis_results = {
                    'url': url,
                    'domain': self.context.domain,
                    'timestamp': datetime.now().isoformat(),
                    'analysis_metadata': {
                        'version': '2.0',
                        'depth': max_depth,
                        'comprehensive': True
                    },
                    'page_analysis': {},
                    'workflow_patterns': [],
                    'suggested_configs': {},
                    'confidence_scores': {}
                }

                # Analyze main page
                page = await browser.new_page()
                self.logger.info(f"Analyzing main page: {url}")
                main_analysis = await self._analyze_page_comprehensive(page, url, "main")
                analysis_results['page_analysis']['main'] = main_analysis

                # Detect framework and language
                self.logger.info("Detecting framework and language")
                await self._detect_framework_and_language(page)

                # Navigate and explore configurator if found
                self.logger.info("Exploring configurator workflow if present")
                configurator_analysis = await self._explore_configurator_workflow(page)
                if configurator_analysis:
                    print("Configurator workflow detected and analyzed successfully.")
                    print(configurator_analysis)
                    analysis_results['page_analysis']['configurator'] = configurator_analysis

                # Explore cart workflow
                # self.logger.info("Exploring cart workflow if present")
                # cart_analysis = await self._explore_cart_workflow(page)
                # if cart_analysis:
                #     analysis_results['page_analysis']['cart'] = cart_analysis


                await page.close()
                return analysis_results

            except Exception as e:
                self.logger.error(f"Error in comprehensive analysis: {e}")
                raise
            finally:
                await browser.close()

    async def _analyze_page_comprehensive(self, page: Page, url: str, page_type: str) -> Dict[str, Any]:
        """Comprehensive analysis of a single page"""
        await page.goto(url, wait_until='networkidle')
        await asyncio.sleep(2)

        # Handle initial popups
        await self._handle_popups_enhanced(page)

        # Collect comprehensive page data
        page_analysis = {
            'url': page.url,
            'page_type': page_type,
            'page_structure': await self._analyze_page_structure_enhanced(page),
            'form_fields': await self._analyze_form_fields_enhanced(page),
            'interactive_elements': await self._find_interactive_elements_enhanced(page),
            'price_elements': await self._find_price_elements_enhanced(page),
            'workflow_triggers': await self._find_workflow_triggers(page),
            'framework_detection': await self._detect_page_framework(page)
        }

        return page_analysis

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        parsed = urlparse(url)
        return parsed.netloc.replace('www.', '')

    def export_config(self, analysis_results: Dict, output_format: str = 'json') -> str:
        """Export the analysis results and suggested config in database format"""
        if output_format == 'json':
            # Return only the suggested configs in the correct database format
            config = analysis_results.get('suggested_configs', {})
            return json.dumps(config, indent=2, default=str)

        return str(analysis_results.get('suggested_configs', {}))

    def generate_summary_report(self, analysis_results: Dict) -> str:
        """Generate a human-readable summary report"""
        domain = analysis_results['domain']
        config = analysis_results.get('suggested_configs', {})
        categories = config.get('categories', {})

        report = f"""
Enhanced Configuration Analysis Report for {domain}
=================================================

Analysis completed at: {analysis_results['timestamp']}
Analysis version: {analysis_results.get('analysis_metadata', {}).get('version', 'N/A')}

Configuration Categories Generated:
"""

        for category, category_config in categories.items():
            steps = category_config.get('steps', [])
            report += f"""
{category.upper()}:
- Steps generated: {len(steps)}
- Workflow type: {'Complex' if len(steps) > 10 else 'Simple'}
"""

        report += f"""

Generated Configuration Ready for Database Storage:
- Domain: {domain}
- Categories: {list(categories.keys())}
- Total configuration steps: {sum(len(cat.get('steps', [])) for cat in categories.values())}

The configuration follows the production database schema and can be directly imported.
"""
        return report

    # Placeholder methods for the comprehensive analysis
    # These would be implemented with the actual logic

    async def _handle_popups_enhanced(self, page: Page):
        """Enhanced popup handling with comprehensive cookie consent detection"""
        try:
            # Wait a moment for popups to appear
            await asyncio.sleep(2)

            # Comprehensive list of cookie consent selectors
            cookie_selectors = [
                # Cookiebot (expresszuschnitt.de uses this)
                '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
                '#CybotCookiebotDialogBodyButtonAccept',
                '#CybotCookiebotDialogBodyButtonDecline',

                # Generic cookie accept buttons
                '[data-cy="accept-all"]', '[data-testid="accept-all"]',
                '.cookie-accept', '.accept-all', '.consent-accept',
                '[aria-label*="Accept"]', '[aria-label*="Akzeptieren"]',
                '[aria-label*="Alle akzeptieren"]', '[aria-label*="Accept all"]',

                # Text-based selectors
                'button:has-text("Accept all")', 'button:has-text("Alle akzeptieren")',
                'button:has-text("Accept")', 'button:has-text("Akzeptieren")',
                'button:has-text("OK")', 'button:has-text("Zustimmen")',

                # ID/Class patterns
                '#accept-cookies', '#cookie-accept', '#consent-accept',
                '.btn-accept', '.cookie-btn-accept', '.gdpr-accept',

                # Generic patterns that might work
                '[onclick*="accept"]', '[onclick*="consent"]',
                '[data-action*="accept"]', '[data-consent="accept"]'
            ]

            for selector in cookie_selectors:
                try:
                    # Check if element exists and is visible
                    element = await page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        if is_visible:
                            self.logger.info(f"Found and clicking cookie consent: {selector}")
                            await element.click()
                            await asyncio.sleep(1)
                            return True  # Successfully handled popup
                except Exception as e:
                    self.logger.debug(f"Could not click selector {selector}: {e}")
                    continue

            # Try to close any modal overlays
            modal_selectors = [
                '.modal .close', '.overlay .close',
                '[aria-label="Close"]', '[aria-label="Schließen"]',
                '.modal-close', '.close-button',
                '.popup-close', '[data-dismiss="modal"]'
            ]

            for selector in modal_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        await asyncio.sleep(0.5)
                        break
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Error in popup handling: {e}")

        return False

    async def _analyze_page_structure_enhanced(self, page: Page) -> Dict[str, Any]:
        """Enhanced page structure analysis"""
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

    async def _analyze_form_fields_enhanced(self, page: Page) -> List[FormFieldInfo]:
        """Enhanced form field analysis"""
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

                return fields;
            }
        """)

        # Convert to FormFieldInfo objects (simplified for now)
        return []

    async def _find_interactive_elements_enhanced(self, page: Page) -> List[ElementInfo]:
        """Enhanced interactive element detection"""
        # Simplified implementation for now
        return []

    async def _find_price_elements_enhanced(self, page: Page) -> List[ElementInfo]:
        """Enhanced price element detection"""
        # Simplified implementation for now
        return []

    async def _find_workflow_triggers(self, page: Page) -> List[Dict[str, Any]]:
        """Find elements that trigger configurator workflows"""
        # Look for configuration buttons
        config_buttons = await page.evaluate("""
            () => {
                const buttons = [];
                const selectors = [
                    '.btn-confi', '.fl_but', '[data-action*="config"]',
                    'button:has-text("konfigurieren")', 'button:has-text("Configure")',
                    '.customize-btn', '.configure-btn'
                ];

                selectors.forEach(selector => {
                    try {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach(el => {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                buttons.push({
                                    selector: selector,
                                    text: el.textContent?.trim() || '',
                                    type: 'configuration_trigger'
                                });
                            }
                        });
                    } catch(e) {}
                });

                return buttons;
            }
        """)

        return config_buttons

    async def _detect_page_framework(self, page: Page) -> Dict[str, Any]:
        """Detect the framework/CMS used by the page"""
        return await page.evaluate("""
            () => {
                const frameworks = [];

                // Check for common indicators
                if (window.jQuery) frameworks.push('jQuery');
                if (window.React) frameworks.push('React');
                if (window.Vue) frameworks.push('Vue');
                if (window.angular) frameworks.push('Angular');

                // Check for CMS indicators
                if (document.querySelector('.woocommerce')) frameworks.push('WooCommerce');
                if (document.querySelector('[data-shopify]')) frameworks.push('Shopify');
                if (document.querySelector('.magento')) frameworks.push('Magento');

                return {
                    detected_frameworks: frameworks,
                    has_spa_indicators: !!document.querySelector('[data-reactroot], [ng-app], #__nuxt')
                };
            }
        """)

    async def _detect_framework_and_language(self, page: Page):
        """Detect framework and language from page"""
        try:
            lang_info = await page.evaluate("""
                () => {
                    return {
                        lang: document.documentElement.lang || 'en',
                        title: document.title,
                        url: window.location.href
                    };
                }
            """)

            # Update context
            if lang_info.get('lang'):
                detected_lang = lang_info['lang'][:2].lower()
                if detected_lang in ['de', 'en', 'fr', 'nl', 'es', 'it']:
                    self.context.language = detected_lang
        except Exception as e:
            self.logger.debug(f"Could not detect language: {e}")

    async def _explore_configurator_workflow(self, page: Page) -> Optional[Dict[str, Any]]:
        """Explore and analyze configurator workflow by actually executing it"""
        try:
            self.logger.info("Exploring configurator workflow...")

            # Step 1: Look for and click configurator triggers
            config_selectors = [
                '.btn-confi.fl_but', '.btn-confi', '[data-action="configure"]',
                'button:has-text("konfigurieren")', 'button:has-text("Configure")'
            ]

            configurator_triggered = False
            for selector in config_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        self.logger.info(f"Clicking configurator trigger: {selector}")
                        await element.click()
                        await asyncio.sleep(3)
                        configurator_triggered = True
                        break
                except Exception as e:
                    self.logger.debug(f"Could not click configurator {selector}: {e}")
                    continue

            if not configurator_triggered:
                self.logger.info("No configurator trigger found or clickable")
                return None

            # Step 2: Don't change dimensions - use whatever defaults are set
            self.logger.info("Using default dimension values (not changing any inputs)")

            # Just check what dimension fields are available without changing them
            available_fields = await self._detect_dimension_fields(page)

            await asyncio.sleep(3)

            # Step 3: Try to add to cart with current/default values
            cart_success = await self._add_to_cart(page)

            # Step 4: Navigate to cart page
            cart_analysis = None
            if cart_success:
                cart_analysis = await self._navigate_to_cart_and_analyze(page)

            return {
                'trigger_selector': 'configurator found',
                'configurator_triggered': configurator_triggered,
                'available_fields': available_fields,
                'added_to_cart': cart_success,
                'cart_analysis': cart_analysis,
                'workflow_detected': True
            }

        except Exception as e:
            self.logger.error(f"Error exploring configurator: {e}")
            return None

    async def _fill_dimension_fields(self, page: Page, test_values: Dict[str, str]) -> Dict[str, bool]:
        """Fill dimension fields with test values"""
        filled_fields = {}

        # Domain-specific field patterns
        domain = self.context.domain

        if 'expresszuschnitt' in domain:
            # ExpressZuschnitt.de specific selectors
            field_mappings = {
                'length': 'input.fl_but[data-key="x"]',
                'width': 'input.fl_but[data-key="y"]',
                'thickness': 'input.fl_but[data-key="z"]',
                'quantity': 'input.fl_but[data-but="b_swoodVar"]'
            }
        else:
            # Generic field patterns
            field_mappings = {
                'length': 'input[name*="length"], input[data-key="x"], #length, input[placeholder*="length"]',
                'width': 'input[name*="width"], input[data-key="y"], #width, input[placeholder*="width"]',
                'thickness': 'input[name*="thickness"], input[data-key="z"], #thickness, input[placeholder*="thick"]',
                'quantity': 'input[name*="quantity"], .qty, #quantity, input[placeholder*="quantity"]'
            }

        for field_name, selector in field_mappings.items():
            try:
                value = test_values.get(field_name, '1')

                # Try multiple selectors for generic patterns
                selectors = selector.split(', ') if ', ' in selector else [selector]

                for sel in selectors:
                    try:
                        element = await page.query_selector(sel.strip())
                        if element and await element.is_visible():
                            # Clear field first
                            await element.click()
                            await element.fill('')
                            await asyncio.sleep(0.5)

                            # Fill with test value
                            await element.fill(value)
                            await asyncio.sleep(0.5)

                            # Trigger change event
                            await element.blur()
                            await asyncio.sleep(1)

                            filled_fields[field_name] = True
                            self.logger.info(f"Filled {field_name} with {value} using {sel}")
                            break
                    except Exception as e:
                        self.logger.debug(f"Could not fill {field_name} with {sel}: {e}")
                        continue

                if field_name not in filled_fields:
                    filled_fields[field_name] = False

            except Exception as e:
                self.logger.debug(f"Error filling {field_name}: {e}")
                filled_fields[field_name] = False

        return filled_fields

    async def _detect_dimension_fields(self, page: Page) -> Dict[str, Any]:
        """Detect what dimension fields are available without changing them"""
        domain = self.context.domain

        field_info = {}

        if 'expresszuschnitt' in domain:
            # ExpressZuschnitt.de specific selectors
            field_mappings = {
                'length': 'input.fl_but[data-key="x"]',
                'width': 'input.fl_but[data-key="y"]',
                'thickness': 'input.fl_but[data-key="z"]',
                'quantity': 'input.fl_but[data-but="b_swoodVar"]'
            }
        else:
            # Generic field patterns
            field_mappings = {
                'length': 'input[name*="length"], input[data-key="x"], #length',
                'width': 'input[name*="width"], input[data-key="y"], #width',
                'thickness': 'input[name*="thickness"], input[data-key="z"], #thickness',
                'quantity': 'input[name*="quantity"], .qty, #quantity'
            }

        for field_name, selector in field_mappings.items():
            try:
                # Try multiple selectors for generic patterns
                selectors = selector.split(', ') if ', ' in selector else [selector]

                for sel in selectors:
                    element = await page.query_selector(sel.strip())
                    if element and await element.is_visible():
                        # Get current value without changing it
                        current_value = await element.get_attribute('value') or ''
                        field_info[field_name] = {
                            'selector': sel.strip(),
                            'current_value': current_value,
                            'available': True
                        }
                        self.logger.info(f"Found {field_name} field with value: {current_value}")
                        break
                else:
                    field_info[field_name] = {'available': False}

            except Exception as e:
                self.logger.debug(f"Error detecting {field_name} field: {e}")
                field_info[field_name] = {'available': False}

        return field_info

    async def _add_to_cart(self, page: Page) -> bool:
        """Try to add the configured item to cart"""
        domain = self.context.domain

        if 'expresszuschnitt' in domain:
            # ExpressZuschnitt.de specific selectors
            cart_selectors = [
                'button:has-text("Zum Warenkorb")',
                'button[name="inWarenkorb"]',
                '.btn-cart',
                'button:has-text("In den Warenkorb")'
            ]
        else:
            # Generic cart button patterns
            cart_selectors = [
                '.add-to-cart',
                '.btn-cart',
                'button[name*="cart"]',
                'input[type="submit"][value*="cart"]',
                'button:has-text("Add to cart")',
                'button:has-text("Add to Cart")',
                '.single_add_to_cart_button',
                '.addtocart'
            ]

        for selector in cart_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    self.logger.info(f"Clicking add to cart: {selector}")
                    await element.click()
                    await asyncio.sleep(3)

                    await self._handle_post_cart_popups(page)

                    # Check if we were redirected or if cart was updated
                    current_url = page.url
                    if 'cart' in current_url.lower() or 'warenkorb' in current_url.lower():
                        self.logger.info("Successfully added to cart and redirected")
                        return True

                    # Check for cart indicators on page
                    cart_indicators = await page.query_selector_all('.cart-count, .cart-items, .basket-count')
                    if cart_indicators:
                        self.logger.info("Cart indicators found - item likely added")
                        return True

            except Exception as e:
                self.logger.debug(f"Could not click add to cart {selector}: {e}")
                continue

        self.logger.warning("Could not find or click any add to cart button")
        return False

    async def _navigate_to_cart_and_analyze(self, page: Page) -> Optional[Dict[str, Any]]:
        """Navigate to cart page and analyze pricing structure"""
        domain = self.context.domain

        # If we're not already on cart page, try to navigate
        current_url = page.url
        if not ('cart' in current_url.lower() or 'warenkorb' in current_url.lower()):

            if 'expresszuschnitt' in domain:
                # ExpressZuschnitt.de specific cart navigation
                cart_nav_selectors = [
                    '.btn-basket',
                    'a[href*="warenkorb"]',
                    '.cart-link',
                    '.basket-link'
                ]
            else:
                # Generic cart navigation
                cart_nav_selectors = [
                    '.cart-link',
                    'a[href*="cart"]',
                    '.basket-link',
                    'a[href*="basket"]',
                    '.mini-cart',
                    '#cart-link'
                ]

            cart_navigated = False
            for selector in cart_nav_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        self.logger.info(f"Navigating to cart via: {selector}")
                        await element.click()
                        await asyncio.sleep(3)
                        cart_navigated = True
                        break
                except Exception as e:
                    self.logger.debug(f"Could not navigate via {selector}: {e}")
                    continue

            if not cart_navigated:
                self.logger.warning("Could not navigate to cart page")
                return None

        # Analyze cart page pricing structure
        try:
            cart_analysis = await self._analyze_cart_pricing(page)
            return cart_analysis
        except Exception as e:
            self.logger.error(f"Error analyzing cart pricing: {e}")
            return None

    async def _analyze_cart_pricing(self, page: Page) -> Dict[str, Any]:
        """Analyze the cart page to find pricing elements and structure"""

        # Wait for cart page to load and ensure it's stable
        try:
            await page.wait_for_load_state('networkidle', timeout=10000)
        except:
            await asyncio.sleep(3)

        try:
            pricing_analysis = await page.evaluate("""
                () => {
                    const analysis = {
                        url: window.location.href,
                        pricing_elements: [],
                        cart_items: [],
                        total_elements: [],
                        shipping_elements: []
                    };

                    // Find individual item prices
                    const itemPriceSelectors = [
                        '.fl_itemPrice', '.item-price', '.product-price',
                        '.price_overall', '.einzelpreis', '.line-total'
                    ];

                    itemPriceSelectors.forEach(selector => {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach(el => {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                analysis.pricing_elements.push({
                                    selector: selector,
                                    text: el.textContent?.trim() || '',
                                    type: 'item_price',
                                    position: {x: rect.x, y: rect.y}
                                });
                            }
                        });
                    });

                    // Find shipping costs
                    const shippingSelectors = [
                        '.fl_shp', '.shipping-cost', '.delivery-cost',
                        '.versand', '.lieferkosten'
                    ];

                    shippingSelectors.forEach(selector => {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach(el => {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                // Also check for price in nearby elements
                                const priceEl = el.nextElementSibling?.querySelector('.price_overall') ||
                                              el.parentElement?.querySelector('.price_overall');

                                analysis.shipping_elements.push({
                                    selector: selector,
                                    text: el.textContent?.trim() || '',
                                    price_text: priceEl?.textContent?.trim() || '',
                                    type: 'shipping_cost'
                                });
                            }
                        });
                    });

                    // Find total prices
                    const totalSelectors = [
                        '.total-sum', '.gesamtsumme', '.grand-total',
                        '.price.total', '.total .price'
                    ];

                    totalSelectors.forEach(selector => {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach(el => {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                analysis.total_elements.push({
                                    selector: selector,
                                    text: el.textContent?.trim() || '',
                                    type: 'total_price'
                                });
                            }
                        });
                    });

                    return analysis;
                }
            """)

            # Generate updated selectors based on what we found
            updated_selectors = self._generate_updated_selectors_from_analysis(pricing_analysis)
            pricing_analysis['updated_selectors'] = updated_selectors

            self.logger.info(f"Cart analysis complete: {len(pricing_analysis['pricing_elements'])} price elements found")

            return pricing_analysis

        except Exception as e:
            self.logger.warning(f"Cart analysis failed with evaluation error: {e}")
            # Return minimal analysis structure if evaluation fails
            return {
                'url': page.url,
                'pricing_elements': [],
                'cart_items': [],
                'total_elements': [],
                'shipping_elements': [],
                'updated_selectors': {},
                'analysis_failed': True
            }

    def _generate_updated_selectors_from_analysis(self, cart_analysis: Dict[str, Any]) -> Dict[str, str]:
        """Generate updated selectors based on actual cart analysis"""
        selectors = {}

        # Find best shipping selector
        shipping_elements = cart_analysis.get('shipping_elements', [])
        if shipping_elements:
            # Prefer elements that have actual price text
            shipping_with_price = [el for el in shipping_elements if el.get('price_text')]
            if shipping_with_price:
                best_shipping = shipping_with_price[0]
                if best_shipping['price_text']:
                    # Create selector that targets the price element
                    selectors['shipping'] = f"{best_shipping['selector']} + .text-right .price_overall"
                else:
                    selectors['shipping'] = best_shipping['selector']
            else:
                selectors['shipping'] = shipping_elements[0]['selector']

        # Find best item price selector
        pricing_elements = cart_analysis.get('pricing_elements', [])
        if pricing_elements:
            # Prefer selectors that contain actual price text
            price_with_text = [el for el in pricing_elements if '€' in el.get('text', '') or '$' in el.get('text', '')]
            if price_with_text:
                selectors['item_price'] = price_with_text[0]['selector']
            else:
                selectors['item_price'] = pricing_elements[0]['selector']

        # Find best total selector
        total_elements = cart_analysis.get('total_elements', [])
        if total_elements:
            selectors['total'] = total_elements[0]['selector']

        return selectors

    async def _explore_cart_workflow(self, page: Page) -> Optional[Dict[str, Any]]:
        """Explore cart workflow and pricing with actual workflow execution"""
        try:
            self.logger.info("Exploring cart workflow with actual execution...")

            # First, try to configure the product with default values
            await self._execute_product_configuration(page)

            # Now look for "Add to Cart" buttons with German text
            cart_selectors = [
                # German "Add to Cart" variations
                'button:has-text("Zum Warenkorb")',
                'button:has-text("In den Warenkorb")',
                'button:has-text("Warenkorb")',
                '[title*="Warenkorb"]',
                '[alt*="Warenkorb"]',

                # Generic selectors
                '.btn-basket', '.cart-btn', '.add-to-cart',
                '[href*="cart"]', '[href*="warenkorb"]',
                'button[name*="warenkorb"]', 'input[name*="warenkorb"]',
                '.btn-cart', '.button-cart'
            ]

            # Try each selector to find and click the add to cart button
            for selector in cart_selectors:
                try:
                    self.logger.debug(f"Trying cart selector: {selector}")
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        self.logger.info(f"Found add to cart button: {selector}")

                        # Click the add to cart button
                        await asyncio.sleep(3)
                        await element.click()
                        await asyncio.sleep(3)  # Wait for any popup or redirect

                        # Handle any popups that appear after clicking
                        await self._handle_post_cart_popups(page)

                        # Check if we're now on cart page or need to navigate
                        current_url = page.url
                        if 'warenkorb' in current_url or 'cart' in current_url:
                            self.logger.info(f"Successfully reached cart page: {current_url}")
                        else:
                            # Try to navigate to cart
                            await self._navigate_to_cart_page(page)

                        return {
                            'cart_selector': selector,
                            'cart_workflow_detected': True,
                            'cart_button_clicked': True,
                            'final_url': page.url
                        }

                except Exception as e:
                    self.logger.debug(f"Could not use cart selector {selector}: {e}")
                    continue

            self.logger.warning("Could not find or click any add to cart button")
            return {
                'cart_workflow_detected': False,
                'error': 'No cart button found'
            }

        except Exception as e:
            self.logger.error(f"Error exploring cart workflow: {e}")
            return None

    async def _execute_product_configuration(self, page: Page):
        """Execute product configuration with default values"""
        try:
            self.logger.info("Configuring product with default values...")

            # Wait a bit more for the page to fully load
            await asyncio.sleep(3)

            # Try to click configuration button if it exists
            config_button_selectors = [
                '.btn-confi.fl_but', '.btn-confi', '[data-action="configure"]',
                'button:has-text("konfigurieren")', 'button:has-text("Konfigurieren")'
            ]

            for selector in config_button_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        self.logger.info(f"Clicking configuration button: {selector}")
                        await element.click()
                        await asyncio.sleep(2)
                        break
                except Exception:
                    continue

            # Fill in dimension fields with default values if they exist
            dimension_fields = [
                {'selector': 'input[data-key="x"]', 'value': '100', 'name': 'length'},
                {'selector': 'input[data-key="y"]', 'value': '80', 'name': 'width'},
                {'selector': 'input[data-key="z"]', 'value': '19', 'name': 'thickness'},
                {'selector': 'input[data-but="b_swoodVar"]', 'value': '1', 'name': 'quantity'}
            ]

            for field in dimension_fields:
                try:
                    element = await page.query_selector(field['selector'])
                    if element and await element.is_visible():
                        self.logger.info(f"Setting {field['name']} to {field['value']}")
                        await element.clear()
                        await element.fill(field['value'])
                        await asyncio.sleep(1)
                except Exception as e:
                    self.logger.debug(f"Could not set {field['name']}: {e}")

            # Wait a bit for any dynamic price updates
            await asyncio.sleep(2)

        except Exception as e:
            self.logger.debug(f"Error in product configuration: {e}")

    async def _handle_post_cart_popups(self, page: Page):
        """Handle popups that appear after clicking add to cart"""
        try:
            self.logger.info("Handling post-cart popups if any...")
            await asyncio.sleep(2)  # Wait for popup to appear

            # Look for common popup close/continue buttons
            popup_selectors = [
                '.modal .btn-primary', '.modal .btn-success',
                'button:has-text("Weiter")', 'button:has-text("Continue")',
                'button:has-text("OK")', 'button:has-text("Schließen")',
                '.popup .close', '.modal .close',
                '[data-dismiss="modal"]',
                'button:has-text("Zum Warenkorb")',
                'a:has-text("Zum Warenkorb")',
                'button:has-text("In den Warenkorb")',
                'button:has-text("Warenkorb")',
                '[title*="Warenkorb"]',
                '[alt*="Warenkorb"]',

                # Generic selectors
                '.btn-basket', '.cart-btn', '.add-to-cart',
                '[href*="cart"]', '[href*="warenkorb"]',
                'button[name*="warenkorb"]', 'input[name*="warenkorb"]',
                '.btn-cart', '.button-cart'
            ]

            for selector in popup_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        self.logger.info(f"Clicking popup button: {selector}")
                        await element.click()
                        await asyncio.sleep(1)
                        break
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Error handling post-cart popups: {e}")

    async def _navigate_to_cart_page(self, page: Page):
        """Navigate to cart page if not already there"""
        try:
            # Look for cart navigation links
            cart_nav_selectors = [
                '.btn-basket', '[href*="warenkorb"]', '[href*="cart"]',
                'a:has-text("Warenkorb")', 'a:has-text("Cart")',
                '.cart-icon', '.basket-icon'
            ]

            for selector in cart_nav_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        self.logger.info(f"Navigating to cart via: {selector}")
                        await element.click()
                        await asyncio.sleep(3)
                        return
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Error navigating to cart: {e}")
