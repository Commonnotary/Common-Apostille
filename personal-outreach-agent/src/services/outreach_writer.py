"""Outreach email writer service."""

from typing import List, Optional, Tuple
from datetime import datetime
import logging
import random

from ..config import get_settings, CORE_SERVICES
from ..models.lead import Lead, Segment
from ..models.outreach import OutreachMessage, MessageVariant, MessageStatus

logger = logging.getLogger(__name__)


class OutreachWriter:
    """
    Service for generating personalized outreach emails.

    Creates three variants per lead:
    1. Intro (first contact)
    2. Follow-up #1 (3-5 business days later)
    3. Follow-up #2 (7-10 days later, polite close-the-loop)

    Tone: Partner-oriented, not salesy. Short, warm, credible.
    """

    def __init__(self):
        self.settings = get_settings()

    def _get_greeting(self, lead: Lead) -> str:
        """Get appropriate greeting based on available info."""
        if lead.attorney_name:
            # Extract first name or use full name
            name_parts = lead.attorney_name.strip().split()
            if len(name_parts) >= 2:
                # Use title + last name for more formal tone
                last_name = name_parts[-1]
                # Check for common suffixes
                if last_name.lower() in ['jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv', 'esq', 'esq.']:
                    last_name = name_parts[-2] if len(name_parts) > 2 else name_parts[0]
                return f"Dear {last_name.title()} Law Office"
            return f"Dear {lead.attorney_name}"
        return f"Dear {lead.firm_name} Team"

    def _get_service_mention(self, lead: Lead) -> str:
        """Get a brief, relevant service mention based on lead segment."""
        # Core services to mention (not loan signing unless relevant)
        notary = CORE_SERVICES["notarization"]["short"]
        apostille = CORE_SERVICES["apostille"]["short"]

        # Customize based on segment
        if lead.segment == Segment.ESTATE_PLANNING:
            return f"mobile notarization for estate documents (trusts, POAs, wills) and apostille facilitation"
        elif lead.segment == Segment.PROBATE:
            return f"notarization for estate administration documents and apostille services"
        elif lead.segment == Segment.ELDER_LAW:
            return f"mobile notarization (including bedside visits at homes and facilities) and apostilles"
        elif lead.segment == Segment.FAMILY:
            return f"notarization for family law documents and apostille facilitation"
        else:
            return f"{notary} and {apostille}"

    def _get_cta_variant(self, variant: MessageVariant) -> str:
        """Get call-to-action based on message variant."""
        ctas = {
            MessageVariant.INTRO: [
                "Would a brief 10-minute call be helpful to see if there's a fit?",
                "Worth a quick call to discuss how I might help your clients?",
                "Would you be open to a short conversation about how I could support your practice?",
            ],
            MessageVariant.FOLLOWUP_1: [
                "Would it help to schedule a quick call this week?",
                "Happy to stop by your office briefly if that's easier.",
                "Let me know if a 10-minute call would be useful.",
            ],
            MessageVariant.FOLLOWUP_2: [
                "If now isn't the right time, no problem at all. I'll circle back in a few months.",
                "If this isn't a fit right now, I understand. I'll keep your firm in mind.",
                "Just wanted to close the loop. If timing isn't right, I'll check back later.",
            ]
        }
        return random.choice(ctas.get(variant, ctas[MessageVariant.INTRO]))

    def _get_subject_line(self, lead: Lead, variant: MessageVariant) -> str:
        """Generate subject line for email."""
        # Use firm name or attorney name for personalization
        name_for_subject = lead.attorney_name or lead.firm_name

        subjects = {
            MessageVariant.INTRO: [
                f"Mobile notary partner for {lead.firm_name}?",
                f"Estate document notarization - {lead.city or 'local'} notary",
                f"Quick intro: Notary services for estate planning firms",
                f"Supporting {lead.city or 'area'} estate attorneys with notarization",
            ],
            MessageVariant.FOLLOWUP_1: [
                f"Following up: Notary partnership",
                f"Re: Mobile notary services for your clients",
                f"Quick follow-up from Common Notary Apostille",
            ],
            MessageVariant.FOLLOWUP_2: [
                f"Last note: Notary services",
                f"Closing the loop",
                f"One last note from Common Notary Apostille",
            ]
        }
        return random.choice(subjects.get(variant, subjects[MessageVariant.INTRO]))

    def generate_intro_email(self, lead: Lead) -> Tuple[str, str]:
        """
        Generate the initial outreach email.

        Returns (subject, body)
        """
        greeting = self._get_greeting(lead)
        services = self._get_service_mention(lead)
        cta = self._get_cta_variant(MessageVariant.INTRO)

        # Build personalized opening
        if lead.personalization_snippet:
            opener = lead.personalization_snippet
        else:
            # Fallback opener
            if lead.segment == Segment.ESTATE_PLANNING:
                opener = "I know estate planning attorneys often need reliable notarization for document execution."
            elif lead.segment == Segment.PROBATE:
                opener = "I understand probate and estate administration work requires timely document notarization."
            elif lead.segment == Segment.ELDER_LAW:
                opener = "I know elder law practices often need flexible notarization, including at clients' homes or facilities."
            else:
                opener = "I wanted to reach out to introduce myself."

        # Location mention
        location = ""
        if lead.city:
            location = f"I'm based in the DC/NoVA area and regularly work with attorneys in {lead.city}. "

        body = f"""{greeting},

{opener}

{location}I offer {services}. My approach is to be a reliable partner for your practice - available when you need me, professional with your clients, and easy to work with.

{cta}

Best regards,
{self.settings.contact_name}
{self.settings.business_name}
{self.settings.business_phone}
{self.settings.business_email}"""

        subject = self._get_subject_line(lead, MessageVariant.INTRO)
        return subject, body.strip()

    def generate_followup1_email(self, lead: Lead) -> Tuple[str, str]:
        """
        Generate the first follow-up email (3-5 days after intro).

        Shorter, references the first email.
        Returns (subject, body)
        """
        greeting = self._get_greeting(lead)
        cta = self._get_cta_variant(MessageVariant.FOLLOWUP_1)

        # Keep it brief
        body = f"""{greeting},

I wanted to follow up on my note from earlier this week about notary services for your practice.

If you ever have clients who need document signings at their home, hospital, or care facility, I'm happy to accommodate. I handle estate planning documents regularly and understand the importance of getting them right.

{cta}

Best,
{self.settings.contact_name}
{self.settings.business_name}
{self.settings.business_phone}"""

        subject = self._get_subject_line(lead, MessageVariant.FOLLOWUP_1)
        return subject, body.strip()

    def generate_followup2_email(self, lead: Lead) -> Tuple[str, str]:
        """
        Generate the second follow-up email (7-10 days after intro).

        Polite close-the-loop, very brief.
        Returns (subject, body)
        """
        greeting = self._get_greeting(lead)
        cta = self._get_cta_variant(MessageVariant.FOLLOWUP_2)

        body = f"""{greeting},

I'll keep this brief - just wanted to close the loop on my earlier messages about notary services.

{cta}

Take care,
{self.settings.contact_name}
{self.settings.business_name}"""

        subject = self._get_subject_line(lead, MessageVariant.FOLLOWUP_2)
        return subject, body.strip()

    def generate_all_variants(self, lead: Lead) -> List[OutreachMessage]:
        """
        Generate all three email variants for a lead.

        Returns list of OutreachMessage objects (not yet committed to DB).
        """
        messages = []

        # Intro email
        subject, body = self.generate_intro_email(lead)
        messages.append(OutreachMessage(
            lead_id=lead.id,
            variant=MessageVariant.INTRO,
            subject=subject,
            body=body,
            status=MessageStatus.DRAFT
        ))

        # Follow-up #1
        subject, body = self.generate_followup1_email(lead)
        messages.append(OutreachMessage(
            lead_id=lead.id,
            variant=MessageVariant.FOLLOWUP_1,
            subject=subject,
            body=body,
            status=MessageStatus.DRAFT
        ))

        # Follow-up #2
        subject, body = self.generate_followup2_email(lead)
        messages.append(OutreachMessage(
            lead_id=lead.id,
            variant=MessageVariant.FOLLOWUP_2,
            subject=subject,
            body=body,
            status=MessageStatus.DRAFT
        ))

        return messages

    def generate_messages_for_leads(
        self,
        leads: List[Lead],
        session=None
    ) -> List[OutreachMessage]:
        """
        Generate outreach messages for multiple leads.

        If session is provided, messages are added to the session.
        """
        all_messages = []

        for lead in leads:
            if not lead.id:
                logger.warning(f"Lead {lead.display_name} has no ID, skipping message generation")
                continue

            messages = self.generate_all_variants(lead)
            all_messages.extend(messages)

            if session:
                for msg in messages:
                    session.add(msg)

            logger.info(f"Generated {len(messages)} message variants for {lead.display_name}")

        return all_messages

    def preview_email(
        self,
        lead: Lead,
        variant: MessageVariant = MessageVariant.INTRO
    ) -> Tuple[str, str]:
        """
        Preview an email without saving it.

        Returns (subject, body)
        """
        if variant == MessageVariant.INTRO:
            return self.generate_intro_email(lead)
        elif variant == MessageVariant.FOLLOWUP_1:
            return self.generate_followup1_email(lead)
        elif variant == MessageVariant.FOLLOWUP_2:
            return self.generate_followup2_email(lead)
        else:
            return self.generate_intro_email(lead)

    def regenerate_message(
        self,
        message: OutreachMessage,
        lead: Lead
    ) -> OutreachMessage:
        """
        Regenerate a message with fresh content.

        Useful if the user wants a different version.
        """
        subject, body = self.preview_email(lead, message.variant)
        message.subject = subject
        message.body = body
        message.status = MessageStatus.DRAFT
        message.updated_at = datetime.utcnow()
        return message
