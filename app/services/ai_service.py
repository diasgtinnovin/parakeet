import openai
import random
import logging
import os
import re
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self, api_key=None, use_ai=True):
        self.api_key = api_key
        self.use_ai = use_ai
        self.client = None
        self.ai_available = False
        
        # Debug information
        logger.info(f"Initializing AIService with use_ai={use_ai}, api_key_provided={bool(api_key)}")
        
        # Check if we should use AI and validate the API key
        if not use_ai:
            logger.info("AI disabled via use_ai parameter")
        elif not api_key:
            logger.info("No API key provided")
        elif api_key == "your-openai-api-key":
            logger.info("Placeholder API key detected")
       # Around lines 28-51, change to:
        else:
            logger.info(f"Attempting to initialize OpenAI client with API key (length: {len(api_key)})")
            try:
                self.client = openai.OpenAI(api_key=api_key)
                self.ai_available = True
                logger.info("OpenAI client initialized successfully!")
                
            except Exception as e:
                logger.error(f"OpenAI client initialization failed: {e}")
                self.client = None
                self.ai_available = False
                logger.info("Falling back to template-only generation")
        
        # Load templates and configuration
        # Remove or comment out the line below:
        # self.ai_available = True
        
       
        # Load templates and configuration
        # self.ai_available = True
        self.templates = self._load_templates()
        self.placeholders = self._load_placeholders()
        self.ai_prompts = self._load_ai_prompts()
        self.config = self._load_configuration()
        
        # Configuration for mixing ratios
        if self.ai_available:
            # Use configured ratios when AI is available
            self.generation_ratios = {
                'pure_template': self.config.get('pure_template_ratio', 0.3),
                'template_ai_fill': self.config.get('template_ai_fill_ratio', 0.4),
                'ai_addon': self.config.get('ai_addon_ratio', 0.2),
                'ai_seeded': self.config.get('ai_seeded_ratio', 0.1)
            }
            logger.info("AI available - using hybrid generation ratios")
        else:
            # Use only template-based generation when AI is not available
            self.generation_ratios = {
                'pure_template': 1.0,
                'template_ai_fill': 0.0,
                'ai_addon': 0.0,
                'ai_seeded': 0.0
            }
            logger.info("AI not available - using 100% template generation")
        
        # Normalize ratios to ensure they sum to 1.0
        total = sum(self.generation_ratios.values())
        if total != 1.0:
            for key in self.generation_ratios:
                self.generation_ratios[key] /= total
            logger.info(f"Normalized generation ratios: {self.generation_ratios}")
    
    def _load_configuration(self) -> Dict[str, float]:
        """Load configuration from file"""
        config = {}
        config_file = Path(__file__).parent.parent / 'templates' / 'generation_config.txt'
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            key, value = parts
                            # Try to convert to appropriate type
                            try:
                                if '.' in value:
                                    config[key] = float(value)
                                elif value.lower() in ['true', 'false']:
                                    config[key] = value.lower() == 'true'
                                else:
                                    config[key] = int(value) if value.isdigit() else value
                            except ValueError:
                                config[key] = value
        except FileNotFoundError:
            logger.warning("Configuration file not found, using defaults")
        
        return config
    
    def _load_templates(self) -> Dict[str, List[Dict]]:
        """Load email templates from file"""
        templates = {}
        templates_file = Path(__file__).parent.parent / 'templates' / 'email_templates.txt'
        
        try:
            with open(templates_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split('|')
                        if len(parts) == 3:
                            template_type, subject, content = parts
                            if template_type not in templates:
                                templates[template_type] = []
                            templates[template_type].append({
                                'subject': subject,
                                'content': content
                            })
            logger.info(f"Loaded {sum(len(v) for v in templates.values())} templates across {len(templates)} categories")
        except FileNotFoundError:
            logger.warning("Templates file not found, using fallback templates")
            # Fallback templates
            templates = {
                'general': [
                    {'subject': 'Hey there!', 'content': '{greeting} {casual_phrase} Hope you\'re doing well! {closing}'},
                    {'subject': 'Just saying hi', 'content': '{greeting} Just wanted to reach out and say hello. {closing}'}
                ]
            }
        
        return templates
    
    def _load_placeholders(self) -> Dict[str, List[str]]:
        """Load placeholder values from file"""
        placeholders = {}
        placeholders_file = Path(__file__).parent.parent / 'templates' / 'placeholders.txt'
        
        try:
            with open(placeholders_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            placeholder_type, value = parts
                            if placeholder_type not in placeholders:
                                placeholders[placeholder_type] = []
                            placeholders[placeholder_type].append(value)
            logger.info(f"Loaded placeholders for {len(placeholders)} categories")
        except FileNotFoundError:
            logger.warning("Placeholders file not found, using fallback placeholders")
            # Fallback placeholders
            placeholders = {
                'greeting': ['Hey there!', 'Hi!', 'Hello!'],
                'casual_phrase': ['Hope all is well.', 'How have you been?'],
                'closing': ['Take care!', 'Talk soon!', 'Best wishes!']
            }
        
        return placeholders
    
    def _load_ai_prompts(self) -> Dict[str, str]:
        """Load AI prompts from file"""
        prompts = {}
        prompts_file = Path(__file__).parent.parent / 'templates' / 'ai_prompts.txt'
        
        try:
            with open(prompts_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split('|', 1)
                        if len(parts) == 2:
                            prompt_type, prompt_content = parts
                            prompts[prompt_type] = prompt_content
            logger.info(f"Loaded {len(prompts)} AI prompts")
        except FileNotFoundError:
            logger.warning("AI prompts file not found, using fallback prompts")
            # Fallback prompts
            prompts = {
                'ai_seeded': 'Write a short, casual email (2-3 sentences). Keep it friendly and natural.',
                'subject_generation': 'Generate a casual email subject line for this content: "{content}". Keep it short and friendly.'
            }
        
        return prompts
    
    def _fill_template_placeholders(self, template: str, use_ai: bool = False) -> str:
        """Fill template placeholders with values"""
        filled_template = template
        
        # Find all placeholders in the template
        placeholders_in_template = re.findall(r'\{(\w+)\}', template)
        
        for placeholder in placeholders_in_template:
            if use_ai and self.ai_available:
                # Use AI to generate placeholder value
                value = self._ai_fill_placeholder(placeholder)
            else:
                # Use random value from placeholders
                if placeholder in self.placeholders:
                    value = random.choice(self.placeholders[placeholder])
                else:
                    value = f"[{placeholder}]"  # Fallback if placeholder not found
            
            filled_template = filled_template.replace(f'{{{placeholder}}}', value)
        
        return filled_template
    
    def _ai_fill_placeholder(self, placeholder_type: str) -> str:
        """Use AI to fill a single placeholder"""
        if not self.ai_available:
            # Fallback to random placeholder
            if placeholder_type in self.placeholders:
                return random.choice(self.placeholders[placeholder_type])
            return f"[{placeholder_type}]"
        
        try:
            examples = self.placeholders.get(placeholder_type, [])[:3]  # Get first 3 examples
            examples_str = ", ".join(examples) if examples else "friendly, casual phrases"
            
            prompt = self.ai_prompts.get('fill_placeholder', '').format(
                placeholder_type=placeholder_type,
                examples=examples_str
            )
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.config.get('max_subject_tokens', 30),
                temperature=self.config.get('ai_temperature', 0.8)
            )
            
            return response.choices[0].message.content.strip().strip('"').strip("'")
        
        except Exception as e:
            logger.error(f"AI placeholder filling failed: {e}")
            # Fallback to random placeholder
            if placeholder_type in self.placeholders:
                return random.choice(self.placeholders[placeholder_type])
            return f"[{placeholder_type}]"
    
    def _generate_ai_addon(self, base_content: str) -> str:
        """Generate AI addon sentences to append to base content"""
        if not self.ai_available:
            return base_content
        
        try:
            prompt = self.ai_prompts.get('addon_sentence', '').format(base_content=base_content)
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=self.config.get('ai_temperature', 0.8)
            )
            
            addon = response.choices[0].message.content.strip()
            return f"{base_content} {addon}"
        
        except Exception as e:
            logger.error(f"AI addon generation failed: {e}")
            return base_content
    
    def _generate_ai_seeded_content(self, theme: str = "friendly greeting") -> Dict[str, str]:
        """Generate fully AI-seeded content with human-like characteristics"""
        if not self.ai_available:
            # Fallback to template
            return self._generate_pure_template_content()
        
        try:
            # Enhanced themes for more human-like content
            enhanced_themes = [
                "casual friend check-in with slight imperfections",
                "quick hello with regional slang",
                "friendly greeting with natural filler words",
                "conversational check-in like texting a buddy",
                "warm greeting with mild grammatical casualness"
            ]
            
            # Use enhanced theme or provided theme
            if theme == "friendly greeting":
                theme = random.choice(enhanced_themes)
            
            prompt = self.ai_prompts.get('ai_seeded', '').format(theme=theme)
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.config.get('max_content_tokens', 100),
                temperature=self.config.get('ai_temperature', 0.8)
            )
            
            content = response.choices[0].message.content.strip()
            
            # Apply post-processing for more human-like content
            content = self._humanize_content(content)
            
            # Generate subject
            subject = self._generate_ai_subject(content)
            
            return {'subject': subject, 'content': content}
        
        except Exception as e:
            logger.error(f"AI seeded generation failed: {e}")
            # Fallback to template
            return self._generate_pure_template_content()
    
    def _generate_ai_subject(self, content: str) -> str:
        """Generate AI subject line for content"""
        if not self.ai_available:
            # Fallback subjects
            fallback_subjects = ['Hey there!', 'Quick hello', 'Just saying hi', 'Hope you\'re well']
            return random.choice(fallback_subjects)
        
        try:
            prompt = self.ai_prompts.get('subject_generation', '').format(content=content)
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.config.get('max_subject_tokens', 20),
                temperature=self.config.get('ai_temperature', 0.7)
            )
            
            return response.choices[0].message.content.strip().strip('"').strip("'")
        
        except Exception as e:
            logger.error(f"AI subject generation failed: {e}")
            # Fallback subjects
            fallback_subjects = ['Hey there!', 'Quick hello', 'Just saying hi', 'Hope you\'re well']
            return random.choice(fallback_subjects)
    
    def _generate_pure_template_content(self) -> Dict[str, str]:
        """Generate content using pure templates"""
        template_types = list(self.templates.keys())
        if not template_types:
            return self._fallback_content()
        
        template_type = random.choice(template_types)
        template = random.choice(self.templates[template_type])
        
        subject = self._fill_template_placeholders(template['subject'], use_ai=False)
        content = self._fill_template_placeholders(template['content'], use_ai=False)
        
        return {
            'subject': subject,
            'content': content,
            'generation_type': 'pure_template',
            'template_type': template_type
        }
    
    def _humanize_content(self, content: str) -> str:
        """Apply post-processing to make content more human-like"""
        if not content:
            return content
        
        # Occasionally add natural imperfections (configurable rate)
        if self.config.get('enable_intentional_imperfections', True) and random.random() < self.config.get('imperfection_rate', 0.05):
            imperfections = [
                lambda s: s.replace("you are", "your") if "you are" in s else s,
                lambda s: s.replace("it is", "its") if "it is" in s and random.random() < 0.3 else s,
                lambda s: s.replace("a lot", "alot") if "a lot" in s and random.random() < 0.2 else s,
            ]
            for imperfection in imperfections:
                if random.random() < 0.3:  # Apply each imperfection with 30% chance
                    content = imperfection(content)
        
        # Add natural contractions (configurable rate)
        if self.config.get('enable_contractions', True) and random.random() < self.config.get('contraction_rate', 0.6):
            contractions = {
                "I am": "I'm",
                "you are": "you're", 
                "it is": "it's",
                "that is": "that's",
                "we are": "we're",
                "they are": "they're",
                "cannot": "can't",
                "do not": "don't",
                "will not": "won't",
                "should not": "shouldn't",
                "would not": "wouldn't"
            }
            for formal, casual in contractions.items():
                if formal in content and random.random() < 0.7:
                    content = content.replace(formal, casual)
        
        # Occasionally add natural filler words (configurable rate)
        if self.config.get('enable_filler_words', True) and random.random() < self.config.get('filler_word_rate', 0.15):
            filler_words = ["anyway", "by the way", "oh", "so", "well", "actually"]
            filler = random.choice(filler_words)
            
            # Insert filler word at natural positions
            sentences = content.split('. ')
            if len(sentences) > 1:
                insert_pos = random.randint(1, len(sentences) - 1)
                sentences[insert_pos] = f"{filler.capitalize()}, {sentences[insert_pos].lower()}"
                content = '. '.join(sentences)
        
        # Occasionally add subtle emotional expressions (configurable rate)
        if self.config.get('enable_emotional_touches', True) and random.random() < self.config.get('emotional_touch_rate', 0.1):
            emotions = [":)", "😊", "🙂", "lol", "haha"]
            if not any(emotion in content for emotion in emotions):
                content = content.rstrip('.!') + f" {random.choice(emotions)}"
        
        return content
    
    def _add_timing_context(self, content: str) -> str:
        """Add time-based context to make emails feel more natural"""
        import datetime
        now = datetime.datetime.now()
        
        # Morning context (6 AM - 12 PM)
        if 6 <= now.hour < 12:
            morning_additions = [
                "Hope your morning's off to a good start.",
                "Early bird today!",
                "Coffee hitting the spot?",
                "Getting an early start today."
            ]
            if self.config.get('enable_timing_context', True) and random.random() < self.config.get('timing_context_rate', 0.3):
                return content + " " + random.choice(morning_additions)
        
        # Afternoon context (12 PM - 6 PM)
        elif 12 <= now.hour < 18:
            afternoon_additions = [
                "Hope your afternoon's going well.",
                "Midday check-in!",
                "How's the day treating you?",
                "Afternoon slump hitting yet?"
            ]
            if self.config.get('enable_timing_context', True) and random.random() < self.config.get('timing_context_rate', 0.3):
                return content + " " + random.choice(afternoon_additions)
        
        # Evening context (6 PM - 10 PM)
        elif 18 <= now.hour < 22:
            evening_additions = [
                "Hope you're winding down well.",
                "End of day vibes.",
                "How was your day?",
                "Ready for some downtime?"
            ]
            if self.config.get('enable_timing_context', True) and random.random() < self.config.get('timing_context_rate', 0.3):
                return content + " " + random.choice(evening_additions)
        
        return content

    def _validate_content(self, content: str) -> bool:
        """Post-process and validate content for spam patterns"""
        if not self.config.get('enable_spam_filtering', True):
            return True
        
        # Basic validation rules
        spam_patterns = [
            r'!!!+',  # Multiple exclamation marks
            r'FREE\s+\w+',  # Free + word
            r'URGENT\s+\w+',  # Urgent + word
            r'LIMITED\s+TIME',  # Limited time
            r'ACT\s+NOW',  # Act now
            r'CLICK\s+HERE',  # Click here
            r'\$\d+',  # Money amounts
            r'www\.',  # URLs
            r'http[s]?://',  # URLs
            r'BUY\s+NOW',  # Buy now
            r'SPECIAL\s+OFFER',  # Special offer
        ]
        
        content_upper = content.upper()
        for pattern in spam_patterns:
            if re.search(pattern, content_upper):
                logger.warning(f"Content flagged for spam pattern: {pattern}")
                return False
        
        # Check for excessive repetition
        words = content.lower().split()
        if len(words) > 3:
            word_freq = {}
            for word in words:
                if len(word) > 2:  # Only check meaningful words
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # Flag if any word appears more than configured threshold
            max_repetition_ratio = self.config.get('max_word_repetition_ratio', 0.3)
            if word_freq:
                max_freq = max(word_freq.values())
                if max_freq / len(words) > max_repetition_ratio:
                    logger.warning("Content flagged for excessive word repetition")
                    return False
        
        return True
    
    def _fallback_content(self) -> Dict[str, str]:
        """Generate fallback content when all else fails"""
        fallback_contents = [
            "Hey! Hope you're doing well. Just wanted to reach out and say hello. Take care!",
            "Hi there! How have you been? Just wanted to touch base and see how things are going. Talk soon!",
            "Hello! Hope everything is going well with you. Have a great day!",
            "Hey there! Just wanted to drop you a quick line. Hope you're having a great week. Best wishes!"
        ]
        
        fallback_subjects = ["Hello there!", "Just saying hi", "Hope you're doing well", "Quick hello"]
        
        return {
            'subject': random.choice(fallback_subjects),
            'content': random.choice(fallback_contents),
            'generation_type': 'fallback',
            'template_type': 'general'
        }
    
    def generate_email_content(self, email_type: str = "general") -> Dict[str, str]:
        """Generate human-like email content using hybrid approach"""
        try:
            # Determine generation method based on ratios
            rand_val = random.random()
            cumulative = 0
            
            generation_method = 'pure_template'  # Default
            for method, ratio in self.generation_ratios.items():
                cumulative += ratio
                if rand_val <= cumulative:
                    generation_method = method
                    break
            
            logger.info(f"Using generation method: {generation_method} (AI available: {self.ai_available})")
            
            # Generate content based on selected method
            if generation_method == 'pure_template':
                result = self._generate_pure_template_content()
            
            elif generation_method == 'template_ai_fill':
                if not self.ai_available:
                    logger.info("AI not available, falling back to pure template")
                    result = self._generate_pure_template_content()
                    result['generation_type'] = 'pure_template_fallback'
                else:
                    template_types = list(self.templates.keys())
                    template_type = random.choice(template_types) if template_types else 'general'
                    
                    # Filter by email_type if available
                    if email_type in self.templates:
                        template_type = email_type
                    
                    available_templates = self.templates.get(template_type, [{'subject': 'Hi!', 'content': '{greeting} {closing}'}])
                    template = random.choice(available_templates)
                    
                    subject = self._fill_template_placeholders(template['subject'], use_ai=True)
                    content = self._fill_template_placeholders(template['content'], use_ai=True)
                    
                    # Apply humanization to AI-filled templates
                    content = self._humanize_content(content)
                    
                    result = {
                        'subject': subject,
                        'content': content,
                        'generation_type': 'template_ai_fill',
                        'template_type': template_type
                    }
            
            elif generation_method == 'ai_addon':
                if not self.ai_available:
                    logger.info("AI not available, falling back to pure template")
                    result = self._generate_pure_template_content()
                    result['generation_type'] = 'pure_template_fallback'
                else:
                    # Start with template, add AI content
                    base_result = self._generate_pure_template_content()
                    enhanced_content = self._generate_ai_addon(base_result['content'])
                    
                    result = {
                        'subject': base_result['subject'],
                        'content': enhanced_content,
                        'generation_type': 'ai_addon',
                        'template_type': base_result.get('template_type', 'general')
                    }
            
            elif generation_method == 'ai_seeded':
                if not self.ai_available:
                    logger.info("AI not available, falling back to pure template")
                    result = self._generate_pure_template_content()
                    result['generation_type'] = 'pure_template_fallback'
                else:
                    themes = [
                        'friendly greeting', 'casual check-in', 'quick hello', 
                        'thinking of you', 'hope you\'re well', 'random message',
                        'just saying hi', 'checking in', 'long time no talk',
                        'how have you been', 'hope all is good'
                    ]
                    theme = random.choice(themes)
                    ai_result = self._generate_ai_seeded_content(theme)
                    
                    # Apply timing context to make it more natural
                    enhanced_content = self._add_timing_context(ai_result['content'])
                    
                    result = {
                        'subject': ai_result['subject'],
                        'content': enhanced_content,
                        'generation_type': 'ai_seeded',
                        'template_type': 'ai_generated'
                    }
            
            else:
                result = self._generate_pure_template_content()
            
            # Validate content
            if not self._validate_content(result['content']) or not self._validate_content(result['subject']):
                logger.warning("Generated content failed validation, using fallback")
                result = self._fallback_content()
            
            # Ensure we have the required fields
            if 'generation_type' not in result:
                result['generation_type'] = generation_method
            if 'template_type' not in result:
                result['template_type'] = email_type
            
            # Legacy compatibility - ensure 'type' field exists
            result['type'] = result.get('template_type', email_type)
            
            logger.info(f"Generated email using {result['generation_type']} method, type: {result['template_type']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Email content generation failed: {e}")
            return self._fallback_content()
    
    def get_generation_stats(self) -> Dict[str, float]:
        """Return current generation method ratios for monitoring"""
        return self.generation_ratios.copy()
    
    def update_generation_ratios(self, new_ratios: Dict[str, float]) -> bool:
        """Update generation ratios dynamically"""
        if not self.ai_available:
            logger.warning("Cannot update ratios when AI is not available - forcing template-only mode")
            return False
        
        try:
            # Validate ratios sum to 1.0
            total = sum(new_ratios.values())
            if abs(total - 1.0) > 0.001:  # Allow small floating point errors
                logger.error(f"Generation ratios must sum to 1.0, got {total}")
                return False
            
            # Validate all required methods are present
            required_methods = {'pure_template', 'template_ai_fill', 'ai_addon', 'ai_seeded'}
            if set(new_ratios.keys()) != required_methods:
                logger.error(f"Missing required generation methods: {required_methods - set(new_ratios.keys())}")
                return False
            
            self.generation_ratios = new_ratios.copy()
            logger.info(f"Updated generation ratios: {self.generation_ratios}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update generation ratios: {e}")
            return False
    
    def get_ai_status(self) -> Dict[str, any]:
        """Get detailed AI service status"""
        return {
            'ai_available': self.ai_available,
            'client_initialized': self.client is not None,
            'use_ai_setting': self.use_ai,
            'api_key_provided': bool(self.api_key and self.api_key != "your-openai-api-key"),
            'generation_ratios': self.generation_ratios.copy(),
            'templates_loaded': len(self.templates),
            'placeholder_categories': len(self.placeholders),
            'ai_prompts_loaded': len(self.ai_prompts)
        }
