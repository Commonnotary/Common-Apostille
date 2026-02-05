"""Lead segmentation service for classifying practice areas and regions."""

from typing import List, Dict, Tuple, Optional
import logging

from ..config import PRACTICE_AREA_KEYWORDS, REGIONS
from ..models.lead import Lead, Segment, Region

logger = logging.getLogger(__name__)


class LeadSegmenter:
    """
    Service for segmenting and classifying leads.

    Classifies leads by:
    - Practice area (Estate Planning, Probate, Elder Law, Family, Other)
    - Geographic region (DC, NoVA, SWVA, Other)
    """

    # Priority order for segment assignment (if multiple match)
    SEGMENT_PRIORITY = [
        Segment.ESTATE_PLANNING,  # Primary target
        Segment.PROBATE,
        Segment.ELDER_LAW,
        Segment.FAMILY,
        Segment.OTHER
    ]

    def __init__(self):
        # Build reverse lookup from keywords to segments
        self._keyword_to_segment: Dict[str, Segment] = {}
        for segment_key, keywords in PRACTICE_AREA_KEYWORDS.items():
            segment = Segment(segment_key)
            for keyword in keywords:
                self._keyword_to_segment[keyword.lower()] = segment

    def _score_segment(self, text: str, segment: Segment) -> Tuple[int, List[str]]:
        """
        Score how well text matches a segment.

        Returns (score, matched_keywords)
        """
        if not text:
            return 0, []

        text_lower = text.lower()
        segment_key = segment.value
        keywords = PRACTICE_AREA_KEYWORDS.get(segment_key, [])

        matched = []
        for keyword in keywords:
            if keyword.lower() in text_lower:
                matched.append(keyword)

        return len(matched), matched

    def classify_segment(self, lead: Lead) -> Tuple[Segment, float, List[str]]:
        """
        Classify a lead into a practice area segment.

        Uses practice_areas field primarily, then firm name, notes.

        Returns:
            Tuple of (segment, confidence_score, matched_keywords)
        """
        # Combine relevant text fields for analysis
        text_parts = []
        if lead.practice_areas:
            text_parts.append(lead.practice_areas)
        if lead.firm_name:
            text_parts.append(lead.firm_name)
        if lead.notes:
            text_parts.append(lead.notes)
        if lead.attorney_title:
            text_parts.append(lead.attorney_title)

        combined_text = ' '.join(text_parts)

        if not combined_text.strip():
            return Segment.OTHER, 0.0, []

        # Score each segment
        segment_scores: Dict[Segment, Tuple[int, List[str]]] = {}
        for segment in self.SEGMENT_PRIORITY:
            if segment != Segment.OTHER:
                score, matched = self._score_segment(combined_text, segment)
                segment_scores[segment] = (score, matched)

        # Find best matching segment
        best_segment = Segment.OTHER
        best_score = 0
        best_matched = []

        for segment in self.SEGMENT_PRIORITY:
            if segment in segment_scores:
                score, matched = segment_scores[segment]
                if score > best_score:
                    best_score = score
                    best_segment = segment
                    best_matched = matched

        # Calculate confidence (0.0 to 1.0)
        # More keyword matches = higher confidence
        if best_score == 0:
            confidence = 0.0
        elif best_score == 1:
            confidence = 0.5
        elif best_score == 2:
            confidence = 0.7
        else:
            confidence = min(0.9, 0.6 + (best_score * 0.1))

        return best_segment, confidence, best_matched

    def classify_region(self, lead: Lead) -> Tuple[Region, float]:
        """
        Classify a lead into a geographic region.

        Returns:
            Tuple of (region, confidence_score)
        """
        # Already have region set?
        if lead.region and lead.region != Region.OTHER:
            return lead.region, 0.9

        # Combine location fields
        location_text = ' '.join(filter(None, [
            lead.city,
            lead.state,
            lead.address,
            lead.zip_code
        ])).lower()

        if not location_text.strip():
            return Region.OTHER, 0.0

        # Check each region
        for region_code, region_info in REGIONS.items():
            for city in region_info["cities"]:
                if city.lower() in location_text:
                    return Region(region_code), 0.9

        # Check state-level
        if 'dc' in location_text or 'district of columbia' in location_text:
            return Region.DC, 0.7
        elif 'virginia' in location_text or ', va' in location_text:
            # Can't determine NoVA vs SWVA without city
            # Default to NoVA as it's the primary market
            return Region.NOVA, 0.5

        return Region.OTHER, 0.0

    def segment_lead(self, lead: Lead) -> Lead:
        """
        Classify and update a lead with segment and region.

        Modifies the lead in place and returns it.
        """
        # Classify practice area
        segment, segment_confidence, matched_keywords = self.classify_segment(lead)
        lead.segment = segment

        # Classify region
        region, region_confidence = self.classify_region(lead)
        lead.region = region

        # Update confidence score (average of both)
        original_confidence = lead.confidence_score or 0.5
        new_confidence = (segment_confidence + region_confidence) / 2
        lead.confidence_score = (original_confidence + new_confidence) / 2

        logger.debug(
            f"Segmented {lead.display_name}: "
            f"segment={segment.value} (conf={segment_confidence:.2f}, keywords={matched_keywords}), "
            f"region={region.value} (conf={region_confidence:.2f})"
        )

        return lead

    def segment_leads(self, leads: List[Lead]) -> List[Lead]:
        """Segment multiple leads."""
        for lead in leads:
            self.segment_lead(lead)
        return leads

    def get_segment_display_name(self, segment: Segment) -> str:
        """Get human-readable segment name."""
        mapping = {
            Segment.ESTATE_PLANNING: "Estate Planning",
            Segment.PROBATE: "Probate & Estate Administration",
            Segment.ELDER_LAW: "Elder Law",
            Segment.FAMILY: "Family Law",
            Segment.OTHER: "Other"
        }
        return mapping.get(segment, segment.value)

    def get_region_display_name(self, region: Region) -> str:
        """Get human-readable region name."""
        if region.value in REGIONS:
            return REGIONS[region.value]["name"]
        return "Other Region"

    def filter_by_segment(
        self,
        leads: List[Lead],
        segments: List[Segment]
    ) -> List[Lead]:
        """Filter leads by segment."""
        return [lead for lead in leads if lead.segment in segments]

    def filter_by_region(
        self,
        leads: List[Lead],
        regions: List[Region]
    ) -> List[Lead]:
        """Filter leads by region."""
        return [lead for lead in leads if lead.region in regions]

    def get_segment_stats(self, leads: List[Lead]) -> Dict[str, int]:
        """Get count of leads per segment."""
        stats = {segment.value: 0 for segment in Segment}
        for lead in leads:
            if lead.segment:
                stats[lead.segment.value] += 1
        return stats

    def get_region_stats(self, leads: List[Lead]) -> Dict[str, int]:
        """Get count of leads per region."""
        stats = {region.value: 0 for region in Region}
        for lead in leads:
            if lead.region:
                stats[lead.region.value] += 1
        return stats
