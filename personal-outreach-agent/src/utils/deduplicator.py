"""Intelligent lead deduplication."""

import re
from typing import List, Optional, Tuple
from difflib import SequenceMatcher
import logging

from ..models.lead import Lead

logger = logging.getLogger(__name__)


class LeadDeduplicator:
    """
    Intelligent deduplication of leads based on multiple criteria.

    Handles:
    - Same firm with multiple website pages
    - Different spellings/formats of firm names
    - Same attorney at different listings
    - Email/phone matching
    """

    # Threshold for fuzzy name matching (0.0 to 1.0)
    NAME_SIMILARITY_THRESHOLD = 0.85

    # Common suffixes to normalize in firm names
    FIRM_SUFFIXES = [
        r'\s+(llp|llc|pllc|pc|p\.c\.|p\.l\.l\.c\.|l\.l\.p\.|inc|incorporated|pa|p\.a\.)$',
        r'\s+(law\s+(firm|office|offices|group|practice|center))$',
        r'\s+(attorney|attorneys|lawyer|lawyers)\s*(at\s+law)?$',
        r'\s+(&|and)\s+(associates|assoc)$',
    ]

    # Words to remove for comparison
    NOISE_WORDS = ['the', 'a', 'an', 'of', 'at']

    def __init__(self, existing_leads: Optional[List[Lead]] = None):
        """
        Initialize with optional list of existing leads to check against.
        """
        self.existing_leads = existing_leads or []
        self._email_index = self._build_email_index()
        self._phone_index = self._build_phone_index()
        self._firm_index = self._build_firm_index()

    def _build_email_index(self) -> dict:
        """Build index of normalized emails to leads."""
        index = {}
        for lead in self.existing_leads:
            if lead.attorney_email:
                normalized = self._normalize_email(lead.attorney_email)
                if normalized:
                    index[normalized] = lead
        return index

    def _build_phone_index(self) -> dict:
        """Build index of normalized phones to leads."""
        index = {}
        for lead in self.existing_leads:
            if lead.attorney_phone:
                normalized = self._normalize_phone(lead.attorney_phone)
                if normalized:
                    index[normalized] = lead
        return index

    def _build_firm_index(self) -> dict:
        """Build index of normalized firm names to leads."""
        index = {}
        for lead in self.existing_leads:
            if lead.firm_name:
                normalized = self._normalize_firm_name(lead.firm_name)
                if normalized not in index:
                    index[normalized] = []
                index[normalized].append(lead)
        return index

    @staticmethod
    def _normalize_email(email: str) -> Optional[str]:
        """Normalize email for comparison."""
        if not email:
            return None
        return email.lower().strip()

    @staticmethod
    def _normalize_phone(phone: str) -> Optional[str]:
        """Normalize phone for comparison (digits only)."""
        if not phone:
            return None
        # Keep only digits
        digits = re.sub(r'\D', '', phone)
        # Handle common US phone formats
        if len(digits) == 11 and digits.startswith('1'):
            digits = digits[1:]  # Remove leading 1
        if len(digits) == 10:
            return digits
        return None if len(digits) < 7 else digits

    @classmethod
    def _normalize_firm_name(cls, name: str) -> str:
        """Normalize firm name for comparison."""
        if not name:
            return ""

        normalized = name.lower().strip()

        # Remove common suffixes
        for pattern in cls.FIRM_SUFFIXES:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)

        # Remove noise words
        words = normalized.split()
        words = [w for w in words if w not in cls.NOISE_WORDS]
        normalized = ' '.join(words)

        # Remove extra whitespace and punctuation
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    @staticmethod
    def _normalize_person_name(name: str) -> str:
        """Normalize person name for comparison."""
        if not name:
            return ""

        normalized = name.lower().strip()

        # Remove common titles and suffixes
        titles = r'\b(mr|mrs|ms|dr|esq|jr|sr|ii|iii|iv)\b\.?'
        normalized = re.sub(titles, '', normalized, flags=re.IGNORECASE)

        # Remove extra whitespace and punctuation
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    @staticmethod
    def _similarity(s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings."""
        if not s1 or not s2:
            return 0.0
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

    def is_duplicate(self, new_lead: Lead) -> Tuple[bool, Optional[Lead], str]:
        """
        Check if a lead is a duplicate of an existing lead.

        Returns:
            Tuple of (is_duplicate, matching_lead, reason)
        """
        # Check 1: Exact email match
        if new_lead.attorney_email:
            normalized_email = self._normalize_email(new_lead.attorney_email)
            if normalized_email in self._email_index:
                return (True, self._email_index[normalized_email], "email_match")

        # Check 2: Phone match
        if new_lead.attorney_phone:
            normalized_phone = self._normalize_phone(new_lead.attorney_phone)
            if normalized_phone and normalized_phone in self._phone_index:
                return (True, self._phone_index[normalized_phone], "phone_match")

        # Check 3: Firm name + attorney name match
        if new_lead.firm_name:
            normalized_firm = self._normalize_firm_name(new_lead.firm_name)

            # Check exact firm name match
            if normalized_firm in self._firm_index:
                for existing in self._firm_index[normalized_firm]:
                    # If same firm and same attorney (or no attorney specified)
                    if new_lead.attorney_name and existing.attorney_name:
                        name_sim = self._similarity(
                            self._normalize_person_name(new_lead.attorney_name),
                            self._normalize_person_name(existing.attorney_name)
                        )
                        if name_sim >= self.NAME_SIMILARITY_THRESHOLD:
                            return (True, existing, "firm_and_attorney_match")
                    elif not new_lead.attorney_name or not existing.attorney_name:
                        # Same firm, but no attorney name to compare
                        # Could be same listing
                        return (True, existing, "firm_match")

            # Check fuzzy firm name match
            for norm_firm, leads in self._firm_index.items():
                firm_sim = self._similarity(normalized_firm, norm_firm)
                if firm_sim >= self.NAME_SIMILARITY_THRESHOLD:
                    for existing in leads:
                        if new_lead.attorney_name and existing.attorney_name:
                            name_sim = self._similarity(
                                self._normalize_person_name(new_lead.attorney_name),
                                self._normalize_person_name(existing.attorney_name)
                            )
                            if name_sim >= self.NAME_SIMILARITY_THRESHOLD:
                                return (True, existing, "fuzzy_firm_and_attorney_match")

        # Check 4: Website match (same firm website)
        if new_lead.firm_website:
            normalized_website = new_lead.firm_website.lower().rstrip('/')
            for existing in self.existing_leads:
                if existing.firm_website:
                    existing_website = existing.firm_website.lower().rstrip('/')
                    if normalized_website == existing_website:
                        # Same website - check if same attorney
                        if new_lead.attorney_name and existing.attorney_name:
                            name_sim = self._similarity(
                                self._normalize_person_name(new_lead.attorney_name),
                                self._normalize_person_name(existing.attorney_name)
                            )
                            if name_sim >= self.NAME_SIMILARITY_THRESHOLD:
                                return (True, existing, "website_and_attorney_match")
                        elif not new_lead.attorney_name:
                            return (True, existing, "website_match")

        return (False, None, "")

    def add_lead(self, lead: Lead):
        """Add a lead to the deduplicator's index."""
        self.existing_leads.append(lead)

        # Update indexes
        if lead.attorney_email:
            normalized = self._normalize_email(lead.attorney_email)
            if normalized:
                self._email_index[normalized] = lead

        if lead.attorney_phone:
            normalized = self._normalize_phone(lead.attorney_phone)
            if normalized:
                self._phone_index[normalized] = lead

        if lead.firm_name:
            normalized = self._normalize_firm_name(lead.firm_name)
            if normalized not in self._firm_index:
                self._firm_index[normalized] = []
            self._firm_index[normalized].append(lead)

    def deduplicate_list(self, leads: List[Lead]) -> Tuple[List[Lead], List[Tuple[Lead, Lead, str]]]:
        """
        Deduplicate a list of new leads against existing leads and each other.

        Returns:
            Tuple of (unique_leads, duplicates_with_matches)
            where duplicates_with_matches is a list of (duplicate, matched_original, reason)
        """
        unique = []
        duplicates = []

        for lead in leads:
            is_dup, matched, reason = self.is_duplicate(lead)
            if is_dup:
                duplicates.append((lead, matched, reason))
                logger.debug(f"Duplicate found: {lead.display_name} matches {matched.display_name} ({reason})")
            else:
                unique.append(lead)
                self.add_lead(lead)  # Add to index for checking subsequent leads

        logger.info(f"Deduplication: {len(unique)} unique, {len(duplicates)} duplicates from {len(leads)} total")
        return unique, duplicates
